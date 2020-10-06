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

        self.xrange = range(x0,x1) 
        self.zrange = range(z0,z1)

    def in_room(self, _x, _z):
        if _x in self.xrange and _z in self.zrange:
            return True   
        else:
            return False

class door(object):
    def __init__(self, x0, z0, x1, z1, room1, room2):
        self.room1 = room1
        self.room2 = room2
        self.xrange = range(x0,x1+1)
        self.zrange = range(z0,z1+1)

    def at_this_door(self, _x, _z):
        if _x in self.xrange and _z in self.zrange:
            return True
        else:
            return False

class msg(object):
    def __init__(self, msg_type):
        self.mtype = msg_type
        self.mdict = {}

class msgreader(object):
    def __init__(self, fname, latest=False):
        self.psychsim_tags = ['mission_timer', 'sub_type'] # maybe don't need here
        self.nmessages = 0
        self.rooms = []
        self.doors = []
        self.msg_types = ['Event:Triage', 'Event:Door']
        self.messages = []
        self.mission_running = False
        

    def get_all_messages(self,fname):
        message_arr = []
        jsonfile = open(fname, 'rt')
        for line in jsonfile.readlines():
            if line.find('data') > -1:
                m = self.parse_message(line)
                if (len(m.items()) > 0):
                    message_arr.append(m)
            jsonfile.close()
        return message_arr

    # add to msgreader obj
    # TODO: add counter to know nlines btwn start/stop
    def add_all_messages(self,fname):
        message_arr = []
        jsonfile = open(fname, 'rt')
        nlines = 0
        for line in jsonfile.readlines():
            if line.find("mission_state\":\"Start") > -1:
                self.mission_running = True
            elif line.find("mission_state\":\"Stop") > -1:
                self.mission_running = False
            elif line.find("paused\":true") > -1:
                self.mission_running = False
            elif line.find("paused\":false") > -1:
                self.mission_running = True
            elif line.find('data') > -1:
                self.add_message(line)
            nlines += 1
        jsonfile.close()

    # parses single message from line of json txt
    def parse_message(self,jtxt):
        msg_type = self.check_type(jtxt) # this should set psychsim_tags
        obs = json.loads(jtxt)
        message = obs[u'msg']
        data = obs[u'data']
        alldat = {}
        for (k,v) in data.items():
            if k in self.psychsim_tags:
                alldat[k] = v
        for (k,v) in message.items():
            if k in self.psychsim_tags:
                alldat[k] = v
        if msg_type in ['triage', 'beep', 'motionz', 'lever']:
            self.add_room(alldat,msg_type)            
        elif msg_type in ['door']: 
            self.add_door_rooms(alldat,msg_type)
        return alldat

    # adds single message to msgreader.messages list
    def add_message(self,jtxt): 
        msg_type = self.check_type(jtxt) # this should set psychsim_tags
        if msg_type in self.msg_types and self.mission_running:
            m = msg(msg_type)
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
            if msg_type in ['Event:Triage', 'Event:Lever']:
                self.add_room(m.mdict,msg_type)            
            elif msg_type == 'Event:Door':
                self.add_door_rooms(m.mdict,msg_type)
            self.messages.append(m)

    # adds which room event is occurring in 
    def add_room(self, msgdict, msg_type):
        x = 0
        z = 0
        xkey = ''
        ykey = ''
        zkey = ''
        room_name = ''
        for (k,v) in msgdict.items():
            if k.find('_x') > -1:
                x = float(v)
                xkey = k
            elif k.find('_z') > -1:
                z = int(v)
                zkey = k
            elif k.find('_y') > -1:
                ykey = k
        for r in self.rooms:
            if r.in_room(x,z):
                room_name = r.name
        del msgdict[xkey]
        del msgdict[ykey]
        del msgdict[zkey]

        msgdict.update({'room':room_name})

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
                del msgdict['door_y']
                del msgdict['door_z']
                doors_found += 1
        # if we did not find this door's adjoining rooms, it's not a portal, still need to update its fields
        if doors_found == 0:
            msgdict.update({'room1':'null'})
            msgdict.update({'room2':'null'})
            del msgdict['door_x'] # no longer needed once have ajoining rooms
            del msgdict['door_y']
            del msgdict['door_z']
        
    # check what kind of event to determine tags to look for
    # if doesn't match any, we don't care about it so tag list will be empty
    # and message won't be processed
    def check_type(self,jtxt):
        msg_type = 'NONE'
        self.psychsim_tags = ['mission_timer', 'sub_type', 'playername']
        if jtxt.find('Event:Triage') > -1:
            self.psychsim_tags += ['triage_state', 'color', 'victim_x', 'victim_y', 'victim_z']
            msg_type = 'Event:Triage'
        elif jtxt.find('Event:Door') > -1:
            self.psychsim_tags += ['open', 'door_x', 'door_y', 'door_z', 'room1', 'room2']
            msg_type = 'Event:Door'
        return msg_type

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

# USE: create reader object then use to read either last message in file -- returns single dict
# or all messages in file -- returns array of dictionaries

jsonfile = '/home/skenny/usc/asist/data/study-1_2020.08_TrialMessages_CondBtwn-NoTriageNoSignal_CondWin-FalconEasy-StaticMap_Trial-120_Team-na_Member-51_Vers-1.metadata'
reader = msgreader(jsonfile, True)
reader.load_rooms('/home/skenny/usc/asist/data/ASIST_FalconMap_Rooms_v1.1_OCN.csv')
reader.load_doors('/home/skenny/usc/asist/data/ASIST_FalconMap_Portals_v1.1_OCN.csv')
reader.add_all_messages(jsonfile)
# print all the messages
for m in reader.messages:
    print(str(m.mdict))
