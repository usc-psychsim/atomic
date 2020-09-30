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
print = functools.partial(print, flush=True)

class msgreader(object):
    def __init__(self, fname, latest=False):
        self.psychsim_tags = []
        self.nmessages = 0
 
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

    def parse_message(self,jtxt):
        self.check_type(jtxt) # this should set psychsim_tags
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
        return alldat

    # check what kind of event to determine tags to look for
    # if doesn't match any, we don't care about it so tag list will be empty
    # and message won't be processed
    def check_type(self,jtxt):
        if jtxt.find('Event:Triage') > -1:
            self.psychsim_tags = ['sub_type', 'triage_state', 'color', 'victim_x', 'victim_y', 'victim_z', 'timestamp', 'playername']
        elif jtxt.find('Event:MissionState') > -1:
            self.psychsim_tags = ['mission_state', 'mission']
        elif jtxt.find('Event:Door') > -1:
            self.psychsim_tags = ['mission_timer', 'playername', 'open', 'door_x', 'door_y', 'door_z']
        elif jtxt.find('Event:Beep') > -1:
            self.psychsim_tags = ['playername', 'mission_timer', 'beep_x', 'beep_y', 'beep_z', 'message']
        elif jtxt.find('Event:Pause') > -1:
            self.psychsim_tags = ['mission_timer', 'paused']
        elif jtxt.find('Event:Location') > -1: # not seeing entered_locations in current tria data thus far
            self.psychsim_tags = ['playername', 'exited_locatoins', 'connected_locations']
        elif jtxt.find('Event:VictimsExpired') > -1:
            self.psychsim_tags = ['mission_timer', 'message']
        elif jtxt.find('Mission:VictimList') > -1:
            self.psychsim_tags = ['mission_victim_list', 'room_name', 'message_type']
        elif jtxt.find('FoV') > -1:
            self.psychsim_tags = ['playername', 'sub_type', 'observation', 'blocks']
        elif jtxt.find('motion_z') > -1: # for type 'state' to disambiguate
            self.psychsim_tags = ['playername', 'sub_type', 'motion_x', 'motion_y', 'motion_z', 'message_type', 'yaw', 'pitch', 'life']
#        elif jtxt.find('Event:Lever') > -1: # event:lever not found in trial data thus far
        else:
            self.psychsim_tags = []

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

# USE: create reader object then use to read either last message in file -- returns single dict
# or all messages in file -- returns array of dictionaries

jsonfile = '/home/skenny/usc/asist/data/study-1_2020.08_TrialMessages_CondBtwn-NoTriageNoSignal_CondWin-FalconEasy-StaticMap_Trial-120_Team-na_Member-51_Vers-1.metadata'
reader = msgreader(jsonfile, True)
singlemsg = reader.get_latest_message(jsonfile)
print("LAST MESSAGE "+str(singlemsg))
allmsgs = reader.get_all_messages(jsonfile)

