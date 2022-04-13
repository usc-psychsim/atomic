#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 20:35:23 2020

@author: mostafh
"""
import logging
from atomic.parsing import GameLogParser
from atomic.parsing.json_parser import JSONReader
from atomic.definitions import MISSION_DURATION, extract_time
import numpy as np


class MsgQCreator(GameLogParser):

    def __init__(self, filename, processor=None, logger=logging, use_collapsed_map=True, use_ihmc_locations=True, verbose=True):
        self.verbose = verbose
        super().__init__(filename, processor, logger)
        self.call_sign_2_role = {'BLUE_ASIST1':'eng', 'GREEN_ASIST1':'tran', 'RED_ASIST1':'med'}
        self.locations = set()
        self.jsonFile = filename
        self.grouping_res = 10
        if len(filename) > 0:
            print('Reading json with these input files', filename)
            self.jsonParser = JSONReader(filename, verbose=verbose, use_collapsed_map=use_collapsed_map, use_ihmc_locations=use_ihmc_locations)
            self.jsonParser.read_semantic_map()

    def startProcessing_simple(self): 
        self.jsonParser.registerFeatures([])
        self.jsonParser.process_json_file(self.jsonFile)

    def startProcessing(self, featuresToExtract, msg_types): 
        self.jsonParser.registerFeatures(featuresToExtract)
        self.jsonParser.process_json_file(self.jsonFile)
        
        self.allPlayersMs = [m for m in self.jsonParser.messages if msg_types is None or m['sub_type'] in msg_types]
        
        self.players = set([m['playername'] for m in self.allPlayersMs if m['playername'] is not None])
        if self.verbose: print("all players", self.players)
        
        ## Initialize player-specific data structures
        self.playerToMsgs = {pl:[m for m in self.allPlayersMs if m['playername'] == pl] for pl in self.players}
        self.createActionQs()
        

    def _getGroupedMsgs(self, player, maxTime):
        nextMsg = self.nextMsgIdx[player]
        groupedMsgs = []
        while nextMsg < len(self.playerToMsgs[player]):
            msg = self.playerToMsgs[player][nextMsg]
            
            if 'mission_timer' not in msg or ':' not in msg['mission_timer']:
                nextMsg = nextMsg + 1
                continue
            
            ## If malformed time, skip
            timeInSec = extract_time(msg)
            if timeInSec is None:
                nextMsg = nextMsg + 1
                continue
            
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
                    break
            if allDone:
                if self.verbose: print('Everyone done')
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
#                    msg['playername'] = self.call_sign_2_role[player]
#                    step_actions[self.call_sign_2_role[player]] = msg
#                    msg['playername'] = self.call_sign_2_role[player]
                    step_actions[player] = msg
                self.actions.append(step_actions)
                        
