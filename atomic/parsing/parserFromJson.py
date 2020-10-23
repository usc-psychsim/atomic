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

    def parseTriageStart(self, ts):
        self.triageStartTime = ts
    
    def parseTriageEnd(self, vicColor, isSuccessful, ts):
        self.logger.debug('triage ended of %s %s' % (vicColor, ts))
        originalDuration = ts - self.triageStartTime
        duration, success = self.getTriageDuration(vicColor, originalDuration)
        
        if success != isSuccessful:
            self.logger.error('Triage succes in data %s but by duration %s' % (isSuccessful, success) )
        
        triageAct = self.victimsObj.getTriageAction(self.human, vicColor)
        self.actions.append([TRIAGE, [triageAct, duration], ts])
    
    def parseMove(self, newRoom, ts):
        if self.lastParsedLoc == None:
            self.actions.append(newRoom) 
            return
        
        # Add one or more move actions
        self.lastParsedLoc = newRoom
        mv = self.world_map.getMoveAction(self.human, self.lastParsedLoc, newRoom)
        if mv == []:
            self.logger.error('unreachable %s %s %s' % (self.lastParsedLoc, newRoom, ts))
            return

        for m in mv:
            self.actions.append([MOVE, mv, ts]) 
        self.logger.debug('moved to %s %s' % (self.lastParsedLoc, ts))


    def parseLight(self, loc, ts):
        action = self.world_map.lightActions[self.human]
        self.actions.append([TOGGLE_LIGHT, [action], ts])
        
        
    def parseBeep(self, msg, ts):
        numBeeps= len(msg['message'].split())
        targetRoom = msg['room_name']
        direction = self.world_map.getDirection(self.lastParsedLoc, targetRoom)
        sensorKey = stateKey(self.human, 'sensor'+str(direction.value))
        self.actions.append([BEEP, [sensorKey, str(numBeeps)], ts])

    def parseFOV(self, colors, ts):
        ## TODO what if multiple victims in FOV
        ## TODO skip message with no change
        if len(colors) > 0:
            found = colors[0]            
        else:
            found = 'none'
        if found != self.lastParsedClrInFOV:
            self.logger.debug('Searched and found ' + found)
            self.actions.append([SEARCH, [self.victimsObj.getSearchAction(self.human), found], ts])
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
        
    def processJson(self, jsonMsgIter, maxActions = -1):
        numMsgs = 0
        m = next(jsonMsgIter)
        while (m != None) and ((maxActions < 0) or (numMsgs < maxActions)):
            numMsgs = numMsgs + 1
            
            mtype = m['sub_type']
            print(numMsgs, mtype)
            input('press any key.. ')
            if mtype in ['Mission:VictimList']:
                m = next(jsonMsgIter)
                continue
            # mission_timer gives remaining time
            [mm, ss] = [int(x) for x in m['mission_timer'].split(':')]
            ## time elapsed in seconds
            ts = 10 * 60 - mm * 60 - ss
            
            if mtype == 'Event:Triage':
                tstate = m['triage_state']
                vicColor = m['color']
                if tstate == 'IN_PROGRESS':
                    self.parseTriageStart(ts)
                else:
                    success = (tstate == 'SUCCESSFUL')
                    self.parseTriageEnd(vicColor, success, ts)            
                    
            elif mtype == 'Event:Beep':
                self.parseBeep(m, ts)
                    
            elif mtype == 'FoV':
                colors = map(lambda x: 'Green' if x == 'block_victim_1'  else 'Yellow', m['victim_list'])
                self.parseFOV(list(colors), ts)
            
            elif mtype == 'Event:Location':
                loc = m['room_name']
                self.parseMove(loc, ts)
                
            elif mtype == 'Event:Lever':
                #  is_powered:false then the player has just turned that light switch on
                self.parseLight(loc, ts)
            
            elif mtype == 'Event:Door':
                pass
            
            m = next(jsonMsgIter)
        

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
            self.logger.info('%d) Running: %s' % (t + start, ','.join(map(str, actStruct[1]))))
            if t + start >= ffwdTo:
                input('press any key.. ')
                
            actType = actStruct[0]
            act = actStruct[1][0]
            ## Start with the assumption that you didn't hear any beeps in any direction
            selDict = {stateKey(self.human, 'sensor'+str(d.value)):'none' for d in Directions}
            
            if act not in world.agents[self.human].getLegalActions():
                raise ValueError('Illegal action!')
                
            if actType == MOVE:
                pass
                
            if actType == TRIAGE:
                dur = actStruct[1][1]
                clock = stateKey(WORLD, 'seconds')
                curTime = world.getState(WORLD, 'seconds', unique=True)
                newTime = curTime + dur
                selDict = {clock: newTime}
                self.logger.debug('Time now %d triage until %d' % (curTime, newTime))

            if actType == SEARCH:
                color = actStruct[1][1]
                k = stateKey(self.human, 'vicInFOV')
                selDict = {k: world.value2float(k, color)}                
                if permissive and color != 'none' and world.getState(WORLD, 'ctr_{}_{}'.format(self.lastParsedLoc, color),
                                                                     unique=True) == 0:
                    # Observed a victim who should not be here
                    self.logger.warning('In {}, a nonexistent {} victim entered the FOV'.format(self.lastParsedLoc, color))
                    continue
                
            t = t+1
            ## After you parse an action, skip ahead to overwrite 'none' beeps with heard beeps.
            while self.actions[t][0] == BEEP:
                [sensorKey, value] = self.actions[t][1]
                selDict[sensorKey] = value
                t = t+1
                    
            self.pre_step(world)
            world.step(act, select=selDict, threshold=prune_threshold)                    
            self.post_step(world, None if act is None else world.getAction(self.human))
            self.summarizeState(world)
            
    
    def summarizeState(self, world):
        loc = world.getState(self.human, 'loc', unique=True)
        time = world.getState(WORLD, 'seconds', unique=True)
        self.logger.info('Time: %d' % (time))
    
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
