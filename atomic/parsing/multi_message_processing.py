#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 20:35:23 2020

@author: mostafh
"""
import logging
import json
from psychsim.pwl import stateKey
from psychsim.world import WORLD
from atomic.parsing import GameLogParser
from atomic.parsing.json_parser import createJSONParser
from atomic.definitions import GOLD_STR, GREEN_STR, WHITE_STR, MISSION_DURATION, INJECT_PSYCH_ACTIONS
import numpy as np

MOVE = 0
TRIAGE = 1


class ProcessParsedJson(GameLogParser):

    def __init__(self, filename, room_list, processor=None, logger=logging):
        super().__init__(filename, processor, logger)
        self.world = None
        self.playerToAgent = {}
        self.agentToPlayer = {}
        self.locations = set()
        self.jsonFile = filename
        if len(filename) > 0:
            print('Reading json with these input files', filename)
            self.jsonParser = createJSONParser(room_list)
            
    def startProcessing(self, featuresToExtract): 
        self.jsonParser.registerFeatures(featuresToExtract)
        self.jsonParser.process_json_file(self.jsonFile)
        self.allPlayersMs = self.jsonParser.messages
        self.vList = self.jsonParser.vList
        print(len(self.allPlayersMs))
        
        self.createActionQs()
        
    def useParsedFile(self, msgfile):
        jsonfile = open(msgfile, 'rt')
        for line in jsonfile.readlines():
            self.allMs.append(json.loads(line))
            
        self.createActionQs()
        
    def createActionQs(self):
        """ Create an action queue per player
        """
        self.players = set([m['playername'] for m in self.allPlayersMs])
        print("all players", self.players)
        msgTypes = {pl:set([m['sub_type'] for m in self.allPlayersMs if (m['playername'] == pl) and ('sub_type' in m)]) for pl in self.players}
        print("all msgTypes", msgTypes)
        triagePlayers = set([m['playername'] for m in self.allPlayersMs if m['sub_type'] == 'Event:Triage'])
        print("all players who triaged", triagePlayers )
        
        ## Initialize player-specific data structures
        self.playerToMsgs = {pl:[m for m in self.allPlayersMs if m['playername'] == pl] for pl in self.players}        
        self.lastParsedLoc = {p:None for p in self.players}
        self.triageStartTime = {p:0 for p in self.players}
        self.actions = {p:[] for p in self.players}
        
    ###############################################
    #######  Message handlers
    ###############################################

    def parseTriageStart(self, player, vicColor, ts):
        self.logger.debug('%s triage started of %s at %s' % (player, vicColor, ts))
        self.triageStartTime[player] = ts

    def parseTriageEnd(self, player, vicColor, isSuccessful, msgIdx, ts):
        self.logger.debug('%s triage ended (success = %s) of %s at %s' % (player, isSuccessful, vicColor, ts))
        
        ## If reported as successful, force duration to be long enough
        if isSuccessful:
            if vicColor == GREEN_STR:
                duration = 8
            else:
                duration = 15
        ## Otherwise use actual duration capped by long enough duration
        else:
            duration = 5

        ## Update the parser's version of victims in each room
        if (self.lastParsedLoc[player] in self.roomToVicDict) and \
            (vicColor in self.roomToVicDict[self.lastParsedLoc[player]]):
            if isSuccessful:
                self.roomToVicDict[self.lastParsedLoc[player]].remove(vicColor)
            if INJECT_PSYCH_ACTIONS:
                triageAct = self.victimsObj.getTriageAction(player, vicColor)
            else:
                triageAct = None
            
            ## Record it as happening at self.triageStartTime
            self.actions[player].append([TRIAGE, [triageAct, duration], msgIdx, self.triageStartTime[player]])
        else:
            self.logger.warn("ERROR: triaged non-existent %s victim in %s at %s" % (vicColor, self.lastParsedLoc[player], ts))
            return 1
        return 0

    def firstLocation(self, player, newRoom, ts):
        if (self.lastParsedLoc[player] is None) and (newRoom is not None):
            self.actions[player].insert(0, [newRoom, ts])
            self.lastParsedLoc[player] = newRoom
            self.logger.debug('%s moved to %s at %s' % (player, self.lastParsedLoc[player], ts))
            

    def parseMove(self, player, newRoom, msgIdx, ts):
        self.locations.add(newRoom)
        # Add one or more move actions        
        if INJECT_PSYCH_ACTIONS:
            mv = self.world_map.getMoveAction(player, self.lastParsedLoc[player], newRoom)
        else:
            mv = [True]

        if mv == []:
            self.logger.error('unreachable %s to %s at %s' % (self.lastParsedLoc[player], newRoom, ts))
            self.lastParsedLoc[player] = newRoom
            return 1

        if len(mv) > 1:
            self.logger.error('multiple steps from %s to %s at %s' % (self.lastParsedLoc[player], newRoom, ts))
        for mAct in mv:
            self.actions[player].append([MOVE, [mAct], msgIdx, ts])
        self.logger.debug('%s moved to %s at %s' % (player, newRoom, ts))
        self.lastParsedLoc[player] = newRoom
        return 0
    
    def parseVictimPicked(self, player, vicColor, room, msgIdx, ts):
        # TODO Inject action
        if (room in self.roomToVicDict) and (vicColor in self.roomToVicDict[room]):
            self.roomToVicDict[room].remove(vicColor)
            self.actions[player].append([-1, ['pickV'], msgIdx, ts])
        else:
            self.logger.warn("ERROR: picked up non-existent %s victim in %s at %s" % (vicColor, room, ts))

    def parseVictimPlaced(self, player, vicColor, room, msgIdx, ts):
        # TODO Inject action
        if room not in self.roomToVicDict:
            self.roomToVicDict[room] = []
        self.roomToVicDict[room].append(vicColor)
        self.actions[player].append([-1, ['placeV'], msgIdx, ts])

    ###############################################
    #######  Processing the json messages
    ###############################################
    
    def setVictimLocations(self, SandRVics):
        self.roomToVicDict = dict(SandRVics)

    def getActionsAndEvents(self, victims, world_map, maxActions=-1):
        jsonMsgIter = iter(self.allMs)
        self.world_map = world_map
        self.victimsObj = victims
        numMsgs = 0
        m = next(jsonMsgIter)
        ignore = ['Mission:VictimList']
        triageInProgress = {p:False for p in self.players}

        while (m != None) and ((maxActions < 0) or (numMsgs < maxActions)):
            err = 0
            mtype = m['sub_type']
            player = m['playername']
            loc = m.get('room_name', None)
            if 'color' in m.keys():                
                vicColor = m['color'].lower()
            
            if mtype in ignore:
                m = next(jsonMsgIter)
                numMsgs = numMsgs + 1
                continue
            
            ## time elapsed in seconds
            try:
                ts = [int(x) for x in m['mission_timer'].split(':')]
            except ValueError:
                pass
                                
            self.firstLocation(player, loc, ts)
 
            if mtype == 'Event:Triage':
                tstate = m['triage_state']
                if m.get('room_name', self.lastParsedLoc[player]) != self.lastParsedLoc[player]:
                    self.logger.error(
                        'Msg %d Triaging in %s but %s in %s' % (numMsgs, loc, player, self.lastParsedLoc[player]))

                if tstate == 'IN_PROGRESS':
                    self.parseTriageStart(player, vicColor, ts)
                    triageInProgress[player] = True
                else:
                    success = (tstate == 'SUCCESSFUL')
                    err = self.parseTriageEnd(player, vicColor, success, numMsgs, ts)
                    triageInProgress[player] = False

            elif mtype == 'Event:Location':
                if triageInProgress[player]:
                    self.logger.error('At %s msg %d walked out of room while triaging' % (m['mission_timer'], numMsgs))
                    triageInProgress[player] = False                
                err = self.parseMove(player, loc, numMsgs, ts)
                    
            elif mtype == 'Event:VictimPickedUp':
                self.logger.info(m['playername'] + " picked " + vicColor + " in " + loc)
                self.parseVictimPicked(player, vicColor, loc, numMsgs, ts)

            elif mtype == 'Event:VictimPlaced':
                self.logger.info(m['playername'] + " placed " + vicColor + " in " + loc)
                self.parseVictimPlaced(player, vicColor, loc, numMsgs, ts)
                
            elif mtype == 'Event:RoleSelected':
                self.logger.info(m['playername'] + " was " + m['prev_role'] + " became " + m['new_role'])


            if err > 0:
                self.logger.error('That was msg %d' % (numMsgs))
            m = next(jsonMsgIter, None)
            numMsgs = numMsgs + 1
        self.locations = list(self.locations)

    ###############################################
    #######  Running the actions we collected
    ###############################################
    
    def run1Action(self, player, actStruct, prune_threshold):         
        [actType, actAndOutcomes, testbedMsgId, trueTime] = actStruct[0]
        act = actAndOutcomes[0]
        outcomes = actAndOutcomes[1:]
        timeInSec = MISSION_DURATION - (trueTime[0] * 60) - trueTime[1]

        self.logger.info('Running msg %d: %s' % (testbedMsgId, ','.join(map(str, actAndOutcomes))))

        # before any action, manually sync the time feature with the game's time (invert timer)
        clockKey = stateKey(WORLD, 'seconds')
        self.worldsetFeature(clockKey, timeInSec, recurse=True)

        if self.processor is not None:
            self.processor.pre_step(self.world)
            
        if act not in self.worldagents[self.playerToAgent[player]].getLegalActions():
            self.logger.error('Illegal %s' % (act))
            raise ValueError('Illegal action!')

        selDict = {}
        if len(outcomes) > 0:
            dur = outcomes[0]
            curTime = self.worldgetFeature(clockKey, unique=True)
            newTime = curTime + dur
            selDict[clockKey] = newTime
            self.logger.debug('Time now %d triage until %d' % (curTime, newTime))

        self.logger.info('Injecting %s' % (selDict))
        selDict = {k: self.worldvalue2float(k, v) for k, v in selDict.items()}
        self.worldstep(act, select=selDict, threshold=prune_threshold)
        self.worldmodelGC()

        self.summarizeState(trueTime)
        if self.processor is not None:
            self.processor.post_step(self.world, None if act is None else self.worldgetAction(player))
            
    def runTimeless(self, start, end, ffwdTo=0, prune_threshold=None, permissive=False):
        for player in self.players:
            actStruct = self.actions[player][0]
            [loc, ts] = actStruct            
            self.worldsetState(self.playerToAgent[player], 'loc', loc, recurse=True)
#            self.worldagents[player].setBelief(stateKey(player, 'loc'), loc)
            self.worldsetState(self.playerToAgent[player], 'locvisits_' + loc, 1, recurse=True)
#            self.worldagents[player].setBelief(stateKey(player, 'locvisits_' + loc), 1)
        
        maxSteps = np.min([len(acts) for acts in self.actions.items()])
        self.logger.info('Running for %d steps' % (maxSteps))
        end = min(maxSteps, end)

        for t in range(1, end):
            for agent in self.world.agents.keys():
                player = self.agentToPlayer[agent]
                actStruct = self.actions[player][t]
                self.run1Action(actStruct, prune_threshold)
            if t > ffwdTo:
                input('press any key.. ')

    def summarizeState(self, ttime):
        time = MISSION_DURATION - self.worldgetState(WORLD, 'seconds', unique=True)
        self.logger.info('psim Time: %s' % ([int(time / 60), time % 60]))
        self.logger.info('True Time: %s' % (ttime))
        self.logger.info('Phase: %s' % (self.worldgetState(WORLD, 'phase', unique=True)))

        for player in self.players:
            loc = self.worldgetState(player, 'loc', unique=True)
            self.logger.info('Player %s location: %s' % (player, loc))
            for clr in [GOLD_STR, GREEN_STR, WHITE_STR]:
                self.logger.debug('%s count: %s' % (clr, self.worldgetState(WORLD, 'ctr_' + loc + '_' + clr, unique=True)))
            self.logger.info('SavedGr: %s' % (self.worldgetState(player, 'numsaved_' + GREEN_STR, unique=True)))

