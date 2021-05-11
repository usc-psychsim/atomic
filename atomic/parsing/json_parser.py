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
from atomic.parsing.pilot2_message_reader import createJSONParser
from atomic.definitions import GOLD_STR, GREEN_STR, WHITE_STR, MISSION_DURATION

MOVE = 0
TRIAGE = 1


class ProcessParsedJson(GameLogParser):

    def __init__(self, filename, map_data, processor=None, logger=logging):
        super().__init__(filename, processor, logger)
        self.lastParsedLoc = None
        self.actions = []
        self.allMs = []
        self.locations = set()
        self.triageStartTime = 0
        self.jsonFile = filename
        if len(filename) > 0:
            print('Reading json with these input files', filename)
            self.jsonParser = createJSONParser(map_data.room_file)
        if map_data:
            self.setVictimLocations(map_data.victims)

            
    def startProcessing(self, featuresToExtract): 
        self.jsonParser.registerFeatures(featuresToExtract)
        self.jsonParser.process_json_file(self.jsonFile)
        self.allPlayersMs = self.jsonParser.messages
        self.vList = self.jsonParser.vList
        self.pickTriager()
        
    def useParsedFile(self, msgfile):
        jsonfile = open(msgfile, 'rt')
        for line in jsonfile.readlines():
            self.allMs.append(json.loads(line))
            
        self.pickTriager()
        
    def pickTriager(self):
        """ Pick a player who spent time as a medic. Ignore everyone else!
        """
        players = set([m['playername'] for m in self.allPlayersMs])
        print("all players", players)
        msgTypes = {pl:set([m['sub_type'] for m in self.allPlayersMs if (m['playername'] == pl) and ('sub_type' in m)]) for pl in players}
        print("all msgTypes", msgTypes)
        triagePlayers = set([m['playername'] for m in self.allPlayersMs if m['sub_type'] == 'Event:Triage'])
        print("all players who triaged", triagePlayers )
        self.playerToMsgs = {pl:[m for m in self.allPlayersMs if m['playername'] == pl] for pl in players}
        if len(triagePlayers) > 0:
            chosenOne = triagePlayers.pop()
            # Get messages of this player AND ANY victim pick up/drop off messages
            self.allMs = [m for m in self.allPlayersMs if (m['playername'] == chosenOne) or
                                                  ( m['sub_type']=='Event:VictimPickedUp') or
                                                  ( m['sub_type']=='Event:VictimPlaced') or 
                                                  ( m['sub_type']=='Event:RoleSelected') ]
            self.human = chosenOne
        
    def player_name(self):
        return self.human

    ###############################################
    #######  Message handlers
    ###############################################

    def parseTriageStart(self, vicColor, ts):
        self.logger.debug('triage started of %s at %s' % (vicColor, ts))
        self.triageStartTime = ts

    def parseTriageEnd(self, vicColor, isSuccessful, msgIdx, ts):
        self.logger.debug('triage ended (success = %s) of %s at %s' % (isSuccessful, vicColor, ts))
        
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
        if (self.lastParsedLoc in self.roomToVicDict) and (vicColor in self.roomToVicDict[self.lastParsedLoc]):
            if isSuccessful:
                self.roomToVicDict[self.lastParsedLoc].remove(vicColor)
            triageAct = self.victimsObj.getTriageAction(self.human, vicColor)
            ## Record it as happening at self.triageStartTime
            self.actions.append([TRIAGE, [triageAct, duration], msgIdx, self.triageStartTime])
        else:
            self.logger.warn("ERROR: triaged non-existent %s victim in %s at %s" % (vicColor, self.lastParsedLoc, ts))
            return 1
        return 0

    def parseMove(self, newRoom, msgIdx, ts):
        self.locations.add(newRoom)
        if self.lastParsedLoc == None:
            self.actions.append(newRoom)
            self.lastParsedLoc = newRoom
            self.logger.debug('moved to %s at %s' % (self.lastParsedLoc, ts))
            return 0

        # Add one or more move actions
        mv = self.world_map.getMoveAction(self.human, self.lastParsedLoc, newRoom)
        if mv == []:
            self.logger.error('unreachable %s to %s at %s' % (self.lastParsedLoc, newRoom, ts))
            self.lastParsedLoc = newRoom
            return 1

        if len(mv) > 1:
            self.logger.error('multiple steps from %s to %s at %s' % (self.lastParsedLoc, newRoom, ts))
        for mAct in mv:
            self.actions.append([MOVE, [mAct], msgIdx, ts])
        self.logger.debug('moved to %s at %s' % (newRoom, ts))
        self.lastParsedLoc = newRoom
        return 0
    
    def parseVictimPicked(self, vicColor, room, ts):
        if (room in self.roomToVicDict) and (vicColor in self.roomToVicDict[room]):
            self.roomToVicDict[room].remove(vicColor)
        else:
            self.logger.warn("ERROR: picked up non-existent %s victim in %s at %s" % (vicColor, room, ts))

    def parseVictimPlaced(self, vicColor, room, ts):
        if room not in self.roomToVicDict:
            self.roomToVicDict[room] = []
        self.roomToVicDict[room].append(vicColor)

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
        triageInProgress = False

        while (m != None) and ((maxActions < 0) or (numMsgs < maxActions)):
            err = 0
            mtype = m['sub_type']
            if mtype in ignore:
                m = next(jsonMsgIter)
                numMsgs = numMsgs + 1
                continue
            ## time elapsed in seconds
            mtime = m['mission_timer']
            try:
                ts = [int(x) for x in mtime.split(':')]
            except ValueError:
                # Mission timer error message
                pass
            #            print(numMsgs)
#            if ffwd > 0 and numMsgs >= ffwd:
#                input('press any key.. ')
            if 'color' in m.keys():                
                vicColor = m['color'].lower()
            else:
                vicColor = None
                
            if mtype == 'Event:Triage':
                tstate = m['triage_state']
                vicColor = m['color'].lower()
                if m.get('room_name', self.lastParsedLoc) != self.lastParsedLoc:
                    self.logger.error(
                        'Msg %d Triaging in %s but I am in %s' % (numMsgs, m['room_name'], self.lastParsedLoc))

                if tstate == 'IN_PROGRESS':
                    self.parseTriageStart(vicColor, ts)
                    triageInProgress = True
                else:
                    success = (tstate == 'SUCCESSFUL')
                    err = self.parseTriageEnd(vicColor, success, numMsgs, ts)
                    triageInProgress = False

            elif mtype == 'Event:Location':
                if triageInProgress:
                    self.logger.error('At %s msg %d walked out of room while triaging' % (m['mission_timer'], numMsgs))
                    triageInProgress = False
                loc = m['room_name']
                err = self.parseMove(loc, numMsgs, ts)
                    
            elif mtype == 'Event:VictimPickedUp':
                self.logger.info(m['playername'] + " picked " + vicColor + " in " + m['room_name'])
                self.parseVictimPicked(vicColor, m['room_name'], ts)

            elif mtype == 'Event:VictimPlaced':
                self.logger.info(m['playername'] + " placed " + vicColor + " in " + m['room_name'])
                self.parseVictimPlaced(vicColor, m['room_name'], ts)
                
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

    def runTimeless(self, world, start, end, ffwdTo=0, prune_threshold=None, permissive=False):
        self.logger.debug(self.actions[start])
        if start == 0:
            loc = self.actions[0]
            world.setState(self.human, 'loc', loc, recurse=True)
#            world.agents[self.human].setBelief(stateKey(self.human, 'loc'), loc)
            world.setState(self.human, 'locvisits_' + loc, 1, recurse=True)
#            world.agents[self.human].setBelief(stateKey(self.human, 'locvisits_' + loc), 1)
            start = 1

        clockKey = stateKey(WORLD, 'seconds')
        t = start
        while True:
            if (t >= end) or (t >= len(self.actions)):
                break

            actStruct = self.actions[t]
            actType = actStruct[0]
            act = actStruct[1][0]
            testbedMsgId = actStruct[-2]
            trueTime = actStruct[-1]
            timeInSec = MISSION_DURATION - (trueTime[0] * 60) - trueTime[1]

            self.logger.info('%d) Running msg %d: %s' % (t + start, testbedMsgId, ','.join(map(str, actStruct[1]))))

            # before any action, manually sync the time feature with the game's time (invert timer)
            world.setFeature(clockKey, timeInSec, recurse=True)

            if self.processor is not None:
                self.processor.pre_step(world)
            selDict = dict()
            if act not in world.agents[self.human].getLegalActions():
                self.logger.error('Illegal %s' % (act))
                raise ValueError('Illegal action!')

            if actType == MOVE:
                pass

            if actType == TRIAGE:
                dur = actStruct[1][1]                
                curTime = world.getFeature(clockKey, unique=True)
                newTime = curTime + dur
                selDict[clockKey] = newTime
                self.logger.debug('Time now %d triage until %d' % (curTime, newTime))

            t = t + 1
            self.logger.info('Injecting %s' % (selDict))
            selDict = {k: world.value2float(k, v) for k, v in selDict.items()}
            world.step(act, select=selDict, threshold=prune_threshold)
            world.modelGC()

            self.summarizeState(world, trueTime)
            if self.processor is not None:
                self.processor.post_step(world, None if act is None else world.getAction(self.human))

            if t + start - 1 > ffwdTo:
                input('press any key.. ')

    def summarizeState(self, world, ttime):
        loc = world.getState(self.human, 'loc', unique=True)
        time = MISSION_DURATION - world.getState(WORLD, 'seconds', unique=True)
        self.logger.info('psim Time: %s' % ([int(time / 60), time % 60]))
        self.logger.info('True Time: %s' % (ttime))
        self.logger.info('Phase: %s' % (world.getState(WORLD, 'phase', unique=True)))

        self.logger.info('Player location: %s' % (loc))
        clrs = [GOLD_STR, GREEN_STR, WHITE_STR]
        for clr in clrs:
            self.logger.debug('%s count: %s' % (clr, world.getState(WORLD, 'ctr_' + loc + '_' + clr, unique=True)))
        self.logger.info('Visits: %d' % (world.getState(self.human, 'locvisits_' + loc, unique=True)))
        self.logger.info('JustSavedGr: %s' % (world.getState(self.human, 'numsaved_' + GREEN_STR, unique=True)))
        self.logger.info('JustSavedGd: %s' % (world.getState(self.human, 'numsaved_' + GOLD_STR, unique=True)))

# f = open('/home/mostafh/Documents/psim/new_atomic/atomic/data/tryj', 'rt')
# lines = f.readlines()
# jsonIter = ite([m.mdict for m in reader.messages])
# jsonParser = ProcessParsedJson()
# jsonParser.processJson(jsonIter, 100)
