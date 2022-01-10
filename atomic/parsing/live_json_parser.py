#!/usr/bin/env python3

import os
import functools
import json
import sys

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None
print = functools.partial(print, flush=True)
from atomic.definitions import GOLD_STR, GREEN_STR
from atomic.parsing.map_parser import extract_map
from atomic.parsing.make_rddl_instance import generate_rddl_victims_from_list

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
                          'Event:ToolUsed', 'Event:RoleSelected', 'Event:ToolDepleted',
                          'Event:VictimPlaced', 'Event:VictimPickedUp',
                          'Event:RubbleDestroyed', 'Event:ItemEquipped', 'Event:dialogue_event',
                          # dp added:
                          'Event:Scoreboard', 'Event:MarkerPlaced', 'asr:transcription', 'start'
                          }

        self.generalFields = ['sub_type', 'playername', 'room_name', 'mission_timer', 'old_room_name', 'timestamp',
                            # dp added:
                            'scoreboard', 'participant_id', 'marker_type', 'victim_type', 
                            'marker_legend', 'mark_regular', 'mark_critical', 'extractions', 'client_info'
                            ]
        self.typeToLocationFields = {
                        'Event:VictimPickedUp': ['victim_x', 'victim_z'],
                        'Event:VictimPlaced': ['victim_x', 'victim_z'],
                        'Event:Triage': ['victim_x', 'victim_z']}
        self.typeToFields = {
                        'Event:Triage':['triage_state', 'type'], 
                        'Event:RoleSelected': ['new_role', 'prev_role'], 
                        'Event:ToolDepleted': ['tool_type'], 
                        'Event:VictimPlaced': ['type'], 
                        'Event:VictimPickedUp': ['type', 'state'], 
                        'Event:ToolUsed': [],
                        'Event:location': [],
                        'Event:RubbleDestroyed': [],
                        'Event:ItemEquipped': ['equippeditemname']}
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
        self.chat_msg = {} # use for chat (testing)
            
    def registerFeatures(self, feats):
        for f in feats:
            self.derivedFeatures.append(f)

    def reset(self):
        self.messages = []
        self.mission_running = False
        self.player_to_curr_room = dict()
        

    def process_json_file(self, fname):
        self.reset()
        
        jsonfile = open(fname, 'rt')
        self.jsonMsgs = [json.loads(line) for line in jsonfile.readlines()]
        jsonfile.close()        
        self.allMTypes = set()
        
#        if tqdm and not self.verbose:
#            iterable = tqdm(self.jsonMsgs)
#        else:
#            iterable = self.jsonMsgs
        for ji, jmsg in enumerate(self.jsonMsgs):

            res_type = self.process_message(jmsg)
            self.allMTypes.add(jmsg['msg']['sub_type'])
            
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

    def add_rooms_map_live(self,mmsg):        
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

        # NOT USED EXCEPT IN PKL    
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
        do_move = ''
        mtype = jmsg['msg']['sub_type']
        if mtype == 'start':
            if 'client_info' in jmsg['data']:
                # Initial message about experimental setup
                if self.subjects is None:
                    self.subjects = {entry.get('playername', entry['callsign']): entry['participant_id'] for entry in jmsg['data']['client_info']}
                self.player_maps = {entry.get('playername', entry['participant_id']): entry['staticmapversion'] 
                    for entry in jmsg['data']['client_info'] if 'staticmapversion' in entry}
                self.player_marker = {entry.get('playername', entry['participant_id']): entry['markerblocklegend'] 
                    for entry in jmsg['data']['client_info'] if 'markerblocklegend' in entry}
            else:
                return
        elif mtype not in self.msg_types:
            return
        m = jmsg['data']
        m['sub_type'] = mtype
        
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
            if m['victim_id'] in self.saved_victim_ids:
                m['state'] = 'saved'
            else:
                m['state'] = 'unsaved'        

        player = m.get('playername', m.get('participant_id', None))
        m['playername'] = player

        if player not in self.player_to_curr_room:
            self.player_to_curr_room[player] = ''
        prev_rm = self.player_to_curr_room[player]

        if 'participant_id' not in m:
            m['participant_id'] = self.subjects.get(m['playername'], None)

        is_location_event = False
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
                do_move = injected_msg
                # set chat msg here (so maybe don't need to return?)
                self.chat_msg = injected_msg
                if self.verbose: 
                    # eventually chat here?
                    print('Injected', injected_msg, 'to reconcile', m)
                return do_move

                # Pretend that the msg is about moving from the common nbr to the new room
                m['old_room_name'] = common_nbr
                return do_move

            self.player_to_curr_room[player] = room_name
            #if self.verbose:
                #print('%s moved to %s' %(player, room_name))   
                
            m['room_name'] = room_name 
            m['sub_type'] = 'Event:location'
            is_location_event = True
            
        elif mtype == 'Event:MarkerPlaced':
            m['room_name'] = self.getRoom(m['marker_x'], m['marker_z'])
            m['marker_type'] = m['type']
            m['victim_type'] = 'none'
            if player and player in self.player_marker:
                m['marker_legend'] = self.player_marker[player]
            m['closest_room'] = self.getClosestRoom(m['marker_x'], m['marker_z'])[0].name
            victims = [v['block_type'] for v in self.vList if v['room_name'] == m['room_name']]
            victims_nearby = [v['block_type'] for v in self.vList if v['room_name'] == m['closest_room']]
            m['mark_regular'] = victims.count('regular')
            m['mark_critical'] = victims.count('critical')
        elif mtype == 'asr:transcription':
            if jmsg['msg']['trial_id'] in {'5b748391-9277-4737-8286-6b385ea1d6ce', 'bd035ce8-ac2c-43eb-9f36-5974a08c02ed'}:
                # Trial 523 or 524 has participant transcripts from Trials 443 and 444
                if jmsg['data']['participant_id'] in {'E000484', 'E000485', 'E000486'}:
                    return
            m['extractions'] = jmsg['data'].get('extractions', [])
            m['text'] = jmsg['data']['text']
            
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
                    if self.verbose: print('Error: Player %s last moved to %s but event %s is in %s. 1-away %s' 
                          %(player, prev_rm, mtype, event_room, self.one_step_removed(self.player_to_curr_room[player], event_room)))
        
        if self.verbose and (not is_location_event) and ('room_name' in m.keys()):
            print('%s did %s in %s (orig %s) to %s %s' %(player, mtype, m['room_name'], m.get('orig_room_name', ''), m.get('victim_id', ''),
                  m.get('triage_state', '')))
        

        if 'mission_timer' in m and m['mission_timer'] == 'Mission Timer not initialized.':
            m['mission_timer'] = '15 : 0'
        
        smallMsg = m # {k:m[k] for k in m if k in self.generalFields + self.typeToFields.get(m['sub_type'], [])}
        self.messages.append(smallMsg)

        ## For every derived feature, ask it to process this message
        for derived in self.derivedFeatures:
            derived.processMsg(smallMsg)
        

    def make_victims_list(self,victim_list_dicts_in):
        self.verbose = False
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
        rooms = list(set([self.room_name_lookup[rm] for rm in self.rooms.keys()]))
        vic_str = generate_rddl_victims_from_list(self.vList, rooms)
            
        rddl_temp_file = open(rddl_template + '.rddl', "r")    
        master_rddl_str = rddl_temp_file.read()
        rddl_str = master_rddl_str.replace('VICSTR', vic_str) 
        rddl_inst_file = open(rddl_template + '_v.rddl', "w")
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
