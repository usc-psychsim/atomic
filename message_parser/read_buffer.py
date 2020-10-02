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

class msgreader(object):
    def __init__(self, fname, latest=False):
        self.psychsim_tags = []
        self.nmessages = 0
        self.rooms = []
 
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

    def get_message_debug(self,jtxt):
        print('****getting info*******')
        obs = json.loads(jtxt)
        message = obs[u'msg']
        data = obs[u'data']
        alldat = {}
        print("printing single message....")
        for (k,v) in data.items():
            if k in self.psychsim_tags:
                alldat[k] = v
        for (k,v) in message.items():
            if k in self.psychsim_tags:
                alldat[k] = v
        for (k,v) in alldat.items(): 
            print("key: "+k)
            print("val: "+str(v))

    # TODO: add messages to msg reader instance instead of returning directly
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
        if msg_type in ['triage', 'door', 'beep', 'motionz', 'lever']:
            self.add_rooms(alldat,msg_type)            
        return alldat

    #pull vals from csv -- maybe don't need message type
    def add_rooms(self, msgdict, msg_type):
        x = 0
        z = 0
        for (k,v) in msgdict.items():
            if k.find('_x') > -1:
                x = float(v)
            elif k.find('_z') > -1:
                z = int(v)
        for r in self.rooms:
#            print(" HEREEEEE room name = "+r.name+" x = "+str(x)+" z = "+str(z))
            if r.in_room(x,z):
                msgdict.update({'room':r.name})

    # check what kind of event to determine tags to look for
    # if doesn't match any, we don't care about it so tag list will be empty
    # and message won't be processed
    def check_type(self,jtxt):
        msg_type = ''
        if jtxt.find('Event:Triage') > -1:
            self.psychsim_tags = ['sub_type', 'triage_state', 'color', 'victim_x', 'victim_y', 'victim_z', 'timestamp', 'playername']
            msg_type = 'triage'
        elif jtxt.find('Event:MissionState') > -1:
            self.psychsim_tags = ['mission_state', 'mission']
            msg_type = 'mission'
        elif jtxt.find('Event:Door') > -1:
            self.psychsim_tags = ['mission_timer', 'playername', 'open', 'door_x', 'door_y', 'door_z']
            msg_type = 'door'
        elif jtxt.find('Event:Beep') > -1:
            self.psychsim_tags = ['playername', 'mission_timer', 'beep_x', 'beep_y', 'beep_z', 'message']
            msg_type = 'beep'
        elif jtxt.find('Event:Pause') > -1:
            self.psychsim_tags = ['mission_timer', 'paused']
            msg_type = 'pause'
        elif jtxt.find('Event:Location') > -1: # not seeing entered_locations in current tria data thus far
            self.psychsim_tags = ['playername', 'exited_locatoins', 'connected_locations']
            msg_type = 'location'
        elif jtxt.find('Event:VictimsExpired') > -1:
            self.psychsim_tags = ['mission_timer', 'message']
            msg_type = 'victimsexpired'
        elif jtxt.find('Mission:VictimList') > -1:
            self.psychsim_tags = ['mission_victim_list', 'room_name', 'message_type']
            msg_type = 'victimlist'
        elif jtxt.find('FoV') > -1:
            self.psychsim_tags = ['playername', 'sub_type', 'observation', 'blocks']
            msg_type = 'fov'
        elif jtxt.find('motion_z') > -1: # for type 'state' to disambiguate
            self.psychsim_tags = ['playername', 'sub_type', 'motion_x', 'motion_y', 'motion_z', 'message_type', 'yaw', 'pitch', 'life']
            msg_type = 'motionz'
        elif jtxt.find('Event:Lever') > -1:
            self.psychsim_tags = ['playername', 'mission_time', 'powered', 'lever_x', 'lever_y', 'lever_z']
            msg_type = 'lever'
        else:
            self.psychsim_tags = []
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

# USE: create reader object then use to read either last message in file -- returns single dict
# or all messages in file -- returns array of dictionaries

jsonfile = '/home/skenny/usc/asist/data/study-1_2020.08_TrialMessages_CondBtwn-NoTriageNoSignal_CondWin-FalconEasy-StaticMap_Trial-120_Team-na_Member-51_Vers-1.metadata'
reader = msgreader(jsonfile, True)
reader.load_rooms('/home/skenny/usc/asist/data/ASIST_FalconMap_Rooms_v1.1_OCN.csv')
singlemsg = reader.get_latest_message(jsonfile)
print("LAST MESSAGE "+str(singlemsg))
allmsgs = reader.get_all_messages(jsonfile)
#print("ALL MSGS: "+str(allmsgs))

