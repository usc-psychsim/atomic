#!/usr/bin/env python3

# read necessary portions of message buffer for psychsim
# can call on entire file or request latest event
# adapted from original message_reader to process engineered subjects data/AI/non-human which don't have triage event

from builtins import range
import os
import sys
import time
import functools
import json
import math
import csv
import subprocess
import time
print = functools.partial(print, flush=True)
from atomic.definitions import GOLD_STR, GREEN_STR

class room(object):
    def __init__(self, name, x0, z0, x1, z1):
        self.name = name
        # coords in new file using top rt corner, bottom left (unlike previous) so need to adjust for calculating range
        if x0 < x1:
            self.xrange = range(x0,x1+1)
        else:
            self.xrange = range(x1+1,x0)
        if z0 < z1:
            self.zrange = range(z0,z1+1)
        else:
            self.zrange = range(z1+1,z0)
        self.victims = []

    def in_room(self, _x, _z):
        if _x in self.xrange and _z in self.zrange:
            return True   
        else:
            return False

class victim(object):
    def __init__(self, loc, color, x, z):
        self.room = loc
        self.color = color
        self.x = x
        self.z = z

class msg(object):
    def __init__(self, msg_type):
        self.mtype = msg_type
        self.mdict = {}

class msgreader(object):
    def __init__(self, fname, room_list, verbose=False):
        self.psychsim_tags = ['mission_timer', 'sub_type'] # maybe don't need here
        self.nmessages = 0
        self.rooms = []
        self.victims = []
        self.victimcoords = []
        self.victim_rooms = []
        self.fov_messages = []
        self.msg_types = ['Event:Triage', 'Event:VictimsExpired', 'Mission:VictimList', 'state','FoV', \
                          'Event:ToolUsed', 'Event:RoleSelected', 'Event:ToolDepleted', 'Event:VictimPlaced', 'Event:VictimPickedUp', \
                          'Event:RubbleDestroyed', 'Event:ItemEquipped']
        self.messages = []
        self.mission_running = False
        self.locations = []
        self.observations = []
        self.curr_room = ''
        self.rescues = 0
        self.verbose = verbose
        self.playername = self.get_player(fname)
        if (room_list.endswith('.csv')):
            self.load_rooms(room_list)
        else:
            self.load_rooms_semantic(room_list)

    def load_fovs(self, fname):
        victim_arr = []
        jsonfile = open(fname, 'rt')
        for line in jsonfile.readlines():
            if line.find('victim') > -1:
                obs = json.loads(line)
                data = obs[u'data']
                playername = data['playername']    # maybe don't need, assume no ghosts?
                obsnum = data['observation']
                blocks = data['blocks']
                fmsg = msg('FoV')
                fmsg.mdict.update({'sub_type':'FoV','playername':playername, 'observation':obsnum})
                victim_arr = self.get_fov_blocks_f(fmsg, line)
                if len(victim_arr) > 0:
                    fmsg.mdict.update({'victim_list':victim_arr})
                    self.fov_messages.append(fmsg)
                
    # if there are multiple players use triage to get 'real' one, otherwise just grab first playername found
    def get_player(self, msgfile):
        playername = 'NONE'
        jsonfile = open(msgfile, 'rt')
        for line in jsonfile.readlines():
            if line.find('Triage') > -1:
                obs = json.loads(line)
                data = obs[u'data']
                playername = data['playername']
                break
        jsonfile.close()
        if playername == 'NONE': #no triage just get first playernane
            jsonfile = open(msgfile, 'rt')
            for line in jsonfile.readlines():
                if line.find('playername') > -1:
                    obs = json.loads(line)
                    data = obs[u'data']
                    playername = data['playername']
                    break
            jsonfile.close()
        return playername

    def get_room_from_name(self,name):
        rm = ''
        for r in self.rooms:
            if name == r.name:
                rm = r
                break
        return rm

    def get_obs_timer(self,fmessage):
        obsnum = fmessage.mdict['observation']
        nobs = len(self.observations)
        oidx = nobs-1
        timer = ''
        obsx = 0
        obsz = 0
        obsroom = ''
        ts = ''
        while oidx >= 0:
            if obsnum == self.observations[oidx][0]: # we have a match
                timer = self.observations[oidx][1]
                obsx = self.observations[oidx][4]
                obsz = self.observations[oidx][5]
                ts = self.observations[oidx][3]
            oidx -= 1
        fmessage.mdict.update({'mission_timer':timer, 'x':obsx, 'z':obsz, 'timestamp':ts})
        r = self.add_room_obs(fmessage.mdict)
        fmessage.mdict.update({'room_name':r})
        # del fmessage.mdict['x']
        # del fmessage.mdict['z']

    def get_obs_timer_ts(self,fmessage):
        obsnum = fmessage.mdict['observation'] #not working use timestamp instead?
        full_timestamp = fmessage.mdict['timestamp']
        tstamp = fmessage.mdict['timestamp'].split('T')[1].split('.')[0]
        nobs = len(self.observations)
        timer = ''
        obsx = 0
        obsz = 0
        for obs in self.observations:
            if tstamp == obs[3]: # we have a match
                timer = obs[1]
                obsx = obs[4]
                obsz = obs[5]
        if timer == '': # could not match, use last obs (maybe do by default? fovs collected more frequently)
            timer = self.observations[nobs-1][1]
        fmessage.mdict.update({'x':obsx, 'z':obsz})
        r = self.add_room_obs(fmessage.mdict)
        fmessage.mdict.update({'room_name':r})
        fmessage.mdict.update({'mission_timer':timer})

    # add to msgreader obj
    def add_all_messages(self,fname):
        jsonfile = open(fname, 'rt')
        for line in jsonfile.readlines():
            # first filter messages before mission start & record observations
            if line.find("mission_victim_list") > -1:
                self.mission_running = True # count this as mission start, start will occur just after list
                self.add_message(line)
            elif line.find("mission_state\":\"Stop") > -1: # or line.find('Mission Timer not initialized') > -1:
                self.mission_running = False
            elif line.find("paused\":true") > -1:
                self.mission_running = False
            elif line.find("paused\":false") > -1:
                self.mission_running = True
            elif line.find('observation_number') > -1 and self.mission_running:
                self.add_observation(line) # also adds message if room change
            # now get actual messages
            elif line.find('data') > -1: # should check for types here, don't pass all?
                self.add_message(line)
            
        jsonfile.close()

    # adds single message to msgreader.messages list
    def add_message(self,jtxt): 
        add_msg = True
        m = self.make_message(jtxt) # generates message, sets psychsim_tags
        if m.mtype in self.msg_types and (self.mission_running or m.mtype == 'FoV'): # mission not running for many fovs in .metadata due to timing
            obs = json.loads(jtxt)
            message = obs[u'msg']
            data = obs[u'data']
            m.mdict = {}
            for (k,v) in data.items():
                if k in self.psychsim_tags:
                    m.mdict[k] = v
            for (k,v) in message.items():
                if k in self.psychsim_tags:
                    m.mdict[k] = v
            if m.mtype in ['Event:Triage']:
                if m.mdict['color'] == 'Yellow':
                    m.mdict.update({'color':GOLD_STR})
                self.add_room(m.mdict)
                if self.playername != m.mdict['playername']: # ghost player, don't care abt so won't add msg
                    add_msg = False
            if m.mtype == 'Event:Lever':
                self.add_room(m.mdict) 
            if m.mtype == 'Event:VictimPickedUp':
                self.add_room(m.mdict) 
            if m.mtype == 'Event:VictimPlaced':
                self.add_room(m.mdict) 
            if m.mtype == 'Event:RubbleDestroyed':
                self.add_room(m.mdict) 
            elif m.mtype == 'Event:ToolUsed': # not sure why commented out?? don't need room?
                self.add_room(m.mdict)
            elif m.mtype == 'Event:location':
                self.add_room(m.mdict) # possibly can replace obs?
                add_msg = False # won't add here, will be added in add_room. TODO: keep tally make sure all end up added? 
            elif m.mtype == 'Mission:VictimList':
                self.make_victims_msg(jtxt,m)
                self.add_victims_to_rooms()
            elif m.mtype == 'FoV':
                victim_arr = []
                self.get_obs_timer(m) # do at end??
                victim_arr = self.get_fov_blocks(m, jtxt)
                if len(victim_arr) == 0 or m.mdict['playername'] != self.playername or m.mdict['mission_timer'] == '' or m.mdict['room_name'] not in self.victim_rooms:
                    add_msg = False  # no victims, ghost player or no matching state message/was paused, skip msg
                else:
                    m.mdict.update({'victim_list':victim_arr})          
                if not self.verbose:
                    del m.mdict['observation']
                    del m.mdict['x']
                    del m.mdict['z']
                    del m.mdict['room_name']
            if add_msg:
                self.messages.append(m)

    # OBS & STATE ARE SAME, CHECK ROOM HERE
    # this also generates a message if room has changed
    # only used for getting timer of fov's
    def add_observation(self,jtxt):
        obs = json.loads(jtxt)
        # message = obs[u'msg']
        data = obs[u'data']
        if obs['msg']['sub_type'] not in self.msg_types:
            return
        playername = data['playername']
        if playername == self.playername: # only add if not ghost
            obsx = data['x']
            obsz = data['z']
            obsdict = {'x':obsx,'z':obsz}
            self.add_room_obs(obsdict)
            # SKIP when no fov's, otherwise generates unnecessary location message??
            #if room_name != self.curr_room and room_name != '':
             #   m = msg('state')
             #   m.mdict = {'sub_type':'Event:Location','playername':playername,'room_name':room_name,'mission_timer':mtimer,'timestamp':realtime}
             #   self.messages.append(m)
             #   self.curr_room = room_name
            #self.observations.append([obsnum,mtimer,nln,realtime,obsx,obsz]) # add to obs even if is location change

    def make_location_event(self,mtimer, room_name, tstamp): # generates & adds message
        m = msg('state')
        m.mdict = {'sub_type':'Event:Location','playername':self.playername,'room_name':room_name,'mission_timer':mtimer, 'timestamp':tstamp}
        self.messages.append(m)
        self.curr_room = room_name

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
            if vrm == m.mdict['room_name']: # only add if victim in player room
                if b['type'] == 'block_victim_1' and vvcolor == GREEN_STR:
                    if self.verbose:
                        vcolor = GREEN_STR+str(vloc)+' '+vrm
                    else:
                        vcolor = GREEN_STR
                    victim_arr.append(vcolor)
                elif b['type'] == 'block_victim_2' and vvcolor == GOLD_STR:
                    if self.verbose:
                        vcolor = GOLD_STR +str(vloc)+' '+vrm
                    else:
                        vcolor = GOLD_STR
                    victim_arr.append(vcolor)
        m.mdict.update({'victim_list':victim_arr})
        return victim_arr

    def make_victims_msg(self,line,vmsg):
        psychsim_tags = ['sub_type','message_type', 'mission_victim_list']
        victim_list_dicts = []
        obs = json.loads(line)
        header = obs[u'header']
        msg = obs[u'msg']
        victims = obs[u'data']
        for (k,v) in msg.items():
            if k in psychsim_tags:
                vmsg.mdict.update({k:v})
        for (k,v) in header.items():
            if k in psychsim_tags:
                vmsg.mdict.update({k:v})
        for (k,v) in victims.items():
            if k == 'mission_victim_list':
                victim_list_dicts = v
                for vv in victim_list_dicts:
                    blktype = vv['block_type']
                    if blktype == 'block_victim_1':
                        vv.update({'block_type':GREEN_STR})
                    else:
                        vv.update({'block_type':GOLD_STR})
        for v in victim_list_dicts:
            room_name = 'null'
            for (k,val) in v.items():
                if k == 'x':
                    vx = val
                elif k == 'z':
                    vz = val
            for r in self.rooms:
                if r.in_room(vx,vz):
                    room_name = r.name
            del v['y']
            v.update({'room_name':room_name})
            if room_name not in self.victim_rooms:
                self.victim_rooms.append(room_name)
            newvic = victim(room_name,v['block_type'], v['x'], v['z'])
            self.victims.append(newvic)
            if not self.verbose:
                del v['x']
                del v['z']
        vmsg.mdict.update({'mission_victim_list':victim_list_dicts})
        vmsg.mdict.update({'playername':self.playername})

    # adds which room event is occurring in 
    def add_room(self, msgdict):
        x = 0
        z = 0
        xkey = ''
        zkey = ''
        room_name = ''
        for (k,v) in msgdict.items():
            if k.find('_x') > -1:
                x = float(v)
                xkey = k
            elif k.find('_z') > -1:
                z = int(v)
                zkey = k
        for r in self.rooms:
            if r.in_room(x,z):
                room_name = r.name
        if not self.verbose:
            del msgdict[xkey]
            del msgdict[zkey]
        msgdict.update({'room_name':room_name})
        if self.curr_room != room_name:
            self.make_location_event(msgdict['mission_timer'], room_name, msgdict['timestamp'])
            self.curr_room = room_name

    def add_room_obs(self, msgdict):
        room_name = ''
        x = float(round(msgdict['x']))
        z = float(round(msgdict['z']))
        for r in self.rooms:
            if r.in_room(x,z):
                room_name = r.name
        return room_name

    # check what kind of event to determine tags to look for
    # if doesn't match any, we don't care about it so
    # message won't be processed
    def make_message(self,jtxt):
        m = msg('NONE')
        self.psychsim_tags = ['sub_type', 'mission_timer', 'playername', 'timestamp']
        if jtxt.find('Event:Triage') > -1:
            self.psychsim_tags += ['triage_state', 'color', 'victim_x', 'victim_z']
            m.mtype = 'Event:Triage'
            if jtxt.find('SUCCESS') > -1:
                self.rescues += 1
        elif jtxt.find('Event:ToolUsed') > -1:
            self.psychsim_tags += ['tool_type', 'durability', 'target_block_type', 'target_block_x', 'target_block_z']
            m.mtype = 'Event:ToolUsed'
        elif jtxt.find('Event:RoleSelected') > -1:
            self.psychsim_tags += ['new_role', 'prev_role']
            m.mtype = 'Event:RoleSelected'
        elif jtxt.find('Event:ToolDepleted') > -1:
            self.psychsim_tags += ['tool_type']
            m.mtype = 'Event:ToolDepleted'
        elif jtxt.find('Event:VictimPickedUp') > -1:
            self.psychsim_tags += ['color', 'victim_x', 'victim_z']
            m.mtype = 'Event:VictimPickedUp'
        elif jtxt.find('Event:VictimPlaced') > -1:
            self.psychsim_tags += ['color', 'victim_x', 'victim_z']
            m.mtype = 'Event:VictimPlaced'
        elif jtxt.find('Event:RubbleDestroyed') > -1:
            self.psychsim_tags += ['rubble_x','rubble_z']
            m.mtype = 'Event:RubbleDestroyed'
        elif jtxt.find('Event:ItemEquipped') > -1:
            self.psychsim_tags += ['equippeditemname']
            m.mtype = 'Event:ItemEquipped'
        elif jtxt.find('Event:Lever') > -1:
            self.psychsim_tags += ['powered', 'lever_x', 'lever_z']
            m.mtype = 'Event:Lever'
        elif jtxt.find('Event:VictimsExpired') > -1:
            m.mtype = 'Event:VictimsExpired'
            m.mdict.update({'playername':self.playername})
        elif jtxt.find('Mission:VictimList') > -1:
            self.psychsim_tags += ['mission_victim_list', 'room_name', 'message_type']
            m.mtype = 'Mission:VictimList'
        elif jtxt.find('FoV') > -1 and jtxt.find('victim') > -1:
            self.psychsim_tags += ['observation']
            m.mtype = 'FoV'
        elif jtxt.find("sub_type\":\"state") > -1: # DON'T NEED?
            self.psychsim_tags += ['x','z']
            m.mtype = 'state'
        return m

    def load_rooms(self, fname):
        with open(fname) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    line_count += 1
                else:
                    r = room(str(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4]))
                    self.rooms.append(r)
                    line_count += 1

    def load_victims(self, fname):
        with open(fname) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    line_count += 1
                else:
                    v = victim(row[1], row[2], int(row[3]), int(row[5]))
                    self.victims.append(v)
                    if v.room not in self.victim_rooms:
                        self.victim_rooms.append(v.room)
                    line_count += 1

    def load_rooms_semantic(self, fname):
        rfile = open(room_list, 'rt')
        rdict = json.load(rfile)
        rloc = rdict['locations']
        coords = ''
        rid = ''
        x0 = 0
        z0 = 0
        x1 = 0
        z1 = 0
        for r in rloc:
            try:
                coords = (r['bounds']['coordinates'])
            except:
                coords = ''
            if coords != '':
                rid = r['id']
                x0 = coords[0]['x']
                z0 = coords[0]['z']
                x1 = coords[1]['x']
                z1 = coords[1]['z']
                rm = room(rid, x0, z0, x1, z1)
                self.rooms.append(rm)
        rfile.close()
    
    def add_victims_to_rooms(self):
        for v in self.victims:
            for r in self.rooms:
                if v.room == r.name:
                    r.victims.append(v)



def get_rescues(msgfile):
    num_rescues = 0
    num_green = 0
    num_yellow = 0
    mfile = ''
    if msgfile == '':
        print("ERROR: must provide --msgfile <filename>")
    else:
        mfile = open(msgfile, 'rt')
        for line in mfile.readlines():
            if line.find('triage') > -1 and line.find('SUCCESS') > -1:
                num_rescues += 1
                if line.find('Yellow') > -1:
                    num_yellow += 1
                else:
                    num_green += 1
        mfile.close()
        print('green rescues : '+str(num_green))
        print('yellow rescues: '+str(num_yellow))
        print("TOTAL RESCUED : "+str(num_rescues))

def proc_msg_file(msgfile, room_list, psychsimdir):
    reader = msgreader(msgfile, room_list)
    reader.add_all_messages(msgfile)
    outname = msgfile.split('/')
    outfile = psychsimdir+'/'+outname[len(outname)-1]+'.json'
    print("writing to "+outfile)
    # write msgs to file
    msgout = open(outfile,'w')
    for m in reader.messages:
        del m.mdict['timestamp']
        json.dump(m.mdict,msgout)
        msgout.write('\n')
    msgout.close()

# MAIN
# create reader object then use to read all messages in trial file -- returns array of dictionaries
def getMessages(args):    
    ## Defaults
    #room_list = '../../maps/Falcon_EMH_PsychSim/ASIST_FalconMap_Rooms_v1.1_EMH_OCN_VU.csv'
    room_list = 'saturn_rooms.csv'
    
    ## Local directory containing multiple json files, if multitrial
    msgdir = ''
    ## Single json file, if not multitrial
    msgfile = '../data/pilot2/NotHSRData_TrialMessages_CondBtwn-IdvPlan_CondWin-MapA_Trial-T000276_Team-TM000002_Member-P000106-P000107-P000108_Vers-1.metadata'
    #msgfile = '../data/HSRData_TrialMessages_CondBtwn-NoTriageNoSignal_CondWin-FalconEasy-StaticMap_Trial-120_Team-na_Member-51_Vers-3.metadata'
    
    ## Output directory to store parsed content if parsing more than 1 file
    psychsimdir = '.'
   
    print_rescues = False
    multitrial = False
    verbose = False
    
    # Grab inputs, where available
    for a,val in args.items():            
        if a == '--rescues':
            print_rescues = True
        elif a == '--msgfile':
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
            print("--rescues: count number of rescues in a message file (or for all message files in a directory specified with --multitrial")
            print("--msgfile <trial messages file>")
            print("--roomfile <.json or .csv list of rooms>")
            print("--multitrial <directory with message files to be processed>")
            print("--verbose : will provide extra info for each message, e.g. x/z coords") 
            print("--psychsimdir <directory to store processed message files>")
            return

    # if ONLY getting number of rescues
    if print_rescues:
        if multitrial:
            if msgdir == '':
                print("ERROR: must provide message directory --multitrial <directory>")
                return
            file_arr = os.listdir(msgdir)
            for f in file_arr:
                full_path = os.path.join(msgdir,f)
                if os.path.isfile(full_path):
                    print(full_path)
                    get_rescues(full_path)
        else: # just want rescues for single file
            if msgfile == '':
                print("ERROR: must provide --msgfile <filename>")
                return
            get_rescues(msgfile)
        return None, None
    # if running message reader on a directory -- will write results to cwd
    elif multitrial: 
        if msgdir == '':
            print("ERROR: must provide message directory --multitrial <directory>")
            return
        file_arr = os.listdir(msgdir)
        filecnt = 1
        for f in file_arr:
            full_path = os.path.join(msgdir,f)
            if os.path.isfile(full_path):
                print("processing file "+str(filecnt)+" of "+str(len(file_arr))+" :: "+str(full_path))
                proc_msg_file(full_path, room_list, psychsimdir)
                filecnt += 1
        return

    # default to procesing single file, returning a list of dictionaries
    else:
        reader = msgreader(msgfile, room_list, verbose)
        reader.add_all_messages(msgfile)
        for m in reader.messages:
            if not reader.verbose:
                del m.mdict['timestamp']
            allMs = [m.mdict for m in reader.messages]
        return allMs, reader.playername

if __name__ == "__main__":
    argDict = {}
    for i in range(1, len(sys.argv)):
        if sys.argv[i] == '--verbose':
            k = '--verbose'
            v = True
        elif sys.argv[i] == '--rescues':
            k = '--rescues'
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
        
