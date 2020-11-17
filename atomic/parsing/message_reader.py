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
import subprocess
import time
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
    def __init__(self, fname, room_list, portal_list, victim_list, fov_file, verbose=False):
        self.psychsim_tags = ['mission_timer', 'sub_type'] # maybe don't need here
        self.nmessages = 0
        self.rooms = []
        self.doors = [] # actually portals
        self.victims = []
        self.victimcoords = []
        self.victim_rooms = []
        self.fov_messages = []
        self.fov_file = fov_file
        if self.fov_file == '': # no fov file, will use fov messages in metadata
            self.msg_types = ['Event:Triage', 'Event:Door', 'Event:Lever', 'Event:VictimsExpired', 'Mission:VictimList', 'Event:Beep', 'FoV','state']
        else:
            self.msg_types = ['Event:Triage', 'Event:Door', 'Event:Lever', 'Event:VictimsExpired', 'Mission:VictimList', 'Event:Beep','state']
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
        self.load_doors(portal_list)
        #self.load_victims(victim_list)
        
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
    # if no victim there just find closest victim
    def find_beep_room(self,m):
        x = int(m.mdict['beep_x'])
        z = int(m.mdict['beep_z'])
        best_dist = 99999
        victim_room = ''
        agent_room = self.curr_room
        vidx = 0
        bestd = 0
        didx = 0
        bestd = 0

        # first check if player has changed rooms on this move (in case beep msg preceeds state observation msg)
        for r in self.rooms:
            if r.in_room(x,z) and self.curr_room != r.name: # agent moved, need to add event:location message
              self.make_location_event(m.mdict['mission_timer'],r.name,m.mdict['timestamp']) # adds msg, changes agent room
              agent_room = r.name
              break

        for d in self.doors: # find closest portal
            dx = d.center[0]
            dz = d.center[1]
            distance = math.sqrt(pow((dx-x),2) + pow((dz-z),2))
            if distance < best_dist:
                best_dist = distance
                bestd = didx
                # now choose whichever room not already in
                if agent_room == d.room1:
                    victim_room = d.room2
                else:
                    victim_room = d.room1
            didx += 1
        if victim_room in self.victim_rooms: 
            return victim_room
        else: # can't find in adjacent room so get whichever victim closest
            best_dist = 99999
            for v in self.victims:
                if v.room != agent_room: # can't be room player already in
                    distance = math.sqrt(pow((v.x-x),2) + pow((v.z-z),2))
                    if distance < best_dist:
                        best_dist = distance
                        bestv = vidx
                        victim_room = v.room
                vidx += 1
        return victim_room

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
        #del fmessage.mdict['x']
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
            
        if self.fov_file != '': #have fov file load from there
            self.load_fovs(fov_file)
            for fmsg in self.fov_messages:
                self.get_obs_timer(fmsg)
                # has matching obs AND is in a room that has a victim
                if fmsg.mdict['mission_timer'] != '' and fmsg.mdict['room_name'] in self.victim_rooms:
                    if not self.verbose:
                        del fmsg.mdict['x']
                        del fmsg.mdict['z']
                        del fmsg.mdict['observation']
                        del fmsg.mdict['room_name']
                    self.messages.append(fmsg)
            self.messages = sorted(self.messages, key = lambda i: (i.mdict['timestamp']))
        jsonfile.close()

    # adds single message to msgreader.messages list
    def add_message(self,jtxt,linenum): 
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
                    m.mdict.update({'color':'Gold'})
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
                room_name = self.find_beep_room(m)
                if not self.verbose:
                    del m.mdict['beep_x']
                    del m.mdict['beep_z']
                m.mdict.update({'room_name':room_name})
                m.mdict.update({'playername':self.playername})
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
    def add_observation(self,jtxt,nln):
        obs = json.loads(jtxt)
        # message = obs[u'msg']
        data = obs[u'data']
        obsnum = int(data['observation_number'])
        playername = data['name']
        if playername == self.playername: # only add if not ghost
            mtimer = data['mission_timer']
            tstamp = data['timestamp'].split('T')[1].split('.')[0] # don't need?
            realtime = data['timestamp']
            obsx = data['x']
            obsz = data['z']
            obsdict = {'x':obsx,'z':obsz}
            room_name = self.add_room_obs(obsdict)
            if room_name != self.curr_room and room_name != '':
                m = msg('state')
                m.mdict = {'sub_type':'Event:Location','playername':playername,'room_name':room_name,'mission_timer':mtimer,'timestamp':realtime}
                self.messages.append(m)
                self.curr_room = room_name
            self.observations.append([obsnum,mtimer,nln,realtime,obsx,obsz]) # add to obs even if is location change

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
                if b['type'] == 'block_victim_1' and vvcolor == 'Green':
                    if self.verbose:
                        vcolor = 'Green '+str(vloc)+' '+vrm
                    else:
                        vcolor = 'Green'
                    victim_arr.append(vcolor)
                elif b['type'] == 'block_victim_2' and vvcolor == 'Gold':
                    if self.verbose:
                        vcolor = 'Gold '+str(vloc)+' '+vrm
                    else:
                        vcolor = 'Gold'
                    victim_arr.append(vcolor)
        m.mdict.update({'victim_list':victim_arr})
        return victim_arr

    def get_fov_blocks_nope(self,m,jtxt):
        victim_arr = []
        obs = json.loads(jtxt)
        data = obs[u'data']
        blocks = data['blocks']
        for b in blocks:
            btype = str(b['type']).strip()
            if btype == 'block_victim_2' or btype == 'block_victim_1':
                vloc = b['location']
                vx = vloc[0]
                vz = vloc[2]
                greenstr = 'Green'
                goldstr = 'Gold'
                if self.verbose:
                    greenstr = 'Green '+str(vloc)
                    goldstr = 'Gold '+str(vloc)
            if btype == 'block_victim_1':
                vcolor = 'Green'
                victim_arr.append(greenstr)
            elif btype == 'block_victim_2':
                vcolor = 'Gold'
                victim_arr.append(goldstr)
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
                        vv.update({'block_type':'Green'})
                    else:
                        vv.update({'block_type':'Gold'})
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
        self.psychsim_tags = ['sub_type', 'mission_timer', 'playername', 'timestamp']
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

def proc_gc_files(gcdir, prefix, tmpdir='/var/tmp/'):
    file_list = tmpdir+'/metafiles.txt'
    cmd = 'gsutil ls gs://studies.aptima.com/'+gcdir+'/'+prefix+'*metadata > '+file_list
    print("getting file list from:: "+cmd)
    subprocess.getstatusoutput(cmd)
    metafile = open(file_list, 'r')
    cpcnt = 0 # for testing only do first 2 files
    for line in metafile.readlines():
        fname = line.split(gcdir+'/')[1].strip()
        msgfile = tmpdir+fname
        outfile = tmpdir+fname+'.json'
        cmd = 'gsutil cp '+line.strip()+' '+tmpdir # fetch file
        print("processing file:: "+fname)
        subprocess.getstatusoutput(cmd)
        reader = msgreader(msgfile, room_list, portal_list, victim_list, fov_file)
        reader.add_all_messages(msgfile)
        # write msgs to file
        msgout = open(outfile,'w')
        for m in reader.messages:
            del m.mdict['timestamp']
            json.dump(m.mdict,msgout)
            msgout.write('\n')
        msgout.close()
        subprocess.getstatusoutput('rm '+msgfile)
        cpcnt += 1
    metafile.close()


# MAIN
# create reader object then use to read all messages in trial file -- returns array of dictionaries
def getMessages(args):    
    ## Defaults
    msgfile = '../data/HSRData_TrialMessages_CondBtwn-NoTriageNoSignal_CondWin-FalconEasy-StaticMap_Trial-120_Team-na_Member-51_Vers-3.metadata'
    room_list = '../../maps/Falcon_EMH_PsychSim/ASIST_FalconMap_Rooms_v1.1_EMH_OCN_VU.csv'
    portal_list = '../../maps/Falcon_EMH_PsychSim/ASIST_FalconMap_Portals_v1.1_OCN.csv'
    victim_list = '../../maps/Falcon_EMH_PsychSim/ASIST_FalconMap_Easy_Victims_v1.1_OCN_VU.csv'
    fov_file = ''
    msgdir = ''
    
    psychsimdir = '/var/tmp/'    
    gcdir = 'study-1_2020.08'
    gcprefix = ''
    
    files_from_gc = False
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
        elif a == '--portalfile':
            portal_list = args[a]
        elif a == '--victimfile': # no longer allow victim file?
            victim_list = args[a]
        elif a == '--fovfile':
            fov_file = args[a]
        elif a == '--gcprefix':
            gcprefix = args[a]
            files_from_gc = True
        elif a == '--psychsimdir':
            psychsimdir = args[a]
            files_from_gc = True
        elif a == '--verbose':
            verbose = True
        elif a == '--help':
            print("USAGE:")
            print('--home: specify atomic home')
            print("--rescues: count number of rescues in a message file (or for all message files in a directory specified with --multitrial")
            print("--msgfile <trial messages file>")
            print("--roomfile <.json or .csv list of rooms>")
            print("--portalfile <list of portals>")
            print("--victimfile <list of victims .csv>")
            print("--multitrial <directory with message files to be processed>")
            print("--verbose : will provide extra info for each message, e.g. x/z coords") 
            print("--gcprefix <prefix>: prefix for files you want to pull from the google cloud in studies.aptima.com/study-1_2020.08")
            print("--psychsimdir <directory to store processed message files>")
            exit()

    # If reading a directory and writing to files
    if files_from_gc:
        if gcdir == '':
            gcdir = 'HSRData_TrialMessages'
        proc_gc_files(gcdir,gcprefix, psychsimdir+"/")
        return None
    
    # if ONLY getting number of rescues
    if print_rescues:
        if multitrial:
            if msgdir == '':
                print("ERROR: must provide message directory --multitrial <directory>")
                exit()
            file_arr = os.listdir(msgdir)
            for f in file_arr:
                full_path = os.path.join(msgdir,f)
                if os.path.isfile(full_path):
                    print(full_path)
                    get_rescues(full_path)
        else: # just want rescues for single file
            if msgfile == '':
                print("ERROR: must provide --msgfile <filename>")
                exit()
            get_rescues(msgfile)
        return None
    
    # If returning a list of dictionaries
    reader = msgreader(msgfile, room_list, portal_list, victim_list, fov_file, verbose)
    reader.add_all_messages(msgfile)
    for m in reader.messages:
        if not reader.verbose:
            del m.mdict['timestamp']
    allMs = [m.mdict for m in reader.messages]
    return allMs

if __name__ == "__main__":
    argDict = {}
    for i in range(1, len(sys.argv), 2):
        if sys.argv[i] == '--verbose':
            k = '--verbose'
            v = True
        elif sys.argv[i] == '--rescues':
            k = '--rescues'
            v = True
        else:
            k = sys.argv[i]
            v = sys.argv[i+1]
        argDict[k] = v
        
    msgs = getMessages(argDict)
