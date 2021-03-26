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
from atomic.parsing.pilot2_message_reader import getMessages
from atomic.definitions import GOLD_STR, GREEN_STR, WHITE_STR

MOVE = 0
TRIAGE = 1


class ProcessParsedJson(GameLogParser):

    def __init__(self, filename, map_data, processor=None, logger=logging):
        super().__init__(filename, processor, logger)
        self.lastParsedLoc = None
        self.actions = []
        self.locations = set()
        self.triageStartTime = 0
        if len(filename) > 0:
            inputFiles = {
                '--msgfile': filename,
                '--roomfile': map_data.room_file,
                '--portalfile': map_data.portals_file,
                '--victimfile' : map_data.victim_file
            }
            print('Reading json with these input files', inputFiles)
            self.allMs, self.human = getMessages(inputFiles)
            self.originalMs = self.allMs
            self.pickTriager()
        
    def useParsedFile(self, msgfile):
        self.allMs = []
        jsonfile = open(msgfile, 'rt')
        for line in jsonfile.readlines():
            self.allMs.append(json.loads(line))
            
        self.pickTriager()
        
    def pickTriager(self):
        """ Pick a player who spent time as a medic. Ignore everyone else!
        """
        players = set([m['playername'] for m in self.allMs if m['sub_type'] == 'Event:Triage'])
        print("all plauers", players)
        chosenOne = players.pop()
        self.allMs = [m for m in self.allMs if ('playername' in m.keys()) and (m['playername'] == chosenOne)]
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
            self.logger.warn("ERROR: triaged non-existent %s victim in %s" % (vicColor, self.lastParsedLoc))

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
            mtype = m['sub_type']
            if mtype in ignore:
                m = next(jsonMsgIter)
                numMsgs = numMsgs + 1
                continue
            ## time elapsed in seconds
            mtime = m['mission_timer']
            ts = [int(x) for x in mtime.split(':')]

            #            print(numMsgs)
#            if ffwd > 0 and numMsgs >= ffwd:
#                input('press any key.. ')

            if mtype == 'Event:Triage':
                tstate = m['triage_state']
                vicColor = m['color'].lower()
                if m['room_name'] != self.lastParsedLoc:
                    self.logger.error(
                        'Msg %d Triaging in %s but I am in %s' % (numMsgs, m['room_name'], self.lastParsedLoc))

                if tstate == 'IN_PROGRESS':
                    self.parseTriageStart(vicColor, ts)
                    triageInProgress = True
                else:
                    success = (tstate == 'SUCCESSFUL')
                    self.parseTriageEnd(vicColor, success, numMsgs, ts)
                    triageInProgress = False

            elif mtype == 'Event:Location':
                if triageInProgress:
                    self.logger.error('At %s msg %d walked out of room while triaging' % (m['mission_timer'], numMsgs))
                    triageInProgress = False
                loc = m['room_name']
                ret = self.parseMove(loc, numMsgs, ts)
                if ret > 0:
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
            world.setState(self.human, 'loc', loc)
            world.agents[self.human].setBelief(stateKey(self.human, 'loc'), loc)
            world.setState(self.human, 'locvisits_' + loc, 1)
            world.agents[self.human].setBelief(stateKey(self.human, 'locvisits_' + loc), 1)
            start = 1

        t = start
        while True:
            if (t >= end) or (t >= len(self.actions)):
                break

            actStruct = self.actions[t]
            actType = actStruct[0]
            act = actStruct[1][0]
            testbedMsgId = actStruct[-2]
            trueTime = actStruct[-1]
            timeInSec = 600 - (trueTime[0] * 60) - trueTime[1]

            self.logger.info('%d) Running msg %d: %s' % (t + start, testbedMsgId, ','.join(map(str, actStruct[1]))))

            # before any action, manually sync the time feature with the game's time (invert timer)
            world.setFeature(stateKey(WORLD, 'seconds'), timeInSec, recurse=True)

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
                clock = stateKey(WORLD, 'seconds')
                curTime = world.getState(WORLD, 'seconds', unique=True)
                newTime = curTime + dur
                selDict[clock] = newTime
                self.logger.debug('Time now %d triage until %d' % (curTime, newTime))

            t = t + 1
            self.logger.info('Injecting %s' % (selDict))
            # selDict = {k: world.value2float(k, v) for k, v in selDict.items()}
            world.step(act, select=selDict, threshold=prune_threshold)
            world.modelGC()

            self.summarizeState(world, trueTime)
            if self.processor is not None:
                self.processor.post_step(world, None if act is None else world.getAction(self.human))

            if t + start - 1 > ffwdTo:
                input('press any key.. ')

    def summarizeState(self, world, ttime):
        loc = world.getState(self.human, 'loc', unique=True)
        time = 600 - world.getState(WORLD, 'seconds', unique=True)
        self.logger.info('psim Time: %s' % ([int(time / 60), time % 60]))
        self.logger.info('True Time: %s' % (ttime))
        self.logger.info('Phase: %s' % (world.getState(WORLD, 'phase', unique=True)))

        self.logger.info('Player location: %s' % (loc))
        clrs = [GOLD_STR, GREEN_STR, WHITE_STR]
        for clr in clrs:
            self.logger.debug('%s count: %s' % (clr, world.getState(WORLD, 'ctr_' + loc + '_' + clr, unique=True)))
        self.logger.info('Visits: %d' % (world.getState(self.human, 'locvisits_' + loc, unique=True)))
        self.logger.info('JustSavedGr: %s' % (world.getState(self.human, 'numsaved_Green', unique=True)))
        self.logger.info('JustSavedGd: %s' % (world.getState(self.human, 'numsaved_Gold', unique=True)))

# f = open('/home/mostafh/Documents/psim/new_atomic/atomic/data/tryj', 'rt')
# lines = f.readlines()
# jsonIter = ite([m.mdict for m in reader.messages])
# jsonParser = ProcessParsedJson()
# jsonParser.processJson(jsonIter, 100)
