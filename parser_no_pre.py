#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 20:35:23 2020

@author: mostafh
"""
import logging
import pandas as pd
from model_learning.trajectory import copy_world, get_agent_action
from locations_no_pre import Locations
from psychsim.action import ActionSet
from psychsim.pwl import stateKey
import numpy as np
from psychsim.world import WORLD

class DataParser:
    ACTION = 0
    SET_FLG = 1
    SEARCH = 3
    

    def __init__(self, filename, maxDist=5, logger=logging):
        self.maxDist = maxDist
        if filename.endswith('xlsx'):
            self.data = pd.read_excel(filename)
        elif filename.endswith('csv'):
            self.data = pd.read_csv(filename)
        self.maxVicsInLoc = self.data['num_victims'].max()

        self.cols = [
                    'Room_in',
                    'num_victims',
                    'isAVicInFOV',
                    'event_triage_victim_id',
                    'triage_in_progress',
                    'triage_result']
        
        self.logger = logger

        for iv in range(self.maxVicsInLoc):
            self.cols = self.cols + [
                    'victim_'+str(iv)+'_id',
                    'victim_'+str(iv)+'_color',
                    'victim_'+str(iv)+'_in_FOV']

        # Remove rows w/o locations
        self.logger.info('Number of rows %d' % (len(self.data)))
        self.data.dropna(axis=0, subset=['Room_in'], inplace=True)
        self.data= self.data.loc[self.data['Room_in']!='None',:]
        self.logger.info('Number of rows after empty room removal %d' % (len(self.data)))
        
        # Remove in_progress rows that were never back-filled
        self.data= self.data.loc[self.data['triage_result']!='IN_PROGRESS',:]
        self.logger.info('Number of rows after triage in progress removal %d' % (len(self.data)))
        
        # Remove triage_in_progress rows where victim being triaged different from victim in CH
        triageOn = self.data['triage_in_progress'] == True
        sameVic = self.data['event_triage_victim_id']==self.data['victim_in_crosshair_id']
        self.data= self.data.loc[~triageOn | sameVic,:]
        self.logger.info('Number of rows after inconsistent triage vic and CH removal %d' % (len(self.data)))
        
        # Rooms with numeric names: Prepend 'R'
        mask = self.data['Room_in'].str.startswith('2')
        newRoom = 'R' + self.data['Room_in']
        self.data.loc[mask, 'Room_in'] = newRoom.loc[mask]
        self.data['Room_in'] = self.data['Room_in'].astype(str)
                
        # Remove 'd' or 'x' at the end of room names
        rooms = [str(loc) for loc in self.data['Room_in'].unique()]
        newRooms = {r:r for r in rooms if not (r.endswith('x') or r.endswith('d'))}
        newRooms.update({r:r[:-1] for r in rooms if r.endswith('x') or r.endswith('d')})
        self.data['Room_in'].replace(newRooms, inplace=True)

        ## Create flag for whether any victim is in FOV
        self.data['isAVicInFOV'] = self.data['victim_0_in_FOV']
        for iv in range(1, self.maxVicsInLoc):
            self.data['isAVicInFOV'] = self.data['isAVicInFOV'] | self.data['victim_'+str(iv)+'_in_FOV']
        
        manyInFov = self.data['victim_0_in_FOV'] 
        for iv in range(1, self.maxVicsInLoc):
            manyInFov = manyInFov & self.data['victim_'+str(iv)+'_in_FOV']
        if sum(manyInFov) > 0:
            self.logger.warning('%d rows with multiple victims in FOV' % (sum(manyInFov)))

        # Collect names of locations
        self.locations = [str(loc) for loc in self.data['Room_in'].unique()]
        
#        fstr1 = '%Y-%m-%dT%H:%M:%S.%fZ'
#        fstr2 = '%Y-%m-%dT%H:%M:%SZ'
#            self.data['dtime'] = pd.to_datetime(self.data['@timestamp'], format=fstr1, exact=False)
        self.data['dtime'] = pd.to_datetime(self.data['@timestamp'], infer_datetime_format=True, exact=False)
        startTime = self.data['dtime'].iloc[0]
        
        self.data['seconds'] = np.ceil((self.data['dtime'] - startTime) / np.timedelta64(1, 's'))
    
    def parseFOV(self, row, newRoom, prevRow, printTrace, human, searchActs):
        ''' For each victim, if in distance range, add approach action        
        '''
        someoneInFOV= row['isAVicInFOV']
        for vi in range(self.maxVicsInLoc):
            color = row['victim_'+str(vi)+'_color']
            inFov = row['victim_' + str(vi) + '_in_FOV']
            if not prevRow.empty:
                prevFOV = prevRow['victim_' + str(vi) + '_in_FOV']
            
            if newRoom or (not prevFOV):
                if inFov:  #this dude just got into my FOV because of a search action
                    searchActs.append([self.victimsObj.getSearchAction(human), color])
                    self.logger.debug('Searched and found %s' % (color))
            else: # same room and previously in FOV
                # Either remain in FOV ==> noop
                # Or search action found: a) another victim ==> search action injected in another iteration of vi
                # or b) none  ==> set approached to none outside the loop
                pass
            
        if prevRow.empty:
            prevSomeone = False
        else:
            prevSomeone = prevRow['isAVicInFOV']
        if prevSomeone and (not someoneInFOV) and (not newRoom):
            searchActs.append([self.victimsObj.getSearchAction(human), 'none'])
            self.logger.debug('Searched and found none')

    def getFOVColor(self, row):
        for vi in range(self.maxVicsInLoc):
            if row['victim_' + str(vi) + '_in_FOV']:
                return row['victim_'+str(vi)+'_color']
    
    def getDurationIfTriaging(self, row, originalDuration):        
        # Quantize duration to 5, 8 or 15
        if not row['triage_in_progress']:
            return originalDuration
        
        fovColor = self.getFOVColor(row)
        if originalDuration<=7:
            duration = 5
        elif (originalDuration > 7) and (originalDuration < 15):
            if fovColor == 'Green':
                duration = 8
            else:
                duration = 5
        elif originalDuration >= 15:
            if fovColor == 'Green':
                duration = 8
            else:
                duration = 15
        return duration

    def getActionsAndEvents(self, human, printTrace=False, maxEvents=-1):
        self.pData = self.data.loc[self.data['player_ID'] == human]
        
        self.logger.warning('Locations in player data but not map %s' % (','.join(sorted([l for l in self.data['Room_in'].unique() if not l in Locations.AllLocations]))))
        
        ## Sort by time
        self.pData = self.pData.loc[:, ['@timestamp', 'seconds'] + self.cols].sort_values('@timestamp', axis = 0)

        self.pData.to_csv('debug.csv')

        ## Drop consecutive duplicate entries (ignoring the timestamp)
        self.pData = self.pData.loc[(self.pData[self.cols].shift() != self.pData[self.cols]).any(axis=1)]
        self.logger.info('Dropped duplicates. Down to %d' % (len(self.pData)))
        
        self.pData['duration'] = - self.pData['seconds'].diff(periods=-1)

        prev = pd.Series()
        lastLoc = None
        actsAndEvents = []
        attemptID = 0
        for ir,row in self.pData.iterrows():
            if (maxEvents > 0) and (len(actsAndEvents) > maxEvents):
                break
            triageActs = []
            events = []
            moveActs = []
            searchActs = []
            stamp = row['@timestamp']
            duration = row['duration']
            duration = self.getDurationIfTriaging(row, duration)
                        
            self.logger.debug('---- %s dur %s %s' % (row['seconds'], duration, np.sum([a[3] for a in actsAndEvents[:]])))
                
            # Entered a new room.
            if row['Room_in'] != lastLoc:
                if lastLoc == None:
                    # First elements in actions is the intial location
                    moveActs = [row['Room_in']]
                else:
                    # Add a move action
                    mv = Locations.getMoveAction(human, lastLoc, row['Room_in'])
                    if mv == []:
                        self.logger.warning('unreachable %s %s %s' % (lastLoc, row['Room_in'], row['@timestamp']))
#                        ## Transport player to new location by force
#                        events.append(['loc', row['Room_in']])
                        continue                        
                    for m in mv:
                        moveActs.append(m)

                lastLoc = row['Room_in']
                self.logger.debug('moved to %s %s' % (lastLoc, stamp))

                self.parseFOV(row, True, prev, printTrace, human, searchActs)
                
                # Is a TIP in this new room? 
                if row['triage_in_progress']:
                    ## event_triage_victim_id
                    fovColor = self.getFOVColor(row)
                    triageAct = self.victimsObj.getTriageAction(human, fovColor)
                    triageActs.append([triageAct, duration])
                    self.logger.debug('triage started in new room')

            # same room. Compare flag values to know what changed!
            else:
                self.parseFOV(row, False, prev, printTrace, human, searchActs)
                                
                # If TIP changed
                tip = 'triage_in_progress'
                tstatus = 'triage_result'
                if (row[tip] != prev[tip]) or (row[tstatus] != prev[tstatus]):
                    if row[tip]:
                        fovColor = self.getFOVColor(row)
                        triageAct = self.victimsObj.getTriageAction(human, fovColor)
                        triageActs.append([triageAct, duration])
                        self.logger.debug('triage started')
                    if prev[tip]:
                        attemptID = attemptID  + 1

            ## Inject move action(s), then events, then crosshair/approach actions
            ## If we have move act(s), the first one take all duration and the rest 0
            for i, mact in enumerate(moveActs):
                dur = 0
                if i == 0:
                    dur = duration
                    duration = 0
                actsAndEvents.append([DataParser.ACTION, [mact], stamp, dur, attemptID])
            for i, sact in enumerate(searchActs):
                dur = 0
                if i == 0:
                    dur = duration
                    duration = 0
                ## Enforce the value in the data on actions that don't otherwise affect approached victim                
                actsAndEvents.append([DataParser.SEARCH, sact, stamp, dur, attemptID])
            # acts = triage 
            for i, act in enumerate(triageActs):
                ## Enforce the value in the data on actions that don't otherwise affect approached victim                
                actsAndEvents.append([DataParser.ACTION, act, stamp, duration, attemptID]) 
                duration = 0
                
            for ev in events:
                dur = 0
                if i == 0:
                    dur = duration
                    duration = 0
                actsAndEvents.append([DataParser.SET_FLG, ev, stamp, dur, attemptID])
            
            prev = row
        return actsAndEvents, self.pData

    def getTimelessAttempt(world, human, actsAndEvents, attemptID):
        attemptRows = [ae for ae in actsAndEvents if ae[-1] == attemptID]
        return attemptRows

    @staticmethod
    def runTimeless(world, human, actsAndEvents, start, end, ffwdTo=0,
                    trajectory=None, prune_threshold = None, logger=logging):
        """
        Run actions and flag resetting events in the order they're given. No notion of timestamps
        :param trajectory: optional list in which to store history of simulation states for further processing.
        :return: trajectory if provided; otherwise, None
        :rtype: list
        """

        logger.debug(actsAndEvents[start])
        if start == 0:
            [actOrEvFlag, actEv, stamp, duration, attempt] = actsAndEvents[0]
            if actOrEvFlag == DataParser.SET_FLG:
                varName = actEv[0]
                varValue = actEv[1]
                world.setState(human, varName, varValue)
                world.agents[human].setBelief(stateKey(human,varName),varValue)
            else:
                # This first action can be an actual action or an initial location
                if type(actEv) == ActionSet:
                    world.step(actEv)
                else:
                    world.setState(human, 'loc', actEv[0])
                    world.agents[human].setBelief(stateKey(human,'loc'),actEv[0])
                    world.setState(human, 'locvisits_'+actEv[0], 1)
                    world.agents[human].setBelief(stateKey(human,'locvisits_'+actEv[0]),1)
            start = 1                

        for t,actEvent in enumerate(actsAndEvents[start:end]):
            prev_world = copy_world(world)
            act = None
            logger.info('%d) Running: %s' % (t+start, ','.join(map(str,actEvent[1]))))
            if t+start >= ffwdTo:
                input('press any key.. ')
            if actEvent[0] == DataParser.ACTION:
                act = actEvent[1][0]
                if act not in world.agents[human].getLegalActions():
                    raise ValueError('Illegal action!')
                if len(actEvent[1]) > 1:
                    dur = actEvent[1][1]
                    # This is a triage action with an associated duration
                    clock = stateKey(WORLD,'seconds')
                    curTime = world.getState(WORLD,'seconds',unique=True)
                    newTime = curTime + dur
                    selDict = {clock:newTime}
                    logger.debug('Time now %d triage until %d' % (curTime,newTime))
                    world.step(act, select=selDict, threshold=prune_threshold)
                else:
                    world.step(act, threshold=prune_threshold)
                
            elif actEvent[0] == DataParser.SET_FLG:
                [var, val] = actEvent[1]
                key = stateKey(human,var)
                world.state[key] = world.value2float(key,val)
                for model in world.getModel(human).domain():
                    if val not in world.getFeature(key,world.agents[human].models[model]['beliefs']).domain():
                        raise ValueError('Unbelievable data point at time %s: %s=%s' % (actEvent[2],var,val))
                    world.agents[human].models[model]['beliefs'][key] = world.value2float(key,val)
                
            elif actEvent[0] == DataParser.SEARCH:
                act, color = actEvent[1][0], actEvent[1][1]
                k = stateKey(human, 'vicInFOV')
                selDict = {k:world.value2float(k, color)}
                world.step(act, select=selDict, threshold=prune_threshold)
            summarizeState(world,human,logger)

            if trajectory is not None and act is not None:
                trajectory.append((prev_world, get_agent_action(world.agents[human], world.state)))

    def player_name(self):
        """
        :return: the name of the human player in this log file
        :rtype: str
        """
        return self.data['player_ID'].iloc[0]

def printAEs(aes,logger=logging):
    for ae in aes:
        logger.info('%s %s' % (ae[2], ae[1]))
                

def summarizeState(world,human,logger=logging):
    loc = world.getState(human,'loc',unique=True)
    time = world.getState(WORLD,'seconds',unique=True)
    logger.info('Time: %d' % (time))
    
    logger.info('Player location: %s' % (loc))
    clrs = ['Green', 'Gold', 'Red', 'White']
    for clr in clrs:
        logger.debug('%s count: %s' % (clr,world.getState(WORLD, 'ctr_' + loc + '_' + clr,unique=True)))
    logger.info('FOV: %s' % (world.getState(human,'vicInFOV',unique=True)))
    logger.info('Visits: %d' % (world.getState(human,'locvisits_'+loc,unique=True)))
    logger.info('JustSavedGr: %s' % (world.getState(human,'numsaved_Green',unique=True)))
    logger.info('JustSavedGd: %s' % (world.getState(human,'numsaved_Gold',unique=True)))
