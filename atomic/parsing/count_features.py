#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 10 13:22:33 2021

@author: mostafh
"""

import logging
import pandas as pd
import numpy as np

from abc import ABC, abstractmethod
 
class Feature(ABC):
 
    def __init__(self, nm, logger):
        self.logger = logger
        self.name = nm
        self.history = list()
        super().__init__()
        self.rooms_to_track = []
        self.dataframe = pd.DataFrame(columns=['time'])
    
    def processMsg(self, msg):
        self.msg_type = msg['sub_type']
        self.msg_player = msg.get('playername', msg.get('participant_id', None))
        self.msg_time = msg['mission_timer']

    @abstractmethod
    def printValue(self):
        pass
        
    def tracked(self, room):
        for hw in self.rooms_to_track:
            if room.startswith(hw):
                return True
        return False      
    
    def warn(self, text):
        self.logger.warn(text)
        
    def getHistory(self):
        return self.history
    
    def getHistoryOfPlayer(self, player):
        return [m for m in self.history if m['playername'] == player]
    
    def addRow(self, row_dict):
        ## Regardless of message type, add a row
        row = {'time':self.msg_time}
        row.update(row_dict)
        self.dataframe = self.dataframe.append(row, ignore_index=True)
        
    def addCol(self, colName):
        self.dataframe[colName] = np.zeros((len(self.dataframe)))
    
    def getDataframe(self):
        return self.dataframe
    
class CountVisitsPerRole(Feature):
    def __init__(self, roomsToTrack, logger=logging):
        super().__init__("visit count per room per role", logger)    
        self.roomToRoleToCount = dict()
        self.playerToRole = dict()        
        
    # keep track of each player's role and list of rooms
    def processMsg(self, msg):
        super().processMsg(msg)
        
        if self.msg_type == 'Event:Location':
            room = msg['room_name']
            if room not in self.roomToRoleToCount.keys():
                self.roomToRoleToCount[room] = dict()
            role = self.playerToRole[self.msg_player]            
            if role not in self.roomToRoleToCount[room].keys():
                self.roomToRoleToCount[room][role] = 0
            self.roomToRoleToCount[room][role] = self.roomToRoleToCount[room][role] + 1
            self.history.append()
            
        if self.msg_type == 'Event:RoleSelected':
            role = msg['new_role']
            oldRole = msg['old_role']
            if self.msg_player not in self.playerToRole.keys():
                self.playerToRole[self.msg_player] = oldRole
            if self.playerToRole[self.msg_player] != oldRole:
                super().warn('Previous role does not match ' + self.msg_player + ' actually ' + self.playerToRole[self.msg_player] + ' from msg ' + oldRole)                
            self.playerToRole[self.msg_player] = role
            self.history.append()
            
    def printValue(self):
        print(self.name, self.roomToRoleToCount)
                
class CountRoleChanges(Feature):
    def __init__(self, logger=logging):
        super().__init__("count role changes", logger)
        self.playerToCount = dict()
        
    def processMsg(self, msg):
        super().processMsg(msg)
        
        if self.msg_type == 'Event:RoleSelected':
            if self.msg_player not in self.playerToCount.keys():
                self.playerToCount[self.msg_player] = 0
                self.addCol(self.msg_player+'_role_change')
            self.playerToCount[self.msg_player] = self.playerToCount[self.msg_player] + 1
            self.history.append(msg)
            
        self.addRow({pl+'_role_change':ct for pl, ct in  self.playerToCount.items()})
            
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
        super().processMsg(msg)
        
        if self.msg_player not in self.playerToActed.keys():
            self.playerToActed[self.msg_player] = False
        if self.msg_player not in self.playerToCount.keys():
            self.playerToCount[self.msg_player] = 0
            self.addCol(self.msg_player+'_entry_exit')
        if self.msg_player not in self.playerToPrevLoc.keys():
            self.playerToPrevLoc[self.msg_player] = ''
        
        if self.msg_type == 'Event:location':
            prevRoom = self.playerToPrevLoc[self.msg_player]
            room = msg['room_name']
            if self.tracked(prevRoom):
                if not self.playerToActed[self.msg_player]:
                    self.playerToCount[self.msg_player] = self.playerToCount[self.msg_player] + 1
            if self.tracked(prevRoom) or self.tracked(room):
                self.history.append(msg)
            self.playerToPrevLoc[self.msg_player] = room
            self.playerToActed[self.msg_player] = False
            
        if self.msg_type == 'Event:ToolUsed':
            self.playerToActed[self.msg_player] = True
            self.history.append(msg)

        self.addRow({pl+'_entry_exit':ct for pl, ct in  self.playerToCount.items()})  
            
    def printValue(self):
        print(self.name, self.playerToCount)
            

class CountTriageInHallways(Feature):
    def __init__(self, hallways, logger=logging):
        super().__init__("fraction of victims triaged in hallways", logger)
        self.triagesInHallways = 0
        self.triagesInRooms = 0
        self.rooms_to_track = hallways
        self.addCol('hallway_triage')
        self.addCol('room_triage')
        
    def processMsg(self, msg):
        super().processMsg(msg)
        
        if (self.msg_type == 'Event:Triage') and (msg['triage_state'] == 'SUCCESSFUL'):
            room = msg['room_name']
            if self.tracked(room):
                self.triagesInHallways = self.triagesInHallways + 1
            else:
                self.triagesInRooms = self.triagesInRooms + 1
            self.history.append(msg)
            
        self.addRow({'hallway_triage':self.triagesInHallways, 'room_triage':self.triagesInRooms})
        
    def printValue(self):
        print('Total triaged', self.triagesInRooms + self.triagesInHallways, 
              'Fraction in hallways', self.triagesInHallways / (self.triagesInRooms + self.triagesInHallways))

class CountAction(Feature):
    def __init__(self, type_to_count, arg_values, logger=logging):
        super().__init__("count number of times a player sees msg %s with args %s" % (type_to_count, arg_values), logger)
        self.playerToCount = dict()
        self.type_to_count= type_to_count
        self.arg_values = arg_values
        
    def _getColName(self, pl):
        return pl + self.type_to_count + str(self.arg_values)
        
    def processMsg(self, msg):
        super().processMsg(msg)
        
        if self.msg_type == self.type_to_count:
            for arg, value in self.arg_values.items():
                if (arg not in msg.keys()) or (msg[arg] != value):
                    return
            if self.msg_player not in self.playerToCount.keys():
                self.playerToCount[self.msg_player] = 0
                self.addCol(self._getColName(self.msg_player))
            self.playerToCount[self.msg_player] = self.playerToCount[self.msg_player] + 1
            self.history.append(msg)
            
        self.addRow({self._getColName(pl):val for pl,val in self.playerToCount.items()})
            
    def printValue(self):
        print(self.name, self.playerToCount)

        
#This was written to work w/T000315
class CountPlayerDialogueEvents(Feature):
    def __init__(self, logger=logging):
        super().__init__("count number of times a player talks", logger)
        self.playerToCount = dict()
        
    def processMsg(self, msg):
        super().processMsg(msg)
        
        if self.msg_type == 'Event:dialogue_event':
            if self.msg_player not in self.playerToCount.keys():
                self.playerToCount[self.msg_player] = 0
            self.playerToCount[self.msg_player] = self.playerToCount[self.msg_player] + 1
            self.history.append(msg)
            
    def printValue(self):
        print(self.name, self.playerToCount)