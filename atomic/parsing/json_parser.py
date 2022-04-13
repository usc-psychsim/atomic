#!/usr/bin/env python3

import os
import functools
import json
from collections import Counter
import numpy as np

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None
print = functools.partial(print, flush=True)
from atomic.definitions import GOLD_STR, GREEN_STR, extract_time
from atomic.parsing.map_parser import extract_map
from atomic.parsing.make_rddl_instance import generate_rddl_victims_from_list_named_vics
from atomic.analytic.ihmc_wrapper import JAGWrapper
from atomic.analytic.gallup_wrapper import GelpWrapper
from atomic.analytic.corenll_wrapper import ComplianceWrapper
from atomic.analytic.cmu_wrapper import TEDWrapper

class room(object):
    def __init__(self, name, coords):
        [x0, z0, x1, z1] = coords
        self.name = name
        self.x0= min(x0, x1)
        self.x1= max(x0, x1)
        self.z0= min(z0, z1)
        self.z1= max(z0, z1)

    def in_room(self, _x, _z, epsilon = 0):
        return (self.x0 - epsilon <= _x) and (_x <= self.x1 + epsilon) and (self.z0 - epsilon <= _z) and (_z <= self.z1 + epsilon)
    
    def __repr__(self):
        return '%s %.0f %.0f %.0f %.0f' % (self.name, self.x0, self.x1, self.z0, self.z1)

class victim(object):
    def __init__(self, loc, color, x, z):
        self.room = loc
        self.color = color
        self.x = x
        self.z = z

LOCATION_MONITOR = 0
STATE_MSGS = 1

class JSONReader(object):
    def __init__(self, fname, verbose=False, use_collapsed_map=True, use_ihmc_locations=True):
        self.USE_COLLAPSED_MAP = use_collapsed_map
        if self.USE_COLLAPSED_MAP and not use_ihmc_locations:
            raise ValueError('Cannot use collapsed map without using IHMC locations')
            
        self.victims = []
        self.derivedFeatures = []
        self.locations_from = LOCATION_MONITOR
        self.msg_types = {'Event:Triage', 'Mission:VictimList', 'state', 'Event:MissionState',
                          'Event:VictimPlaced', 'Event:VictimPickedUp', 'Event:VictimEvacuated',
                          'Event:RubbleDestroyed', 'Event:RubblePlaced', 'Event:RubbleCollapse',
                          'Event:Signal', 'Event:Chat',
                          'Event:ProximityBlockInteraction',
                          'Event:MarkerPlaced', 'Event:MarkerRemoved', 
#                          'Event:ItemEquipped', 'Event:dialogue_event',
                          # dp added:
#                          'Event:Scoreboard', 'asr:transcription', 
                          'start'
                          }

        self.generalFields = ['sub_type', 'playername', 'room_name', 'mission_timer', 'old_room_name', 'timestamp',
                            # dp added:
#                            'marker_legend', 'extractions', 'client_info'
#                            'scoreboard', 'participant_id', 
                            'marker_type', 'victim_type', 
                            ]
        self.typeToLocationFields = {
                        'Event:VictimPickedUp': ['victim_x', 'victim_z'],
                        'Event:VictimPlaced': ['victim_x', 'victim_z'],
                        'Event:VictimEvacuated': ['victim_x', 'victim_z'],
                        'Event:RubbleDestroyed': ['rubble_x', 'rubble_z'],
                        'Event:RubblePlaced': ['rubble_x', 'rubble_z'],
                        'Event:RubbleCollapse': ['triggerLocation_x', 'triggerLocation_z'],
                        'Event:Signal': ['x', 'z'],
                        'Event:MarkerPlaced': ['marker_x', 'marker_z'], 
                        'Event:MarkerRemoved': ['marker_x', 'marker_z'], 
                        'Event:ProximityBlockInteraction': ['victim_x', 'victim_z'],
                        'Event:Triage': ['victim_x', 'victim_z']}
        self.typeToFields = {
                        'Event:Triage':['triage_state', 'type', 'victim_id'], 
                        'Event:VictimPlaced': ['type', 'victim_id'], 
                        'Event:VictimPickedUp': ['type', 'state', 'victim_id'], 
                        'Event:VictimEvacuated': ['type', 'correct_area', 'victim_id', 'success'], 
                        'Event:Signal': ['message'],
                        'Event:ToolUsed': [],
                        'Event:location': [],
                        'Event:Chat': ['sender', 'addressees', 'text'],
                        'Event:MarkerPlaced': ['type'], 
                        'Event:MarkerRemoved': ['type'], 
                        'Event:MarkerDestroyed': ['type'],
                        'Event:ProximityBlockInteraction': ['action_type', 'players_in_range', 'victim_id'],
                        'Event:RubbleDestroyed': [],
                        'Event:RubblePlaced': []}
        self.participant_2_role = dict()        
        self.ac_filters = {'ihmc':{'observations/events/player/jag', 'observations/events/mission',
                                   'observations/events/player/role_selected'}, 
#                           'cornell':{'agent/ac/player_compliance'},
#                           'cmu_ted':{'agent/ac/cmuta2-ted-ac/ted'},
#                           'gallup':{'agent/gelp'}
                           }
        self.ac_wrappers = {'ihmc':JAGWrapper('ihmc', 'jag'),
#                            'cornell': ComplianceWrapper('cornell', 'compliance'),
#                            'cmu_ted': TEDWrapper('cmu', 'ted'), 
#                            'gallup': GelpWrapper('gallup', 'gelp')
                            }
        self.all_topics = set()
        
        def make_victime_name(x):
            return 'v' + str(x)
        
        def make_addressees(lst):
            return [self.participant_2_role[adr] for adr in lst]
            
        self.field_transformations = {'victim_id': make_victime_name, 'addressees': make_addressees}
        self.verbose = verbose
        self.rooms = {}
        self.fname = fname
        if use_ihmc_locations:
            self.locations_from = LOCATION_MONITOR
            self.msg_types.add('Event:location')
        else:
            self.locations_from = STATE_MSGS
        self.subjects = None
        self.player_maps = {}
        self.player_marker = {}
        self.saved_victim_ids = []
            
    def registerFeatures(self, feats):
        for f in feats:
            self.derivedFeatures.append(f)

    def reset(self):
        self.messages = []
        self.mission_running = False
        self.player_to_curr_room = dict()
        

    def make_role_mappings(self, roles):
        for role_msg in roles:
            role = role_msg['new_role'].lower()[:3]
            self.participant_2_role[role_msg['participant_id']] = role
        print(self.participant_2_role)
        

    def process_json_file(self, fname):
        self.reset()
        
        jsonfile = open(fname, 'rt')
        self.jsonMsgs = [json.loads(line) for line in jsonfile.readlines()]
        jsonfile.close()        
        self.allMTypes = set()
        
        roles = [m['data'] for m in self.jsonMsgs if m['msg']['sub_type']=='Event:RoleSelected']
        self.make_role_mappings(roles)
        
#        if tqdm and not self.verbose:
#            iterable = tqdm(self.jsonMsgs)
#        else:
#            iterable = self.jsonMsgs
        for ji, jmsg in enumerate(self.jsonMsgs):
            msg_topic = jmsg.get('topic', '')
            self.allMTypes.add(jmsg['msg']['sub_type'])
#            self.process_message(jmsg)
            self.all_topics.add(msg_topic)
            for ac_name, topics in self.ac_filters.items():
                if (msg_topic == 'trial') or (msg_topic in topics):
                    self.ac_wrappers[ac_name].handle_message(msg_topic, jmsg['msg'], jmsg['data'])
                    
            if len(self.ac_wrappers['ihmc'].messages) > 40000:
                break
            
        ## Add time in seconds and a serial number to each message
        for i, msg in enumerate(self.messages):
            msg['serial'] = i
            msg['time_sec'] = extract_time(msg)
            
    def read_semantic_map(self):        
        jsonfile = open(self.fname, 'rt')
        
        self.semantic_map = None
        for line in jsonfile.readlines():
            jmsg = json.loads(line)
            if 'semantic_map' in jmsg['data'].keys():
                self.semantic_map = jmsg['data']['semantic_map']
                break
        else:
            raise ValueError('Unable to find semantic map')
        jsonfile.close()

        # Sudeepta's map transformation code
        room_dict, room_connections = extract_map(self.semantic_map)
        
        if self.USE_COLLAPSED_MAP:
            ## Overwrite room_edges and store name lookup and new room names
            from atomic.parsing.remap_connections import transformed_connections
            self.room_edges = []
            edges, self.room_name_lookup, new_map, orig_map = transformed_connections(self.semantic_map)
            for a,b in edges:
                self.room_edges.append((a,b))
                self.room_edges.append((b,a))     
            self.new_room_names = new_map['new_locations']
        else:
            self.room_edges = room_connections

        ## Whether we're using the collapsed map or not, we keep track of the coordinates of the ORIGINAL rooms            
        for rid, coords in room_dict.items():
            x0 = coords[0]['x']
            z0 = coords[0]['z']
            x1 = coords[1]['x']
            z1 = coords[1]['z']
            rm = room(rid, [x0, z0, x1, z1])
            self.rooms[rid] = rm
            
    def get_victims(self):
        self.read_semantic_map()
        
        jsonfile = open(self.fname, 'rt')
        jsonMsgs = [json.loads(line) for line in jsonfile.readlines()]
        jsonfile.close()
        
        for jmsg in jsonMsgs:
            mtype = jmsg['msg']['sub_type']
            m = jmsg['data']
            if mtype == 'Mission:VictimList':
                return self.make_victims_list(m['mission_victim_list'])
            
        return None
        
    
    def is_2steps_connected(self, rm1, rm2):
        nbrs_of_1 = set([other for (rma, other) in self.room_edges if rma == rm1])
        nbrs_of_2 = set([other for (rma, other) in self.room_edges if rma == rm2])
        common_nbrs = nbrs_of_1.intersection(nbrs_of_2)
        if len(common_nbrs) == 0:
            return False, None
        return True, common_nbrs.pop()
        
    
    def process_message(self, jmsg):        
        mtype = jmsg['msg']['sub_type']
        
        if mtype == 'start':
            if 'client_info' in jmsg['data']:
                # Initial message about experimental setup
                if self.subjects is None:
                    self.subjects = {entry['participant_id']:entry.get('playername', entry['callsign']) for entry in jmsg['data']['client_info']}
                self.player_maps = {entry.get('playername', entry['participant_id']): entry['staticmapversion'] 
                    for entry in jmsg['data']['client_info'] if 'staticmapversion' in entry}
                self.player_marker = {entry.get('playername', entry['participant_id']): entry['markerblocklegend'] 
                    for entry in jmsg['data']['client_info'] if 'markerblocklegend' in entry}
            
            return
        elif mtype not in self.msg_types:
            return
        m = jmsg['data']
        m['sub_type'] = mtype
        
        if 'jag' in m.keys():
            self.jag_msgs.append(m)
            
        
        if mtype == "Event:MissionState":
            mission_state = m['mission_state']
            self.mission_running = (mission_state == "Start")
            if self.verbose: print('mission ', mission_state)
            return
                
        if mtype == "Event:Pause":
            isPaused = m['paused']
            self.mission_running = (isPaused != "true")
            if self.verbose: print('paused', isPaused )
            return

        if (not self.mission_running) or mtype not in self.msg_types:
            if (mtype != 'start') and (mtype != 'Event:RoleSelected'):
                return
            
        if mtype == 'Mission:VictimList':
            self.vList = self.make_victims_list(m['mission_victim_list'])
            return
        
        ## Keep track of saved victim IDs
        if (mtype == 'Event:Triage') and (m['triage_state'] == 'SUCCESSFUL'):
            self.saved_victim_ids.append(m['victim_id'])
        
        ## If the picked up victim is saved/unsaved, inject the corresponding field in the msg
        if mtype == 'Event:VictimPickedUp':
            if 'saved' in m['type'] :
                m['state'] = 'saved'
            else:
                m['state'] = 'unsaved'        

        is_location_event = False
        player = self.participant_2_role.get(m.get('participant_id', ''), '')
        m['playername'] = player

        if player not in self.player_to_curr_room:
            self.player_to_curr_room[player] = ''
        prev_rm = self.player_to_curr_room[player]

        if mtype == "state":
            if self.locations_from == LOCATION_MONITOR:
                return
            room_name = self.getRoom(m['x'], m['y'])
            is_location_event = True
        
        if mtype == "Event:location":
            if self.locations_from == STATE_MSGS:
                return
            if 'locations' not in m.keys():
                return
            room_names = [loc['id'] for loc in m['locations'] if loc['id'] in self.rooms]
            if len(room_names) != 1:
                if self.verbose: print('Error: cant tell which room %s' %(m['locations']))
                return
            room_name = room_names[0]
            
            if self.USE_COLLAPSED_MAP:
                room_name = self.room_name_lookup[room_name]
            if room_name == prev_rm:
                return
            
            distance_away = -1
            if (prev_rm == ''):
                distance_away = 1
            elif (prev_rm, room_name) in self.room_edges:
                distance_away = 1
            else:
                connected, common_nbr = self.is_2steps_connected(prev_rm, room_name)
                if connected:
                    distance_away = 2                    
            
            ## If new and old rooms not connected
#            if (prev_rm != '') and (self.room_edges is not None) and ((prev_rm,room_name) not in self.room_edges):
            if distance_away < 0:
                if self.verbose: print('Error: %s and %s not connected' %(prev_rm, room_name))
                
            if distance_away == 1:
                m['old_room_name'] = prev_rm
                
            if distance_away == 2:
                # Inject a move to the common neighbor between prev_rm and the new room
                injected_msg = {'sub_type':'Event:location', 'playername':player, 
                                 'old_room_name': prev_rm, 'room_name':common_nbr, 'mission_timer':m['mission_timer']}
                self.messages.append(injected_msg)
                if self.verbose: print('Injected', injected_msg, 'to reconcile', m)
                # Pretend that the msg is about moving from the common nbr to the new room
                m['old_room_name'] = common_nbr
            
            self.player_to_curr_room[player] = room_name
            if self.verbose:
                print('%s moved to %s' %(player, room_name))   
                
            m['room_name'] = room_name 
            m['sub_type'] = 'Event:location'
            is_location_event = True
            
#        elif mtype == 'Event:MarkerPlaced':
#            m['room_name'] = self.getRoom(m['marker_x'], m['marker_z'])
#            m['marker_type'] = m['type']
#            m['victim_type'] = 'none'
#            if player and player in self.player_marker:
#                m['marker_legend'] = self.player_marker[player]
#            m['closest_room'] = self.getClosestRoom(m['marker_x'], m['marker_z'])[0].name
#            victims = [v['block_type'] for v in self.vList if v['room_name'] == m['room_name']]
#            victims_nearby = [v['block_type'] for v in self.vList if v['room_name'] == m['closest_room']]
#            m['mark_regular'] = victims.count('regular')
#            m['mark_critical'] = victims.count('critical')
#        elif mtype == 'asr:transcription':
#            if jmsg['msg']['trial_id'] in {'5b748391-9277-4737-8286-6b385ea1d6ce', 'bd035ce8-ac2c-43eb-9f36-5974a08c02ed'}:
#                # Trial 523 or 524 has participant transcripts from Trials 443 and 444
#                if jmsg['data']['participant_id'] in {'E000484', 'E000485', 'E000486'}:
#                    return
#            m['extractions'] = jmsg['data'].get('extractions', [])
#            m['text'] = jmsg['data']['text']
            
#        if is_location_event:     
        
        ## If this is a message type we append room name to
        if mtype in self.typeToLocationFields:
            fields = self.typeToLocationFields[mtype]
            x, z = m[fields[0]], m[fields[1]]
            orig_event_room = self.getRoom(x,z)            
            if self.USE_COLLAPSED_MAP:
                event_room = self.room_name_lookup[orig_event_room]
            else:
                event_room = orig_event_room
            m['room_name'] = event_room
            m['orig_room_name'] = orig_event_room
            
            ## If event room doesn't match player's last room
            if event_room != prev_rm:
                ## If connected, inject an Event:location message
                conn = (prev_rm, m['room_name']) in self.room_edges
                if conn:
                    injected_msg = {'sub_type':'Event:location', 'playername':player, 
                                     'old_room_name': prev_rm, 'room_name':event_room, 'mission_timer':m['mission_timer']}
                    self.messages.append(injected_msg)
                    ## When you inject this location change message, assume it will go through and update player's room
                    self.player_to_curr_room[player] = event_room
                    if self.verbose: print('Injected', injected_msg, 'to reconcile', m)
                else:
                    if self.verbose: 
                        print('Error: Player %s last moved to %s but event %s is in %s. 1-away %s' 
                          %(player, prev_rm, mtype, event_room, self.one_step_removed(self.player_to_curr_room[player], event_room)))
        
        if self.verbose and (not is_location_event) and ('room_name' in m.keys()):
            print('%s did %s in %s (orig %s) to %s %s' %(player, mtype, m['room_name'], m.get('orig_room_name', ''), m.get('victim_id', ''),
                  m.get('triage_state', '')))
        

        if 'mission_timer' in m and m['mission_timer'] == 'Mission Timer not initialized.':
            m['mission_timer'] = '15 : 0'
        
        smallMsg = {k:m[k] for k in m if k in self.generalFields + self.typeToFields.get(m['sub_type'], [])}
        for k,v in smallMsg.items():
            if k in self.field_transformations.keys():
                smallMsg[k] = self.field_transformations[k](v)
        self.messages.append(smallMsg)

        ## For every derived feature, ask it to process this message
        for derived in self.derivedFeatures:
            derived.processMsg(smallMsg)
            
    def stats(self):        
        print('==Msg count by type', self.filter_and_tally([],[], 'sub_type'))        
        print('\n==VictimPickedUp by player', self.filter_and_tally(['sub_type'],['Event:VictimPickedUp'], 'playername'))
        print('\n==VictimPickedUp by state', self.filter_and_tally(['sub_type'],['Event:VictimPickedUp'], 'state'))
        print('\n==VictimEvacuated by player (successful)', self.filter_and_tally(['sub_type', 'success'],['Event:VictimEvacuated', 'True'], 'playername'))
        print('\n==VictimEvacuated by player (failed)', self.filter_and_tally(['sub_type', 'success'],['Event:VictimEvacuated', 'False'], 'playername'))
        print('\n==Triage by type', self.filter_and_tally(['sub_type', 'triage_state'],['Event:Triage', 'SUCCESSFUL'], 'type'))
        print('\n==MarkerPlaced by player', self.filter_and_tally(['sub_type'],['Event:MarkerPlaced'], 'playername'))
        print('\n==MarkerPlaced by type', self.filter_and_tally(['sub_type'],['Event:MarkerPlaced'], 'type'))
        print('\n==MarkerRemoved by player', self.filter_and_tally(['sub_type'],['Event:MarkerRemoved'], 'playername'))
        print('\n==MarkerRemoved by type', self.filter_and_tally(['sub_type'],['Event:MarkerRemoved'], 'type'))
        print('\n==RubbleCollapse by player', self.filter_and_tally(['sub_type'],['Event:RubbleCollapse'], 'playername'))
        print('\n==RubbleDestroyed by room', self.filter_and_tally(['sub_type'],['Event:RubbleDestroyed'], 'room_name'))
        print('\n==Signal by content', self.filter_and_tally(['sub_type'],['Event:Signal'], 'message'))
        print('\n==ProximityBlockInteraction by victim', self.filter_and_tally(['sub_type'],['Event:ProximityBlockInteraction'], 'victim_id'))



    ''' 
    Args:   
                msg1_condition, msg2_condition: 2 dicts with the conditions you're looking for in the json msgs
                A key with value None in msg1_condition denotes a wildcard for which you want msg1[key]==msg2[key]
                time_limit: msg2 should appear at most time_limit seconds after msg2    
    Example 1:  time between a player having rubble collapse on them and the engineer starting to destroy it
                msg1_condition = {'sub_type':'Event:RubbleCollapse', 'room_name':None}
                msg2_condition = {'playername':'eng', 'sub_type':'Event:RubbleDestroyed'}
    Example 2:  time between medic triaging a victim and transporter evacuating it
                msg1_condition = {'sub_type':'Event:RubbleCollapse', 'room_name':None}
                msg2_condition = {'playername':'eng', 'sub_type':'Event:RubbleDestroyed'}
    Example 3:  time between medic identifying a critical victim in a room and another player moving to that room
                msg1_condition = {'playername':'med', 'sub_type':'Event:Chat', 'text':'{"text":"Victim Type : C.","color":"red"}', 'room_name':None}
                msg2_condition = {'sub_type':'Event:location'}
    Returns 2 lists
    positives:  Each element is a list [m1, m2, td]. cases where the 2 conditions were met less than time_limit seconds apart
    negatives:  Cases where 2 conditions where met > time_limit seconds apart. If m2 is None, the corresponding m1 was never pairer
                (e.g., a victim that was triaged but never evacuated by the transporter (maybe it was evac'd by someone else))
    '''
    def collect_msg_seq(self, msg1_condition, msg2_condition, time_limit):
        positives = []
        negatives = []
        msg1_matches = []
        
        for msg in self.messages:
            msg1_match = np.all([msg.get(key, '') == val for key, val in msg1_condition.items() if val is not None])
            if msg1_match:
                msg1_matches.append(msg)
                continue
            
            ## If no msg 1 matches
            if len(msg1_matches) == 0:
                continue
            
            msg2_match = np.all([msg.get(key, '') == val for key, val in msg2_condition.items()])
            if not msg2_match:
                continue
            
            ## If we're here, there are msg1 matches and msg matches msg2
            to_pop = []
            for m1 in msg1_matches:
                wildcards = {key:m1[key] for key,val in msg1_condition.items() if val is None}
                wildcard_match = np.all([msg.get(key, '') == val for key, val in wildcards.items()])

                if not wildcard_match:
                    continue
                to_pop.append(m1)
                tdiff = msg['time_sec'] - m1['time_sec']
                if tdiff <= time_limit:
                    positives.append([m1, msg, tdiff])
                else:
                    negatives.append([m1, msg, tdiff])
                
            ## Clear prev_msg1
            for m1 in to_pop:
                msg1_matches.remove(m1)
        
        
        ## Add any un-paired msg1s to the negatives
        for m1 in msg1_matches:
            negatives.append([m1, None, -1])
        return positives, negatives
        
        
    def collapse_messages(self, remove_types=[]):
        collapsed_msgs = []
        last_msg = {}
        for msg in self.messages:
            if msg['sub_type'] in remove_types:
                continue
            flds = ['sub_type', 'playername', 'room_name'] + self.typeToFields.get(msg['sub_type'], [])
            fields_changed = np.any([ msg.get(fld, '') != last_msg.get(fld, '') for fld in flds  ])
            if fields_changed:
                last_msg = msg
                collapsed_msgs.append(msg)
                
        return collapsed_msgs
    
    def filter_out(self, keys, values, keep_keys=None):
        filts = []
        for msg in self.messages:
            msg_vals = [str(msg.get(k, '')).lower() for k in keys]
            values = [str(v).lower() for v in values]
            if msg_vals != values:
                if keep_keys is None:
                    m = msg
                else:
                    m = {k:msg[k] for k in keep_keys}
                filts.append(m)
        
        return filts
    
    def filter(self, keys, values, keep_keys=None):
        filts = []
        for msg in self.messages:
            msg_vals = [str(msg.get(k, '')).lower() for k in keys]
            values = [str(v).lower() for v in values]
            if msg_vals == values:
                if keep_keys is None:
                    m = msg
                else:
                    m = {k:msg[k] for k in keep_keys}
                filts.append(m)
        
        return filts
    
    def filter_and_tally(self, keys, values, talley_key):
        filts = self.filter(keys, values)
        talley_vals = [msg[talley_key] for msg in filts]
        return Counter(talley_vals)

    def make_victims_list(self,victim_list_dicts_in):
        victim_list_dicts_out = []
        for vv_in in victim_list_dicts_in:
            vv = dict(vv_in)
            blktype = vv['block_type']
            if blktype == 'block_victim_1':
                vv.update({'block_type':GREEN_STR})
            else:
                vv.update({'block_type':GOLD_STR})
            room_name = self.getRoom(vv['x'],vv['z'])
            vv_in.update({'room_name':room_name})
            
            if self.USE_COLLAPSED_MAP:
                room_name = self.room_name_lookup[room_name]
            
            vv.update({'room_name':room_name})
            if self.verbose:
                print('victim', vv_in['unique_id'], 'orig', vv_in['room_name'], 'clpsd', vv['room_name'])
            newvic = victim(room_name,vv['block_type'], vv['x'], vv['z'])
            self.victims.append(newvic)
            victim_list_dicts_out.append(vv)
        return victim_list_dicts_out
    
    def write_rddl_file(self, rddl_template):
        if len(self.vList) == 0:
            print('ERROR: No victims msg in metadata file')
            return None
        if self.USE_COLLAPSED_MAP:
            rooms = list(set([self.room_name_lookup[rm] for rm in self.rooms.keys()]))
        else:
            rooms = list(self.rooms.keys())
        vic_str = generate_rddl_victims_from_list_named_vics(self.vList, rooms)
            
        rddl_temp_file = open(rddl_template + '.rddl', "r")    
        master_rddl_str = rddl_temp_file.read()
        rddl_str = master_rddl_str.replace('VICSTR', vic_str) 
        rddl_inst_file = open(rddl_template + '_inst.rddl', "w")
        rddl_inst_file.write(rddl_str)    
        rddl_inst_file.close()
        
    
    def one_step_removed(self, rm1, rm2):
        if (rm1, rm2) in self.room_edges:
            return True
        nbr1 = set([edge[1] for edge in self.room_edges if edge[1] == rm1])
        nbr2 = set([edge[1] for edge in self.room_edges if edge[1] == rm2])
        return len(nbr1.intersection(nbr2)) > 0

    def getClosestRoom(self, x, z, candidate_rooms=[]):
        if candidate_rooms == []:
            candidate_rooms = self.rooms.values()
        min_diff = 1e5
        closest = None
        for rm in candidate_rooms:
            x_diff = 0
            z_diff = 0
            if x < rm.x0:
                x_diff = rm.x0 - x
            elif x > rm.x1:
                x_diff = x - rm.x1
            if z < rm.z0:
                z_diff = rm.z0 - z
            elif z > rm.z1:
                z_diff = z - rm.z1
            if (x_diff + z_diff) < min_diff:
                min_diff = x_diff + z_diff
                closest = rm
        return closest, min_diff

    def getRoom(self, x, z): 
        inrooms = [r for r in self.rooms.values() if r.in_room(x,z)]
        if len(inrooms) == 1:
            return inrooms[0].name
#        closest, min_diff = self.getClosestRoom(x, z, inrooms)
        
        ## If point is in multiple rooms, doesn't matter which we consider 
        ## it to be as long as it's the same every time this function is called
        names = [r.name for r in inrooms]
        names.sort()
        chosen = names[0]        
        if self.verbose:
            print('ERROR  %.1f %.1f in %s rooms. Chose %s ' %(x, z, inrooms, chosen ))
        return chosen 
        

    def writeToJson(self, inJsonFileName, psychsimdir):
        outname = inJsonFileName.split('/')
        outfile = psychsimdir+'/'+outname[len(outname)-1]+'.json'
        if self.verbose: print("writing to "+outfile)
        msgout = open(outfile,'w')
        for m in self.messages:
            json.dump(m,msgout)
            msgout.write('\n')
        msgout.close()

def createJSONParser(room_list):
    reader = JSONReader(room_list, False)
    return reader

def getMessages(args):        
    ## Local directory containing multiple json files, if multitrial
    msgdir = ''
    ## Output directory to store parsed content if parsing more than 1 file
    psychsimdir = '.'
    multitrial = False
    verbose = False
    
    # Grab inputs, where available
    for a,val in args.items():     
        if a == '--msgfile':
            msgfile = args[a]
        elif a == '--roomfile':
            room_list = args[a]
        elif a == '--multitrial':
            multitrial = True
            msgdir = args[a]
        elif a == '--psychsimdir':
            psychsimdir = args[a]
        elif a == '--verbose':
            verbose = True
        elif a == '--help':
            print("USAGE:")
            print('--home: specify atomic home')
            print("--msgfile <trial messages file>")
            print("--roomfile <.json or .csv list of rooms>")
            print("--multitrial <directory with message files to be processed>")
            print("--verbose : will provide extra info for each message, e.g. x/z coords") 
            print("--psychsimdir <directory to store processed message files>")
            return

    reader = JSONReader(room_list, verbose)
    
    if multitrial: 
        if msgdir == '':
            print("ERROR: must provide message directory --multitrial <directory>")
            return
        file_arr = os.listdir(msgdir)
        for fi, f in enumerate(file_arr):
            full_path = os.path.join(msgdir,f)
            if os.path.isfile(full_path):
                print("processing file "+str(fi)+" of "+str(len(file_arr))+" :: "+str(full_path))
                reader.process_json_file(f)
                reader.writeToJson(full_path, psychsimdir)
    # default to procesing single file, returning a list of dictionaries
    else:
        reader.process_json_file(msgfile)
        return reader.messages, reader.vList
