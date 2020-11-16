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

MOVE = 0
TRIAGE = 1
SEARCH = 2
TOGGLE_LIGHT = 3
BEEP = 4

class ProcessParsedJson(object):

    def __init__(self, humanName, world_map, victimsObj, logger=logging):
        self.human = humanName
        self.world_map = world_map
        self.victimsObj = victimsObj
        self.logger = logger
                
        self.lastParsedLoc = None
        self.lastParsedClrInFOV = None
        self.triageStartTime = 0
        self.actions = []

###############################################
#######  Message handlers
###############################################

    def parseTriageStart(self, vicColor, ts):
        self.logger.debug('triage started of %s at %s' % (vicColor, ts))
        self.triageStartTime = ts
    
    def parseTriageEnd(self, vicColor, isSuccessful, msgIdx, ts):
        self.logger.debug('triage ended of %s at %s' % (vicColor, ts))
        originalDuration = (ts[0]*60 + ts[1]) - (self.triageStartTime[0]*60 + self.triageStartTime[1])

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
            if vicColor == 'Green':
                duration = min(originalDuration, 7)
            else:
                duration = min(originalDuration, 14)
        
        triageAct = self.victimsObj.getTriageAction(self.human, vicColor)
        ## Record it as happening at self.triageStartTime
        self.actions.append([TRIAGE, [triageAct, duration], msgIdx, self.triageStartTime])
    
    def parseMove(self, newRoom, msgIdx, ts):
        if self.lastParsedLoc == None:
            self.actions.append(newRoom) 
            self.lastParsedLoc = newRoom
            self.logger.debug('moved to %s at %s' % (self.lastParsedLoc, ts))
            return
        
        # Add one or more move actions
        mv = self.world_map.getMoveAction(self.human, self.lastParsedLoc, newRoom)
        if mv == []:
            self.logger.error('unreachable %s to %s at %s' % (self.lastParsedLoc, newRoom, ts))
            self.lastParsedLoc = newRoom
            return

        for m in mv:
            self.actions.append([MOVE, mv, msgIdx, ts]) 
        self.logger.debug('moved to %s at %s' % (newRoom, ts))
        self.lastParsedLoc = newRoom
        ## Clear the last seen victim color!
        self.lastParsedClrInFOV = 'none'
        

    def parseLight(self, loc, msgIdx, ts):
        action = self.world_map.lightActions[self.human]
        self.actions.append([TOGGLE_LIGHT, [action], msgIdx, ts])        
        
    def parseBeep(self, msg, SandRVics, msgIdx, ts):
        numBeeps= len(msg['message'].split())
        targetRoom = msg['room_name']
        
        if targetRoom not in SandRVics.keys():
            self.logger.error('%d Beeps from %s but no victims at %s' % (numBeeps, targetRoom, ts))
            return 1
        
        cond1 = (numBeeps == 1) and 'Green' in SandRVics[targetRoom] and 'Gold' not in SandRVics[targetRoom]
        cond2 = (numBeeps == 2) and 'Gold' in SandRVics[targetRoom]        
        if not (cond1 or cond2):
            self.logger.error('%d Beep from %s but wrong victims %s' % (numBeeps, targetRoom, SandRVics[targetRoom]))
            return 1
        
        direction = self.world_map.getDirection(self.lastParsedLoc, targetRoom)
        if len(direction) > 1:
            self.logger.error('In %s beep from %s %d steps away at %s' % (self.lastParsedLoc, targetRoom, len(direction), ts))
            return 1
        if direction[0] == -1:
            self.logger.error('In %s beep from %s UNCONNECTED at %s' % (self.lastParsedLoc, targetRoom, ts))
            return 1
        self.logger.debug('Heard %d beeps from %s at %s' % (numBeeps, targetRoom, ts))
        direc = Directions(direction[0]).name
        sensorKey = stateKey(self.human, 'sensor_'+direc)
        self.actions.append([BEEP, [sensorKey, str(numBeeps)], msgIdx, ts])
        return 0

    def parseFOV(self, colors, msgIdx, ts):
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
        
    def processJson(self, jsonMsgIter, SandRVics, ffwd = 0, maxActions = -1):
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
            if numMsgs >= ffwd:
                input('press any key.. ')
            
            if mtype == 'Event:Triage':
                tstate = m['triage_state']
                vicColor = m['color']
                if vicColor == 'Yellow':
                    vicColor = 'Gold'
                if m['room_name'] != self.lastParsedLoc:
                    self.logger.error('Triaging in ' + m['room_name'] + ' but I am in ' + self.lastParsedLoc + ' at ' + mtime)
                    
                if tstate == 'IN_PROGRESS':
                    self.parseTriageStart(vicColor, ts)
                    triageInProgress = True
                else:
                    success = (tstate == 'SUCCESSFUL')
                    self.parseTriageEnd(vicColor, success, numMsgs, ts)
                    triageInProgress = False
                    
            elif mtype == 'Event:Beep':                
                self.parseBeep(m, SandRVics, numMsgs, ts)
                    
            elif mtype == 'FoV':
                ## Ignore 'looking' at victims while you're triaging
                if not triageInProgress:
                    self.parseFOV(m['victim_list'], numMsgs, ts)
            
            elif mtype == 'Event:Location':
                if triageInProgress:
                    self.logger.error('At %s msg %d walked out of room while triaging' % (m['mission_timer'], numMsgs))
                    triageInProgress = False
                loc = m['room_name']
                self.parseMove(loc, numMsgs, ts)
                
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
        while True:
            if t == end:
                break
            
            actStruct = self.actions[t]            
            actType = actStruct[0]
            act = actStruct[1][0]
            testbedMsgId = actStruct[-2]
            trueTime = actStruct[-1]
            
            self.logger.info('%d) Running msg %d: %s' % (t + start, testbedMsgId, ','.join(map(str, actStruct[1]))))
                
            ## Force no beeps (unless overwritten later)
            selDict = {stateKey(self.human, 'sensor_'+d.name):'none' for d in Directions}
            if act not in world.agents[self.human].getLegalActions():
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
                if permissive and color != 'none' and world.getState(WORLD, 'ctr_{}_{}'.format(self.lastParsedLoc, color),
                                                                     unique=True) == 0:
                    # Observed a victim who should not be here
                    self.logger.warning('In {}, a nonexistent {} victim entered the FOV'.format(self.lastParsedLoc, color))
                    continue
                
            t = t+1
            ## After you parse an action, skip ahead to overwrite 'none' beeps with heard beeps.
            while (t < len(self.actions)) and (self.actions[t][0] == BEEP):
                [sensorKey, value] = self.actions[t][1]
                selDict[sensorKey] = value
                t = t+1
            self.logger.info('Injecting %s' %(selDict))
                    
            selDict = {k: world.value2float(k, v) for k,v in selDict.items()}
            self.pre_step(world)
            world.step(act, select=selDict, threshold=prune_threshold)                    
            self.post_step(world, None if act is None else world.getAction(self.human))
            self.summarizeState(world, trueTime)
            
            if t + start >= ffwdTo:
                input('press any key.. ')
            
    
    def summarizeState(self, world, ttime):
        loc = world.getState(self.human, 'loc', unique=True)
        time = 600 - world.getState(WORLD, 'seconds', unique=True)
        self.logger.info('psim Time: %s' % ([int(time/60), time%60]))
        self.logger.info('True Time: %s' % (ttime))
    
        self.logger.info('Player location: %s' % (loc))
        clrs = ['Green', 'Gold', 'Red', 'White']
        for clr in clrs:
            self.logger.debug('%s count: %s' % (clr, world.getState(WORLD, 'ctr_' + loc + '_' + clr, unique=True)))
        self.logger.info('FOV: %s' % (world.getState(self.human, 'vicInFOV', unique=True)))
        self.logger.info('Visits: %d' % (world.getState(self.human, 'locvisits_' + loc, unique=True)))
        self.logger.info('JustSavedGr: %s' % (world.getState(self.human, 'numsaved_Green', unique=True)))
        self.logger.info('JustSavedGd: %s' % (world.getState(self.human, 'numsaved_Gold', unique=True)))


#f = open('/home/mostafh/Documents/psim/new_atomic/atomic/data/tryj', 'rt')
#lines = f.readlines()
#jsonIter = ite([m.mdict for m in reader.messages])
#jsonParser = ProcessParsedJson()
#jsonParser.processJson(jsonIter, 100)
