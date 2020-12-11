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
from atomic.definitions import Directions
from atomic.parsing.message_reader import getMessages

MOVE = 0
TRIAGE = 1
SEARCH = 2
TOGGLE_LIGHT = 3
BEEP = 4


class ProcessParsedJson(object):

    def __init__(self, filename, map_data, logger=logging, unusedMaxDist=0):
        self.logger = logger
        self.lastParsedLoc = None
        self.lastParsedClrInFOV = None
        self.triageStartTime = 0
        self.actions = []
        self.locations = set()
        if len(filename) > 0:
            inputFiles = {
                '--msgfile': filename,
                '--roomfile': map_data.room_file,
                '--portalfile': map_data.portals_file,
                '--victimfile' : map_data.victim_file
            }
            self.allMs, self.human = getMessages(inputFiles)
            self.human = self.allMs[1]['playername']
        
    def useParsedFile(self, msgfile):
        self.allMs = []
        jsonfile = open(msgfile, 'rt')
        for line in jsonfile.readlines():
            self.allMs.append(json.loads(line))
        self.human = self.allMs[1]['playername']

    def player_name(self):
        return self.human

    ###############################################
    #######  Message handlers
    ###############################################

    def injectFOVIfNeeded(self, vicColor, ts):
        ## If color in FOV not what you're trying to triage, inject a FoV message
        if self.lastParsedClrInFOV != vicColor:
            self.logger.error('Injecting search action to look before triage at %s at %s' % (vicColor, ts))
            self.parseFOV([vicColor], -1, ts)

    def parseTriageStart(self, vicColor, ts):
        self.injectFOVIfNeeded(vicColor, ts)
        self.logger.debug('triage started of %s at %s' % (vicColor, ts))
        self.triageStartTime = ts

    def parseTriageEnd(self, vicColor, isSuccessful, msgIdx, ts):
        self.injectFOVIfNeeded(vicColor, ts)

        self.logger.debug('triage ended of %s at %s' % (vicColor, ts))
        
        ## IGNORE what I think about the duration being enough
        ## Adopt success/failure reported in message!
        #        duration, success = self.getTriageDuration(vicColor, originalDuration)
        #        self.logger.debug('Orig dur %d quantized %d' % (originalDuration, duration))
        #        if success != isSuccessful:
        #            self.logger.error('Triage succes in data %s but by duration %s' % (isSuccessful, success) )

        ## If reported as successful, force duration to be long enough
        if isSuccessful:
            if vicColor == 'Green':
                duration = 8
            else:
                duration = 15
            ## Reset the FoV we're tracking
            self.lastParsedClrInFOV = 'White'
        ## Otherwise use actual duration capped by long enough duration
        else:
            duration = 5

        ## Update the parser's version of victims in each room
        if isSuccessful:
            self.roomToVicDict[self.lastParsedLoc].remove(vicColor)

        triageAct = self.victimsObj.getTriageAction(self.human, vicColor)
        ## Record it as happening at self.triageStartTime
        self.actions.append([TRIAGE, [triageAct, duration], msgIdx, self.triageStartTime])

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
        ## Clear the last seen victim color!
        self.lastParsedClrInFOV = 'none'
        return 0

    def parseLight(self, loc, msgIdx, ts):
        action = self.world_map.lightActions[self.human]
        self.actions.append([TOGGLE_LIGHT, [action], msgIdx, ts])

    def parseBeep(self, msg, msgIdx, ts):
        numBeeps = len(msg['message'].split())
        targetRoom = msg['room_name']

        if targetRoom not in self.roomToVicDict.keys():
            self.logger.error('%d Beeps from %s but no victims at %s' % (numBeeps, targetRoom, ts))
            return 1
        victims = self.roomToVicDict[targetRoom]
        cond1 = (numBeeps == 1) and 'Green' in victims and 'Gold' not in victims
        cond2 = (numBeeps == 2) and 'Gold' in victims
        if not (cond1 or cond2):
            self.logger.error('%d Beep from %s but wrong victims %s' % (numBeeps, targetRoom, victims))
            return 1

        direction = self.world_map.getDirection(self.lastParsedLoc, targetRoom)
        if len(direction) > 1:
            self.logger.error(
                'In %s beep from %s %d steps away at %s' % (self.lastParsedLoc, targetRoom, len(direction), ts))
            return 1
        if direction[0] == -1:
            self.logger.error('In %s beep from %s UNCONNECTED at %s' % (self.lastParsedLoc, targetRoom, ts))
            return 1
        self.logger.debug('Heard %d beeps from %s at %s' % (numBeeps, targetRoom, ts))
        direc = Directions(direction[0]).name
        sensorKey = stateKey(self.human, 'sensor_' + direc)
        self.actions.append([BEEP, [sensorKey, str(numBeeps)], msgIdx, ts])
        return 0

    def parseFOV(self, origColors, msgIdx, ts):
        ## Filter our victims that are no longer in the room
        colors = [c for c in origColors if c in self.roomToVicDict[self.lastParsedLoc]]
        if len(colors) < len(origColors):
            self.logger.error('%s in FOV but not in %s at %s idx %d' % (origColors, self.lastParsedLoc, ts, msgIdx))

        ## TODO what if multiple victims in FOV
        if len(colors) > 0:
            found = colors[0]
        else:
            found = 'none'
        #        if found != 'none' and found not in SandRVics[self.lastParsedLoc]:
        #            return
        # If you're seeing a new color (including none)
        if found != self.lastParsedClrInFOV:
            self.logger.debug('Searched and found %s at %s' % (found, ts))
            self.actions.append([SEARCH, [self.victimsObj.getSearchAction(self.human), found], msgIdx, ts])
            self.lastParsedClrInFOV = found

    def getTriageDuration(self, color, originalDuration):
        success = False
        if originalDuration <= 7:
            duration = 5
        elif (originalDuration > 7) and (originalDuration < 15):
            if color == 'Green':
                duration = 8
                success = True
            else:
                duration = 5
        elif originalDuration >= 15:
            success = True
            if color == 'Green':
                duration = 8
            else:
                duration = 15
        return duration, success

    ###############################################
    #######  Processing the json messages
    ###############################################

    def getActionsAndEvents(self, victims, world_map, SandRVics, ffwd=0, maxActions=-1):
        jsonMsgIter = iter(self.allMs)
        self.world_map = world_map
        self.victimsObj = victims
        self.roomToVicDict = dict(SandRVics)
        numMsgs = 0
        m = next(jsonMsgIter)
        ignore = ['Mission:VictimList', 'Event:Door']
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
            if ffwd > 0 and numMsgs >= ffwd:
                input('press any key.. ')

            if mtype == 'Event:Triage':
                tstate = m['triage_state']
                vicColor = m['color']
                if vicColor == 'Yellow':
                    vicColor = 'Gold'
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

            elif mtype == 'Event:Beep':
                ret = self.parseBeep(m, numMsgs, ts)
                if ret > 0:
                    self.logger.error('That was msg %d' % (numMsgs))

            elif mtype == 'FoV':
                ## Ignore 'looking' at victims while you're triaging
                if not triageInProgress:
                    self.parseFOV(m['victim_list'], numMsgs, ts)

            elif mtype == 'Event:Location':
                if triageInProgress:
                    self.logger.error('At %s msg %d walked out of room while triaging' % (m['mission_timer'], numMsgs))
                    triageInProgress = False
                loc = m['room_name']
                ret = self.parseMove(loc, numMsgs, ts)
                if ret > 0:
                    self.logger.error('That was msg %d' % (numMsgs))

            elif mtype == 'Event:Lever':
                if triageInProgress:
                    self.logger.error('At %s msg %d flipped a light while triaging' % (m['mission_timer'], numMsgs))
                    triageInProgress = False
                #  is_powered:false then the player has just turned that light switch on
                self.parseLight(loc, numMsgs, ts)

            elif mtype == 'Event:Door':
                pass

            m = next(jsonMsgIter, None)
            numMsgs = numMsgs + 1
        self.locations = list(self.locations)

    ###############################################
    #######  Running the actions we collected
    ###############################################

    def pre_step(self, world):
        pass

    def post_step(self, world, act):
        pass

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
        timeKey = stateKey(WORLD, 'seconds')
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

            ## Force no beeps (unless overwritten later)
            selDict = {stateKey(self.human, 'sensor_' + d.name): 'none' for d in Directions}
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

            if actType == SEARCH:
                color = actStruct[1][1]
                selDict[stateKey(self.human, 'vicInFOV')] = color
                if permissive and color != 'none' and world.getState(WORLD,
                                                                     'ctr_{}_{}'.format(self.lastParsedLoc, color),
                                                                     unique=True) == 0:
                    # Observed a victim who should not be here
                    self.logger.warning(
                        'In {}, a nonexistent {} victim entered the FOV'.format(self.lastParsedLoc, color))
                    continue

            t = t + 1
            ## After you parse an action, skip ahead to overwrite 'none' beeps with heard beeps.
            while (t < len(self.actions)) and (self.actions[t][0] == BEEP):
                [sensorKey, value] = self.actions[t][1]
                selDict[sensorKey] = value
                t = t + 1
            self.logger.info('Injecting %s' % (selDict))

            selDict = {k: world.value2float(k, v) for k, v in selDict.items()}
            self.pre_step(world)
            world.step(act, select=selDict, threshold=prune_threshold)            
            self.post_step(world, None if act is None else world.getAction(self.human))
            self.summarizeState(world, trueTime)

            if t + start >= ffwdTo:
                input('press any key.. ')

    def summarizeState(self, world, ttime):
        loc = world.getState(self.human, 'loc', unique=True)
        time = 600 - world.getState(WORLD, 'seconds', unique=True)
        self.logger.info('psim Time: %s' % ([int(time / 60), time % 60]))
        self.logger.info('True Time: %s' % (ttime))

        self.logger.info('Player location: %s' % (loc))
        clrs = ['Green', 'Gold', 'Red', 'White']
        for clr in clrs:
            self.logger.debug('%s count: %s' % (clr, world.getState(WORLD, 'ctr_' + loc + '_' + clr, unique=True)))
        self.logger.info('FOV: %s' % (world.getState(self.human, 'vicInFOV', unique=True)))
        self.logger.info('Visits: %d' % (world.getState(self.human, 'locvisits_' + loc, unique=True)))
        self.logger.info('JustSavedGr: %s' % (world.getState(self.human, 'numsaved_Green', unique=True)))
        self.logger.info('JustSavedGd: %s' % (world.getState(self.human, 'numsaved_Gold', unique=True)))

# f = open('/home/mostafh/Documents/psim/new_atomic/atomic/data/tryj', 'rt')
# lines = f.readlines()
# jsonIter = ite([m.mdict for m in reader.messages])
# jsonParser = ProcessParsedJson()
# jsonParser.processJson(jsonIter, 100)
