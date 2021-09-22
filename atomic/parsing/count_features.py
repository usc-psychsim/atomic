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

    COMPACT_DATA = True

    def __init__(self, nm, logger):
        self.logger = logger
        self.name = nm
        self.history = list()
        super().__init__()
        self.rooms_to_track = []
        self.dataframe = pd.DataFrame(columns=['time'])
    
    def processMsg(self, msg):
        self.msg_type = msg['sub_type']
        self.msg_player = msg.get('playername', None)
        if self.msg_player == 'Server':
            self.msg_player = None  # ignore server messages
        self.msg_time = msg['mission_timer'] if 'mission_timer' in msg else '-1:-1'

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
        row = {'time': tuple(map(int, self.msg_time.split(':')))}
        row.update(row_dict)
        self.dataframe = self.dataframe.append(row, ignore_index=True)
        
    def addCol(self, colName):
        self.dataframe[colName] = np.zeros((len(self.dataframe)))
    
    def getDataframe(self):
        return self.dataframe


class PlayerRoomPercentage(Feature):    
    def __init__(self, mission_length=15, logger=logging):
        super().__init__("percentage of time in room per player", logger)
        # Length of mission in minutes
        self.mission_length = 15
        # Current room per player
        self.player_loc = dict()
        # Number of seconds player has spent in each room
        self.player_occupancy = dict()
        # Last mission time of processed message
        self.last_time = {}
        # Total elapsed time (for normalization)
        self.total_time = {}

    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_type == 'Event:location':
            player = msg['participant_id']
            msg_time = tuple(map(int, self.msg_time.split(':')))
            msg_time = self.mission_length*60 - (msg_time[0]*60 + msg_time[1])
            if player in self.player_loc:
                room = self.player_loc[player]
                if room != msg['room_name']:
                    elapsed = msg_time - self.last_time[player]
                    self.player_occupancy[player][room] = self.player_occupancy[player].get(room, 0) + elapsed
                    # Roll forward
                    self.player_loc[player] = msg['room_name']
                    self.last_time[player] = msg_time
                    self.total_time[player] += elapsed
            else:
                self.player_loc[player] = msg['room_name']
                self.player_occupancy[player] = {}
                self.last_time[player] = msg_time
                self.total_time[player] = 0
            add_flag = True
        if add_flag:
            # Convert times into percentages
            for player, occupancy in self.player_occupancy.items():
                if self.total_time[player] > 0:
                    data = {'Participant': player}
                    for room, elapsed in occupancy.items():
                        label = f'Occupancy of {room}'
                        data[label] = elapsed/self.total_time[player]
                    self.addRow(data)

    def printValue(self):
        print(f'{self.name} {self.player_visits}')


class CountVisitsPerRole(Feature):
    def __init__(self, roomsToTrack, logger=logging):
        super().__init__("visit count per room per role", logger)    
        self.roomToRoleToCount = dict()
        self.playerToRole = dict()        
        
    # keep track of each player's role and list of rooms
    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_player is not None:
            if self.msg_type == 'Event:location':
                room = msg['room_name']
                if room not in self.roomToRoleToCount.keys():
                    self.roomToRoleToCount[room] = dict()
                if self.msg_player in self.playerToRole:
                    role = self.playerToRole[self.msg_player]
                    if role not in self.roomToRoleToCount[room].keys():
                        self.roomToRoleToCount[room][role] = 0
                    self.roomToRoleToCount[room][role] = self.roomToRoleToCount[room][role] + 1
                    self.history.append(msg)
                    add_flag = True

            if self.msg_type == 'Event:RoleSelected':
                role = msg['new_role']
                oldRole = msg['prev_role']
                if self.msg_player not in self.playerToRole.keys():
                    self.playerToRole[self.msg_player] = oldRole
                if self.playerToRole[self.msg_player] != oldRole:
                    super().warn('Previous role does not match ' + self.msg_player + ' actually ' + self.playerToRole[self.msg_player] + ' from msg ' + oldRole)
                self.playerToRole[self.msg_player] = role
                self.history.append(msg)
        if add_flag:
            row_dict = {}
            for room, role_counts in self.roomToRoleToCount.items():
                for role, count in role_counts.items():
                    label = f'{role}_visits_{room}'
                    if label not in self.dataframe.columns:
                        self.addCol(label)
                    row_dict[label] = count
            self.addRow(row_dict)
            
    def printValue(self):
        print(self.name, self.roomToRoleToCount)


class CountRoleChanges(Feature):
    def __init__(self, logger=logging):
        super().__init__("count role changes", logger)
        self.playerToCount = dict()
        
    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_player is not None and self.msg_type == 'Event:RoleSelected':
            if self.msg_player not in self.playerToCount.keys():
                self.playerToCount[self.msg_player] = 0
                self.addCol(self.msg_player+'_role_change')
            self.playerToCount[self.msg_player] = self.playerToCount[self.msg_player] + 1
            self.history.append(msg)
            add_flag = True
        if add_flag:
            if self.COMPACT_DATA:
                for pl, ct in self.playerToCount.items():
                    self.addRow({'Participant': pl, 'role_change': ct})
            else:
                self.addRow({pl+'_role_change':ct for pl, ct in  self.playerToCount.items()})
            
    def printValue(self):
        print(self.name, self.playerToCount)


class CountEnterExit(Feature):
    def __init__(self, roomsToTrack, logger=logging):
        super().__init__("enter-exit", logger)
        self.playerToCount = dict()
        self.rooms_to_track = roomsToTrack
        self.playerToActed = dict()
        self.playerToPrevLoc = dict()
        
        
    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_player is not None:
            if self.msg_player not in self.playerToActed.keys():
                self.playerToActed[self.msg_player] = False
            if self.msg_player not in self.playerToCount.keys():
                self.playerToCount[self.msg_player] = 0
                if not self.COMPACT_DATA:
                    self.addCol(self.msg_player+'_entry_exit')
            if self.msg_player not in self.playerToPrevLoc.keys():
                self.playerToPrevLoc[self.msg_player] = ''
        
            if self.msg_type == 'Event:location':
                prevRoom = self.playerToPrevLoc[self.msg_player]
                room = msg['room_name']
                if self.tracked(prevRoom):
                    if not self.playerToActed[self.msg_player]:
                        self.playerToCount[self.msg_player] = self.playerToCount[self.msg_player] + 1
                        add_flag = True
                if self.tracked(prevRoom) or self.tracked(room):
                    self.history.append(msg)
                self.playerToPrevLoc[self.msg_player] = room
                self.playerToActed[self.msg_player] = False

            if self.msg_type == 'Event:ToolUsed':
                self.playerToActed[self.msg_player] = True
                self.history.append(msg)
        if add_flag:
            if self.COMPACT_DATA:
                for pl, ct in self.playerToCount.items():
                    self.addRow({'Participant': pl, 'entry_exit': ct})
            else:
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
        add_flag = not self.COMPACT_DATA
        if (self.msg_type == 'Event:Triage') and (msg['triage_state'] == 'SUCCESSFUL'):
            room = msg['room_name']
            if self.tracked(room):
                self.triagesInHallways = self.triagesInHallways + 1
            else:
                self.triagesInRooms = self.triagesInRooms + 1
            self.history.append(msg)
            add_flag = True

        if add_flag:
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
        
    def _getColName(self, pl=None):
        if pl:
            return f'{pl}_{self.type_to_count}_{str(self.arg_values)}'
        else:
            return f'{self.type_to_count}_{str(self.arg_values)}'
        
    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_player is not None and self.msg_type == self.type_to_count:
            for arg, value in self.arg_values.items():
                if (arg not in msg.keys()) or (msg[arg] != value):
                    return
            if self.msg_player not in self.playerToCount.keys():
                self.playerToCount[self.msg_player] = 0
                if not self.COMPACT_DATA:
                    self.addCol(self._getColName(self.msg_player))
            self.playerToCount[self.msg_player] = self.playerToCount[self.msg_player] + 1
            self.history.append(msg)
            add_flag = True

        if add_flag:
            if self.COMPACT_DATA:
                for pl, val in self.playerToCount.items():
                    self.addRow({'Participant': pl, self._getColName(): val})
            else:
                self.addRow({self._getColName(pl):val for pl,val in self.playerToCount.items()})
            
    def printValue(self):
        print(self.name, self.playerToCount)

        
class RecordScore(Feature):
    def __init__(self, logger=logging):
        super().__init__('record score', logger)
        self.score = {}

    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if msg['sub_type'] == 'Event:Scoreboard':
            self.score.update({field if 'Score' in field else f'Score for {field}': value for field, value in msg['scoreboard'].items()})
            add_flag = True

        if add_flag:
            for field, value in self.score.items():
                if field[:10] == 'Score for ':
                    row = {'Participant': field[10:], 'Individual Score': value, 'Team Score': self.score['TeamScore']}
                else:
                    row = {'Participant': 'Team', 'Team Score': value}
                self.addRow(row)

    def printValue(self):
        print(f'{self.name} {self.score}')


class MarkerPlacement(Feature):
    def __init__(self, logger=logging):
        super().__init__('count marker placement per player per room', logger)
        self.marker_count = {}
        self.marker_legend = {}

    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_type == 'Event:MarkerPlaced':
            player = msg['participant_id']
            if player not in self.marker_count:
                self.marker_count[player] = {f'Marker Block {i+1}': {'regular': 0, 'critical': 0, 'none': 0} for i in range(3)}
            if msg['mark_critical'] > 0:
                self.marker_count[player][msg['marker_type']]['critical'] += 1
            elif msg['mark_regular'] > 0:
                self.marker_count[player][msg['marker_type']]['regular'] += 1
            else:
                self.marker_count[player][msg['marker_type']]['none'] += 1
            if 'marker_legend' in msg:
                self.marker_legend[player] = msg['marker_legend']
            add_flag = True

        if add_flag:
            for player, markers in self.marker_count.items():
                row = {'Participant': player}
                if player in self.marker_legend:
                    row[f'Marker Legend'] =  self.marker_legend[player]
                for marker, table in markers.items():
                    norm = sum(table.values())
                    if norm > 0:
                        norm_count = {f'{marker}_{victim}': count/norm for victim, count in table.items()}
                        row.update(norm_count)
                        row[marker] = norm
    #                    print(f'{player} {self.marker_legend[player]}: {norm_count}')
                self.addRow(row)

    def printValue(self):
        print(f'{self.name} {self.marker_count}')


class DialogueLabels(Feature):
    def __init__(self, logger=logging):
        super().__init__('count utterances per player per label', logger)
        self.utterances = {}

    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_type == 'asr:transcription':
            player = msg['participant_id']
            if player not in self.utterances:
                self.utterances[player] = {}
            for label in msg['extractions']:
                field = f'Utterance {label["label"]}'
                self.utterances[player][field] = self.utterances[player].get(field, 0) + 1
                add_flag = True
        if add_flag:
            for player, utterances in self.utterances.items():
                row = {'Participant': player, 'Utterance Total': sum(self.utterances[player].values())}
                row.update(utterances)
                if len(self.dataframe) > 0:
                    self.dataframe = self.dataframe[self.dataframe['Participant'] != player]
                self.addRow(row)

    def printValue(self):
        print(f'{self.name} {self.utterances}')
