#!/usr/bin/env python3

import os
import sys
import functools
import json
import pprint
import sys
print = functools.partial(print, flush=True)
from atomic.definitions import GOLD_STR, GREEN_STR
from atomic.parsing.map_parser import extract_map

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
    def __init__(self, fname, verbose=False):
        self.victims = []
        self.derivedFeatures = []
        self.locations_from = LOCATION_MONITOR
        self.msg_types = ['Event:Triage', 'Mission:VictimList', 'state', 'Event:MissionState',
                          'Event:ToolUsed', 'Event:RoleSelected', 'Event:ToolDepleted', 
                          'Event:VictimPlaced', 'Event:VictimPickedUp',
                          'Event:RubbleDestroyed', 'Event:ItemEquipped']
        if self.locations_from == LOCATION_MONITOR:
            self.msg_types.append('Event:location')
        self.generalFields = ['sub_type', 'playername', 'room_name', 'mission_timer']
        self.typeToLocationFields = {
                        'Event:VictimPickedUp': ['victim_x', 'victim_z'],
                        'Event:VictimPlaced': ['victim_x', 'victim_z'],
                        'Event:Triage': ['victim_x', 'victim_z']}
        self.typeToFields = {
                        'Event:Triage':['triage_state', 'type'], 
                        'Event:RoleSelected': ['new_role', 'prev_role'], 
                        'Event:ToolDepleted': ['tool_type'], 
                        'Event:VictimPlaced': ['type'], 
                        'Event:VictimPickedUp': ['type'], 
                        'Event:ToolUsed': [],
                        'Event:location': [],
                        'Event:RubbleDestroyed': [],
                        'Event:ItemEquipped': ['equippeditemname']}
        self.verbose = verbose
        self.rooms = {}
        self.fname = fname
            
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
        jsonMsgs = [json.loads(line) for line in jsonfile.readlines()]
        jsonfile.close()        
        self.allMTypes = set()
        
        for jmsg in jsonMsgs:
            self.process_message(jmsg)
            self.allMTypes.add(jmsg['msg']['sub_type'])
            
    def read_semantic_map(self):        
        jsonfile = open(self.fname, 'rt')
        
        for line in jsonfile.readlines():
            jmsg = json.loads(line)
            if 'semantic_map' in jmsg['data'].keys():
                semantic_map = jmsg['data']['semantic_map']
                break
        else:
            raise ValueError('Unable to find semantic map')

        room_dict, self.room_edges = extract_map(semantic_map)
        for rid, coords in room_dict.items():
            x0 = coords[0]['x']
            z0 = coords[0]['z']
            x1 = coords[1]['x']
            z1 = coords[1]['z']
            rm = room(rid, [x0, z0, x1, z1])
            self.rooms[rid] = rm
                    
        jsonfile.close()       
        
    def process_message(self, jmsg):        
        mtype = jmsg['msg']['sub_type']
        if mtype not in self.msg_types:
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
            return
            
        if mtype == 'Mission:VictimList':
            self.vList = self.make_victims_list(m['mission_victim_list'])
            return

        player = m.get('playername', m.get('participant_id', None))
        m['playername'] = player
#        if player == None:
#            print('hi')
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
            is_location_event = True

        if is_location_event:
            if player not in self.player_to_curr_room:
                self.player_to_curr_room[player] = ''
            prev_rm = self.player_to_curr_room[player]
            if room_name == prev_rm:
                return
            m['room_name'] = room_name 
            m['sub_type'] = 'Event:location'
            
            ## If new and old rooms not connected
            if (prev_rm != '') and (self.room_edges is not None) and ((prev_rm,room_name) not in self.room_edges):
                if self.verbose: print('Error: %s and %s not connected' %(prev_rm, room_name))
#                print('Error: %s and %s not connected' %(self.rooms[prev_rm], self.rooms[room_name]))
            
            self.player_to_curr_room[player] = room_name
            if self.verbose:
                print('%s moved to %s' %(player, room_name))
                
#            if 'playername' not in 
            
        
        ## If this is a message type we append room name to
        if mtype in self.typeToLocationFields:
            fields = self.typeToLocationFields[mtype]
            x, z = m[fields[0]], m[fields[1]]
            m['room_name'] = self.getRoom(x,z)
            
            ## If event room doesn't match player's last room
            if player not in self.player_to_curr_room:
                self.player_to_curr_room[player] = ''
            if m['room_name'] != self.player_to_curr_room[player]:
                ## If connected, inject an Event:location message
                conn = ((self.player_to_curr_room[player], m['room_name']) in self.room_edges)
                if conn:
                    injecteDd_msg = {'sub_type':'Event:location', 'playername':player, 
                                     'room_name':m['room_name'], 'mission_timer':m['mission_timer']}
                    self.messages.append(injecteDd_msg)
                else:
                    if self.verbose: print('Error: Player %s last moved to %s but event msg is %s. 1-away %s' 
                          %(player, self.player_to_curr_room[player], mtype, self.one_step_removed(self.player_to_curr_room[player], m['room_name'])))

        if m['mission_timer'] == 'Mission Timer not initialized.':
            m['mission_timer'] = '15 : 0'
        
        smallMsg = {k:m[k] for k in m.keys() if k in self.generalFields + self.typeToFields[m['sub_type']]}
        self.messages.append(smallMsg)
        
        ## For every derived feature, ask it to process this message
        for derived in self.derivedFeatures:
            derived.processMsg(smallMsg)
        

    def make_victims_list(self,victim_list_dicts):        
        for vv in victim_list_dicts:
            blktype = vv['block_type']
            if blktype == 'block_victim_1':
                vv.update({'block_type':GREEN_STR})
            else:
                vv.update({'block_type':GOLD_STR})
            room_name = self.getRoom(vv['x'],vv['z'])
            vv.update({'room_name':room_name})
            newvic = victim(room_name,vv['block_type'], vv['x'], vv['z'])
            self.victims.append(newvic)
        return victim_list_dicts
    
    def one_step_removed(self, rm1, rm2):
        if (rm1, rm2) in self.room_edges:
            return True
        nbr1 = set([edge[1] for edge in self.room_edges if edge[1] == rm1])
        nbr2 = set([edge[1] for edge in self.room_edges if edge[1] == rm2])
        return len(nbr1.intersection(nbr2)) > 0

    def getClosestRoom(self, x, z):
        min_diff = 1e5
        closest = None
        for rm in self.rooms.values():
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
        
        closest, min_diff = self.getClosestRoom(x, z)
#        if self.verbose:
#        print('ERROR  %.1f %.1f in %d rooms. Closest %s diff %.1f' %(x, z, len(inrooms), closest, min_diff))
        return closest.name      
        

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
