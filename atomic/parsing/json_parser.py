#!/usr/bin/env python3

import os
import sys
import functools
import json
print = functools.partial(print, flush=True)
from atomic.definitions import GOLD_STR, GREEN_STR

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

class victim(object):
    def __init__(self, loc, color, x, z):
        self.room = loc
        self.color = color
        self.x = x
        self.z = z

class JSONReader(object):
    def __init__(self, room_dict, verbose=False):
        self.rooms = []
        self.victims = []
        self.fov_messages = []
        self.derivedFeatures = []
        self.msg_types = ['Event:Triage', 'Mission:VictimList', 'state',
                          'Event:ToolUsed', 'Event:RoleSelected', 'Event:ToolDepleted', 
                          'Event:VictimPlaced', 'Event:VictimPickedUp',
                          'Event:RubbleDestroyed', 'Event:ItemEquipped']
        self.generalFields = ['sub_type', 'playername', 'room_name', 'mission_timer']
        self.typeToLocationFields = {
                        'Event:VictimPickedUp': ['victim_x', 'victim_z'],
                        'Event:VictimPlaced': ['victim_x', 'victim_z']}
        self.typeToFields = {
                        'Event:Triage':['triage_state', 'type'], 
                        'Event:RoleSelected': ['new_role', 'prev_role'], 
                        'Event:ToolDepleted': ['tool_type'], 
                        'Event:VictimPlaced': ['type'], 
                        'Event:VictimPickedUp': ['type'], 
                        'Event:ToolUsed': [],
                        'Event:Location': [],
                        'Event:RubbleDestroyed': [],
                        'Event:ItemEquipped': ['equippeditemname']}
        self.verbose = verbose
        for rid, coords in room_dict.items():
            x0 = coords[0]['x']
            z0 = coords[0]['z']
            x1 = coords[1]['x']
            z1 = coords[1]['z']
            rm = room(rid, [x0, z0, x1, z1])
            self.rooms.append(rm)
            
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
        for jmsg in jsonMsgs:
            self.process_message(jmsg)
        
    def process_message(self, jmsg):
        mtype = jmsg['msg']['sub_type']
        m = jmsg['data']
        m['sub_type'] = mtype
        
        if mtype == "Event:MissionState":
            mission_state = m['mission_state']
            self.mission_running = (mission_state == "Start")
            print('mission ', mission_state)
            return
                
        if mtype == "Event:Pause":
            isPaused = m['paused']
            self.mission_running = (isPaused != "true")
            print('paused', isPaused )
            return
            
        if (not self.mission_running) or mtype not in self.msg_types:
            return
            
        if mtype == 'Mission:VictimList':
            self.vList = self.make_victims_list(m['mission_victim_list'])
            return
        
        if mtype == 'Event:Triage':
            pass
                
        if mtype == "state":
            room_name = self.getRoom(m['x'], m['y'])
            player = m['playername']
            if player not in self.player_to_curr_room:
                self.player_to_curr_room[player] = ''
            if room_name == self.player_to_curr_room[player]:
                return
            else:
                m['sub_type'] = 'Event:Location'
                m['room_name'] = room_name 
                self.player_to_curr_room[player] = room_name
                print('%s moved to %s' %(player, room_name))
        
        ## If this is a message type we append room name to
        if mtype in self.typeToLocationFields:
            fields = self.typeToLocationFields[mtype]
            x, z = m[fields[0]], m[fields[1]]
            m['room_name'] = self.getRoom(x,z)

        if m['mission_timer'] == 'Mission Timer not initialized.':
            m['mission_timer'] = '15 : 0'
        
        smallMsg = {k:m[k] for k in m.keys() if k in self.generalFields + self.typeToFields[m['sub_type']]}
        self.messages.append(smallMsg)
        
        ## For every derived feature, ask it to process this message
        for derived in self.derivedFeatures:
            derived.processMsg(smallMsg)
        
    def get_fov_blocks(self,m,jtxt):
        victim_arr = []
        obs = json.loads(jtxt)
        data = obs[u'data']
        blocks = data['blocks']
        for b in blocks:
            vloc = b['location']
            vx = vloc[0]
            vz = vloc[2]
            vrm = ''
            # first check if victim block is in same room as player:
            for v in self.victims:
                if v.x == vx and v.z == vz:
                    vrm = v.room
                    vvcolor = v.color # extra check that block_type & victim color match
            if vrm == m['room_name']: # only add if victim in player room
                if b['type'] == 'block_victim_1' and vvcolor == GREEN_STR:
                    vcolor = GREEN_STR
                elif b['type'] == 'block_victim_2' and vvcolor == GOLD_STR:
                    vcolor = GOLD_STR
                victim_arr.append(vcolor)
        m.update({'victim_list':victim_arr})
        return victim_arr

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

    def getRoom(self, x, z):        
        epsilon = 1-1e-5
        relaxed = [r for r in self.rooms if r.in_room(x,z,epsilon)]
        if len(relaxed) == 1:
            return relaxed[0].name
        
        if len(relaxed) == 0:
            print('ERROR relaxed %f %f not in any rooms' %(x, z))
            return ''
        
        if len(relaxed) > 1:
            matches = [r for r in self.rooms if r.in_room(x,z)]
        if len(matches) == 1:
            print('second time worked')
            return matches[0].name
        
        print('ERROR relaxed in multiple, strict in %f %f in %d rooms' %(x, z, len(matches)))
        return ''


    def writeToJson(self, inJsonFileName, psychsimdir):
        outname = inJsonFileName.split('/')
        outfile = psychsimdir+'/'+outname[len(outname)-1]+'.json'
        print("writing to "+outfile)
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

if __name__ == "__main__":
    argDict = {}
    for i in range(1, len(sys.argv)):
        if sys.argv[i] == '--verbose':
            k = '--verbose'
            v = True
        elif sys.argv[i] == '--help':
            k = '--help'
            v = True
        elif i+1<len(sys.argv):
            k = sys.argv[i]
            v = sys.argv[i+1]
        argDict[k] = v
        
    msgs, _ = getMessages(argDict)
    for m in msgs:
        print(str(m))
        
