#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 10 13:22:33 2021

@author: mostafh
"""

import logging

from abc import ABC, abstractmethod
 
class Feature(ABC):
 
    def __init__(self, nm, logger):
        self.logger = logger
        self.name = nm
        self.history = list()
        super().__init__()
    
    @abstractmethod
    def processMsg(self, msg):
        pass

    @abstractmethod
    def printValue(self):
        pass
    
    def warn(self, text):
        self.logger.warn(text)
        
    def getHistory(self):
        return self.history
    
    def getHistoryOfPlayer(self, player):
        return [m for m in self.history if m['playername'] == player]
    
class CountVisitsPerRole(Feature):
    def __init__(self, logger=logging):
        super().__init__("visit count per room per role", logger)    
        self.roomToRoleToCount = dict()
        self.playerToRole = dict()        
        
    # keep track of each player's role and list of rooms
    def processMsg(self, msg):
        mtype = msg['sub_type']
        player = msg['playername']
        
        if mtype == 'Event:Location':
            room = msg['room_name']
            if room not in self.roomToRoleToCount.keys():
                self.roomToRoleToCount[room] = dict()
            role = self.playerToRole[player]            
            if role not in self.roomToRoleToCount[room].keys():
                self.roomToRoleToCount[room][role] = 0
            self.roomToRoleToCount[room][role] = self.roomToRoleToCount[room][role] + 1
            self.history.append()
            
        if mtype == 'Event:RoleSelected':
            role = msg['new_role']
            oldRole = msg['old_role']
            if player not in self.playerToRole.keys():
                self.playerToRole[player] = oldRole
            if self.playerToRole[player] != oldRole:
                super().warn('Previous role does not match ' + player + ' actually ' + self.playerToRole[player] + ' from msg ' + oldRole)                
            self.playerToRole[player] = role
            self.history.append()
            
    def printValue(self):
        print(self.name, self.roomToRoleToCount)
                
class CountRoleChanges(Feature):
    def __init__(self, logger=logging):
        super().__init__("count role changes", logger)
        self.playerToCount = dict()
        
    def processMsg(self, msg):
        mtype = msg['sub_type']
        player = msg['playername']
        
        if mtype == 'Event:RoleSelected':
            if player not in self.playerToCount.keys():
                self.playerToCount[player] = 0
            self.playerToCount[player] = self.playerToCount[player] + 1
            self.history.append()
            
    def printValue(self):
        print(self.name, self.playerToCount)
            
class CountEnterExit(Feature):
    def __init__(self, roomsToTrack, logger=logging):
        super().__init__("enter-exit", logger)
        self.playerToCount = dict()
        self.roomsToTrack = roomsToTrack
        self.playerToActed = dict()
        self.playerToPrevLoc = dict()
        
    def processMsg(self, msg):
        mtype = msg['sub_type']
        player = msg['playername']
        
        if player not in self.playerToActed.keys():
            self.playerToActed[player] = False
        if player not in self.playerToCount.keys():
            self.playerToCount[player] = 0
        if player not in self.playerToPrevLoc.keys():
            self.playerToPrevLoc[player] = ''
        
        if mtype == 'Event:Location':
            prevRoom = self.playerToPrevLoc[player]
            room = msg['room_name']
            if prevRoom in self.roomsToTrack:
                if not self.playerToActed[player]:
                    self.playerToCount[player] = self.playerToCount[player] + 1
            if (prevRoom in self.roomsToTrack) or (room in self.roomsToTrack):
                self.history.append(msg)
            self.playerToPrevLoc[player] = room
            self.playerToActed[player] = False
            
        if mtype == 'Event:ToolUsed':
            self.playerToActed[player] = True
            self.history.append(msg)
            
    def printValue(self):
        print(self.name, self.playerToCount)
            

class CountTriageInHallways(Feature):
    def __init__(self, hallways, logger=logging):
        super().__init__("fraction of victims triaged in hallways", logger)
        self.triagesInHallways = 0
        self.triagesInRooms = 0
        self.hallways = hallways
            
    def processMsg(self, msg):
        mtype = msg['sub_type']
        
        if (mtype == 'Event:Triage') and (msg['triage_state'] == 'SUCCESSFUL'):
            room = msg['room']
            if room in self.hallways:
                self.triagesInHallways = self.triagesInHallways + 1
            else:
                self.triagesInRooms = self.triagesInRooms + 1
            self.history.append()    
        
    def printValue(self):
        print('Total triaged', self.triagesInRooms + self.triagesInHallways, 
              'Fraction in hallways', self.triagesInHallways / (self.triagesInRooms + self.triagesInHallways))
        
#This was written to work w/T000315
class CountPlayerDialogueEvents(Feature):
    def __init__(self, logger=logging):
        super().__init__("count number of times a player talks", logger)
        self.playerToCount = dict()
        
    def processMsg(self, msg):
        mtype = msg['sub_type']
        player = msg['playername']
        
        if mtype == 'Event:dialogue_event':
            if player not in self.playerToCount.keys():
                self.playerToCount[player] = 0
            self.playerToCount[player] = self.playerToCount[player] + 1
            self.history.append()
            
    def printValue(self):
        print(self.name, self.playerToCount)
