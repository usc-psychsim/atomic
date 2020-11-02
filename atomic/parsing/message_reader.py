#!/usr/bin/env python3

# read necessary portions of message buffer for psychsim
# can call on entire file or request latest event

from builtins import range
import os
import sys
import time
import functools
import json
import math
import csv
print = functools.partial(print, flush=True)

class room(object):
    def __init__(self, name, x0, z0, x1, z1):
        self.name = name

        self.xrange = range(x0,x1+1) 
        self.zrange = range(z0,z1+1)

    def in_room(self, _x, _z):
        if _x in self.xrange and _z in self.zrange:
            return True   
        else:
            return False

class door(object):
    def __init__(self, x0, z0, x1, z1, room1, room2):
        self.room1 = room1
        self.room2 = room2
        self.x0 = x0
        self.x1 = x1
        self.z0 = z0
        self.z1 = z1
        self.center = [x0,z0] # default to corner
        self.xrange = range(x0,x1+1)
        self.zrange = range(z0,z1+1)
        # calc center half the span of x & z 
        xlen = math.floor(abs(x0 - x1)/2)
        zlen = math.floor(abs(z0 - z1)/2)
        self.center = [x0+xlen,z0+zlen]

    def at_this_door(self, _x, _z):
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
        self.linenum = 0

class msgreader(object):
    def __init__(self, fname, room_list, portal_list, latest=False):
        self.psychsim_tags = ['mission_timer', 'sub_type'] # maybe don't need here
        self.nmessages = 0
        self.rooms = []
        self.doors = [] # actually portals
        self.msg_types = ['Event:Triage', 'Event:Door', 'Event:Lever', 'Event:VictimsExpired', 'Mission:VictimList', 'Event:Beep', 'FoV','state']
        self.messages = []
        self.mission_running = False
        self.locations = []
        self.observations = []
        self.curr_room = ''
        self.rescues = 0
        self.playername = self.get_player(fname)
        if (room_list.endswith('.csv')):
            self.load_rooms(room_list)
        else:
            self.load_rooms_semantic(room_list)
        self.load_doors(portal_list)
        
    def get_player(self, msgfile):
        jsonfile = open(msgfile, 'rt')
        for line in jsonfile.readlines():
            if line.find('Triage') > -1:
                obs = json.loads(line)
                data = obs[u'data']
                playername = data['playername']
                break
        jsonfile.close()
        return playername

    # find closest portal (closest room may not be accessible)
    # then find the rooms that portal adjoins & select the one we're not already in
    def find_beep_room(self,x,z):
        best_dist = 99999
        agent_room = self.curr_room
        beep_room = 'null'
        didx = 0
        bestd = 0
        for r in self.rooms:
            if r.in_room(x,z):
                beep_room = r.name
        for d in self.doors:
            dx = d.center[0]
            dz = d.center[1]
            distance = math.sqrt(pow((dx-x),2) + pow((dz-z),2))
            if distance < best_dist:
                best_dist = distance
                bestd = didx
                # now choose whichever room not already in
                if agent_room == d.room1:
                    beep_room = d.room2
                else:
                    beep_room = d.room1
            didx += 1
        return beep_room

    def get_obs_timer(self,fmessage):
        obsnum = fmessage.mdict['observation']
        nobs = len(self.observations)
        oidx = nobs-1
        timer = ''
        while oidx >= 0:
            if obsnum == self.observations[oidx][0]: # we have a match
                timer = self.observations[oidx][1]
            oidx -= 1
        #return timer
        fmessage.mdict.update({'mission_timer':timer})
        
    # add to msgreader obj
    # TODO: add counter to know nlines btwn start/stop
    def add_all_messages(self,fname):
        message_arr = []
        jsonfile = open(fname, 'rt')
        nlines = 1 # start 1 so aligns with line num in file
        for line in jsonfile.readlines():
            # first filter messages before mission start & record observations
            if line.find("mission_victim_list") > -1:
                self.mission_running = True # count this as mission start, start will occur just after list
                self.add_message(line,nlines)
            elif line.find("mission_state\":\"Stop") > -1 or line.find('Mission Timer not initialized') > -1:
                self.mission_running = False
            elif line.find("paused\":true") > -1:
                self.mission_running = False
            elif line.find("paused\":false") > -1:
                self.mission_running = True
            elif line.find('observation_number') > -1 and self.mission_running:
                if self.mission_running:
                    self.add_observation(line,nlines) # also adds message if room change
            # now get actual messages
            elif line.find('data') > -1: # should check for types here, don't pass all?
                self.add_message(line,nlines)
            nlines += 1
        self.messages = sorted(self.messages, key = lambda i: (i.mdict['mission_timer']), reverse=True)
        jsonfile.close()

    # adds single message to msgreader.messages list
    def add_message(self,jtxt,linenum): 
        add_msg = True
        m = self.make_message(jtxt) # generates message, sets psychsim_tags
#        m.linenum = linenum
        if m.mtype in self.msg_types and self.mission_running:
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
                self.add_room(m.mdict)
                if self.playername != m.mdict['playername']: # ghost player, don't care abt so won't add msg
                    add_msg = False
            if m.mtype == 'Event:Lever':
                self.add_room(m.mdict) 
            elif m.mtype == 'Event:Door':
                self.add_door_rooms(m.mdict,m.mtype)
            elif m.mtype == 'Mission:VictimList':
                self.make_victims_msg(jtxt,m)
            elif m.mtype == 'Event:Beep':
                room_name = self.find_beep_room(int(m.mdict['beep_x']), int(m.mdict['beep_z']))
                del m.mdict['beep_x']
                del m.mdict['beep_z']
                m.mdict.update({'room_name':room_name})
                m.mdict.update({'playername':self.playername})
            elif m.mtype == 'FoV':
                self.get_obs_timer(m) # do at end??
                if jtxt.find('victim') == -1 or m.mdict['playername'] != self.playername or m.mdict['mission_timer'] == '':
                    add_msg = False  # no victims, ghost player or no matching state message, skip msg
                else:
                    del m.mdict['observation']
                    self.get_fov_blocks(m,jtxt)
            if add_msg:
                self.convert_mission_timer(m)
                self.messages.append(m)

    def convert_mission_timer(self,m):
        curr_timer = m.mdict['mission_timer']
        new_mt = curr_timer.replace(' ','')
        new_mt = new_mt.replace(':','.')
        m.mdict.update({'mission_timer':float(new_mt)})

    # OBS & STATE ARE SAME, CHECK ROOM HERE
    # this also generates a message if room has changed
    def add_observation(self,jtxt,nln):
        obs = json.loads(jtxt)
        # message = obs[u'msg']
        data = obs[u'data']
        obsnum = int(data['observation_number'])
        playername = data['name']
        if playername == self.playername: # only add if not ghost
            mtimer = data['mission_timer']
            tstamp = data['timestamp'].split('T')[1].split('.')[0]
            obsx = data['x']
            obsz = data['z']
            obsdict = {'x':obsx,'z':obsz}
            room_name = self.add_room_obs(obsdict)
            if room_name != self.curr_room and room_name != '':
                m = msg('state')
                m.mdict = {'sub_type':'Event:Location','playername':playername,'room_name':room_name,'mission_timer':mtimer}
                self.convert_mission_timer(m)
                self.messages.append(m)
                self.curr_room = room_name
            self.observations.append([obsnum,mtimer,nln,tstamp,obsx,obsz]) # add to obs even if is location change

    def get_fov_blocks(self,m,jtxt):
        victim_arr = []
        obs = json.loads(jtxt)
        data = obs[u'data']
        blocks = data['blocks']
        for b in blocks:
            if b['type'] == 'block_victim_1':
                victim_arr.append('green')
            elif b['type'] == 'block_victim_2':
                victim_arr.append('yellow')
        m.mdict.update({'victim_list':victim_arr})
      
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
                        vv.update({'block_type':'green'})
                    else:
                        vv.update({'block_type':'yellow'})
        for victim in victim_list_dicts:
            room_name = 'null'
            for (k,v) in victim.items():
                if k == 'x':
                    vx = v
                elif k == 'z':
                    vz = v
            for r in self.rooms:
                if r.in_room(vx,vz):
                    room_name = r.name
            del victim['x']
            del victim['y']
            del victim['z']
            victim.update({'room_name':room_name})
        vmsg.mdict.update({'mission_victim_list':victim_list_dicts})
        vmsg.mdict.update({'playername':self.playername})
        # del vmsg.mdict['mission_timer']

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
        del msgdict[xkey]
        del msgdict[zkey]
        msgdict.update({'room_name':room_name})

    def add_room_obs(self, msgdict):
        x = 0
        z = 0
        xkey = ''
        zkey = ''
        room_name = ''
        x = float(round(msgdict['x']))
        z = float(round(msgdict['z']))
        for r in self.rooms:
            if r.in_room(x,z):
                room_name = r.name
        return room_name

    def add_door_rooms(self, msgdict, msg_type):
        doors_found = 0
        x = 0
        z = 0
        for (k,v) in msgdict.items():
            if k.find('_x') > -1:
                x = float(v)
            elif k.find('_z') > -1:
                z = int(v)
        for d in self.doors:
            if d.at_this_door(x,z):
                msgdict.update({'room1':d.room1})
                msgdict.update({'room2':d.room2})
                del msgdict['door_x'] # no longer needed once have ajoining rooms
                del msgdict['door_z']
                doors_found += 1
        # if we did not find this door's adjoining rooms, it's not a portal, still need to update its fields
        if doors_found == 0:
            msgdict.update({'room1':'null'})
            msgdict.update({'room2':'null'})
            del msgdict['door_x'] # no longer needed once have ajoining rooms
            del msgdict['door_z']
        
    # check what kind of event to determine tags to look for
    # if doesn't match any, we don't care about it so
    # message won't be processed
    def make_message(self,jtxt):
        m = msg('NONE')
        self.psychsim_tags = ['sub_type', 'mission_timer', 'playername']
        if jtxt.find('Event:Triage') > -1:
            self.psychsim_tags += ['triage_state', 'color', 'victim_x', 'victim_z']
            m.mtype = 'Event:Triage'
            if jtxt.find('SUCCESS') > -1:
                self.rescues += 1
        elif jtxt.find('Event:Door') > -1:
            self.psychsim_tags += ['open', 'door_x', 'door_z', 'room1', 'room2']
            m.mtype = 'Event:Door'
        elif jtxt.find('Event:Lever') > -1:
            self.psychsim_tags += ['powered', 'lever_x', 'lever_z']
            m.mtype = 'Event:Lever'
        elif jtxt.find('Event:VictimsExpired') > -1:
            m.mtype = 'Event:VictimsExpired'
            m.mdict.update({'playername':self.playername})
        elif jtxt.find('Mission:VictimList') > -1:
            self.psychsim_tags += ['mission_victim_list', 'room_name', 'message_type']
            m.mtype = 'Mission:VictimList'
        elif jtxt.find('Event:Beep') > -1:
            self.psychsim_tags += ['message', 'room_name', 'beep_x', 'beep_z']
            m.mtype = 'Event:Beep'
        elif jtxt.find('FoV') > -1:
            self.psychsim_tags += ['observation']
            m.mtype = 'FoV'
        elif jtxt.find("sub_type\":\"state") > -1: # DON'T NEED?
            self.psychsim_tags += ['x','z']
            m.mtype = 'state'
        return m

    # this will be updated to use mmap, for now reads all lines
    # returns empty dict if no new messages
    def get_latest_message(self, fname):
        jsonfile = open(fname, 'rt')
        laststr = ''
        msgcnt = 0
        lastmsg = {}
        for line in jsonfile.readlines():
            laststr = line
            msgcnt += 1
        jsonfile.close()
        if msgcnt > self.nmessages and laststr.find('data') > -1:
            lastmsg = self.parse_message(laststr)
        return lastmsg

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
                    v = victim(int(row[1]), int(row[2]), int(row[3]), int(row[5]))
                    self.victims.append(v)
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

    def load_doors(self, fname):
        with open(fname) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    line_count += 1
                else:
                    d = door(int(row[1]), int(row[2]), int(row[3]), int(row[4]), str(row[5]), str(row[6]))
                    self.doors.append(d)
                    line_count += 1

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

# MAIN
# create reader object then use to read all messages in trial file -- returns array of dictionaries
msgfile = ''
room_list = ''
portal_list = ''
victim_list = ''
print_rescues = False
multitrial = False
msgdir = ''

# allow user to specify inputs
if len(sys.argv) > 1:
    argcnt = 0
    for a in sys.argv:
        if a == '--rescues':
            print_rescues = True
        elif a == '--msgfile':
            msgfile = sys.argv[argcnt+1] 
        elif a == '--roomfile':
            room_list = sys.argv[argcnt+1]
        elif a == '--multitrial':
            multitrial = True
            msgdir = sys.argv[argcnt+1]
        elif a == '--portalfile':
            portal_list = sys.argv[argcnt+1]
        elif a == '--victimfile':
            victim_list = sys.argv[argcnt+1]

        elif a == '--help':
            print("USAGE: message_reader.py --rescues --msgfile <trial messages file> --roomfile <.json or .csv> --portalfile <list of portals> --victimfile <list of victims .csv> --multitrial <directory with message files>")
        argcnt += 1

# if ONLY getting number of rescues
if print_rescues:
    if multitrial:
        if msgdir == '':
            print("ERROR: must provide --msgdir <directory>")
        else:
            file_arr = os.listdir(msgdir)
            for f in file_arr:
                full_path = os.path.join(msgdir,f)
                if os.path.isfile(full_path):
                    print(full_path)
                    get_rescues(full_path)
    else: # just want rescues for single file
        if msgfile == '':
            print("ERROR: must provide --msgfile <filename>")
        else:
            get_rescues(msgfile)
        
else:
# USE DEFAULTS when files not specified
# maybe get victim list from mission_victim_list instead??
    if msgfile == '': # not entered on cmdline
        msgfile = '/home/skenny/usc/asist/data/study-1_2020.08_TrialMessages_CondBtwn-NoTriageNoSignal_CondWin-FalconEasy-StaticMap_Trial-120_Team-na_Member-51_Vers-1.metadata'
    if room_list == '':
        room_list = '/home/skenny/usc/asist/data/ASIST_FalconMap_Rooms_v1.1_OCN.csv'
    if portal_list == '':
        portal_list = '/home/skenny/usc/asist/data/ASIST_FalconMap_Portals_v1.1_OCN.csv'
    if victim_list == '': 
        victim_list = '/home/skenny/usc/asist/data/ASIST_FalconMap_Easy_Victims_v1.1_OCN_VU.csv'
    reader = msgreader(msgfile, room_list, portal_list, True)
    reader.add_all_messages(msgfile)
    # print all the messages
    for m in reader.messages:
        print(str(m.mdict))
