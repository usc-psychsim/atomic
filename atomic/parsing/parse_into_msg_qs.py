#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 20:35:23 2020

@author: mostafh
"""
import logging
from atomic.parsing import GameLogParser
from atomic.parsing.json_parser import JSONReader
from atomic.definitions import MISSION_DURATION
import numpy as np


class MsgQCreator(GameLogParser):

    def __init__(self, filename, processor=None, logger=logging):
        super().__init__(filename, processor, logger)
        self.playerToAgent = {}
        self.agentToPlayer = {}
        self.locations = set()
        self.jsonFile = filename
        self.grouping_res = 10
        if len(filename) > 0:
            print('Reading json with these input files', filename)
            self.jsonParser = JSONReader(filename, True)
            self.jsonParser.read_semantic_map()
            
    def startProcessing(self, featuresToExtract, msg_types): 
        self.jsonParser.registerFeatures(featuresToExtract)
        self.jsonParser.process_json_file(self.jsonFile)
        self.allPlayersMs = [m for m in self.jsonParser.messages if msg_types is None or m['sub_type'] in msg_types]
        
        self.players = set([m['playername'] for m in self.allPlayersMs if m['playername'] is not None])
        print("all players", self.players)
               
        triagePlayers = set([m['playername'] for m in self.allPlayersMs if m['sub_type'] == 'Event:Triage'])
        print("all players who triaged", triagePlayers )
        
        ## Initialize player-specific data structures
        self.playerToMsgs = {pl:[m for m in self.allPlayersMs if m['playername'] == pl] for pl in self.players}
        # Establish a player name to RDDL agent name mapping. Arbitrary.
        for i,p in enumerate(self.players):
            self.playerToAgent[p] = 'p' + str(i+1)
            self.agentToPlayer['p' + str(i+1)] = p      
        
        self.createActionQs()
        

    def _getGroupedMsgs(self, player, maxTime):
        nextMsg = self.nextMsgIdx[player]
        groupedMsgs = []
        while nextMsg < len(self.playerToMsgs[player]):
            msg = self.playerToMsgs[player][nextMsg]
            
            if ':' not in msg['mission_timer']:
                continue
            
            ## If malformed time, skip
            nums = msg['mission_timer'].split(':')
            if np.any([not n.strip().isdigit() for n in nums]):
                continue
            
            ## Extract time
            ts = [int(n) for n in nums]
            timeInSec = MISSION_DURATION - (ts[0] * 60) - ts[1]
            
            ## If message is later than our cutoff time, break
            if timeInSec > maxTime:
                break
            
            ## If message is earlier than our cutoff time, include it and increment index
            groupedMsgs.append(nextMsg)
            nextMsg = nextMsg + 1
            
            
        self.nextMsgIdx[player] = nextMsg
        return groupedMsgs
    

    def createActionQs(self):
        self.nextMsgIdx = {p:0 for p in self.players}
        self.actions = []

        ## For every time interval
        for timeNow in np.arange(0, MISSION_DURATION+1, self.grouping_res):
            self.logger.debug('=== Seconds %d to %d' %(timeNow, timeNow + self.grouping_res))
            
            ## For each player, get the actions they did in this interval
            playerToMs = {p:self._getGroupedMsgs(p, timeNow + self.grouping_res) for p in self.players}
            
            ## Determine the largest number of actions a player did in this interval
            maxNumActs = np.max([len(msgs) for msgs in playerToMs.values()])
            
            ## If all players have processed all their messages, we're done.
            allDone = True
            for player, msgIdx in self.nextMsgIdx.items():
                if msgIdx < len(self.playerToMsgs[player]):
                    allDone = False
            if allDone:
                print('Everyone done')
                break
            
            ## Add noops to players who don't have enough actions
            for player in self.players:
                if len(playerToMs[player]) < maxNumActs:
                    playerToMs[player].extend(np.repeat([-1], maxNumActs - len(playerToMs[player]), 0))
                    
            for ai in range(maxNumActs):
                step_actions = {}
                for player in self.players:
                    msgIdx = playerToMs[player][ai]
                    if msgIdx == -1:
                        msg = {'sub_type':'noop'}
                    else:
                        try:
                            msg = self.playerToMsgs[player][msgIdx]
                        except IndexError:
                            logging.error(f'Player "{player}" has {len(self.playerToMsgs[player])} messages, '\
                                f'so index {msgIdx} (during {timeNow}-{timeNow+self.grouping_res}) is too high.')
                            msg = {'sub_type':'noop'}
                    msg['realname'] = player
                    msg['playername'] = self.playerToAgent[player]
                    step_actions[self.playerToAgent[player]] = msg
                self.actions.append(step_actions)
                        
