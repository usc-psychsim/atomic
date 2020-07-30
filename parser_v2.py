#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 20:35:23 2020

@author: mostafh
"""
import logging
import pandas as pd
from victims_clr import Victims
from new_locations_fewacts import Locations
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
        self.cols = [
                    'Room_in',
                    'num_victims',
                    'victim_0_id',
                    'victim_1_id',
                    'victim_0_color',
                    'victim_1_color',
                    'v0_dist',
                    'v1_dist',
                    'isAVicInDist',
                    'victim_0_in_FOV',
                    'victim_1_in_FOV',
                    'isAVicInFOV',
                    'victim_in_crosshair_id',
                    'victim_in_cross_hair_color',
                    'event_triage_victim_id',
                    'triage_in_progress',
                    'triage_result']
        
        self.maxVicsInLoc = 2
        self.logger = logger

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
                
        # Rempve 'd' or 'x' at the end of room names
        rooms = [str(loc) for loc in self.data['Room_in'].unique()]
        newRooms = {r:r for r in rooms if not (r.endswith('x') or r.endswith('d'))}
        newRooms.update({r:r[:-1] for r in rooms if r.endswith('x') or r.endswith('d')})
        self.data['Room_in'].replace(newRooms, inplace=True)

        ## Create flag for whether each victim is within triage range
        for vi in range(self.maxVicsInLoc):
            self.data['v'+str(vi)+'_dist'] = (self.data['victim_'+str(vi)+'_dist'] > 0) & \
                                            (self.data['victim_'+str(vi)+'_dist'] <= self.maxDist)

        ## Create flag for whether any victim is in distance/FOV
        self.data['isAVicInDist'] = self.data['v0_dist'] | self.data['v1_dist']
        self.data['isAVicInFOV'] = self.data['victim_0_in_FOV'] | self.data['victim_1_in_FOV']
        
        manyApproached = self.data[self.data['v0_dist'] & self.data['v1_dist']]
        manyInFov = self.data[self.data['victim_0_in_FOV'] & self.data['victim_1_in_FOV']]
        if len(manyApproached) > 0:
            logger.warning('%d rows with multiple approached victims' % (len(manyApproached)))
        if len(manyInFov) > 0:
            logger.warning('%d rows with multiple victims in FOV' % (len(manyInFov)))

        # Collect names of locations
        self.locations = [str(loc) for loc in self.data['Room_in'].unique()]
        
#        fstr1 = '%Y-%m-%dT%H:%M:%S.%fZ'
#        fstr2 = '%Y-%m-%dT%H:%M:%SZ'
#            self.data['dtime'] = pd.to_datetime(self.data['@timestamp'], format=fstr1, exact=False)
        self.data['dtime'] = pd.to_datetime(self.data['@timestamp'], infer_datetime_format=True, exact=False)
        startTime = self.data['dtime'].iloc[0]
        
        self.data['seconds'] = round((self.data['dtime'] - startTime) / np.timedelta64(1, 's'))
        
    def parseApproach(self, row, newRoom, prevRow, printTrace, human, acts, events):
        ''' If victim in distance range and same victim in FOV, add deliberate approach action        
        If victim in distance range but not in FOV, add chance approach event
        If someone was within range, but currently no one is, set to none
        '''
        approachedColor = 'none'
        actionTaken = False
        for vi in range(self.maxVicsInLoc):
            color = row['victim_'+str(vi)+'_color']
            appr = row['v' + str(vi) + '_dist']
            if appr:
                approachedColor = color
            if not prevRow.empty:
                prevAppr = prevRow['v' + str(vi) + '_dist']
            inFov = row['victim_' + str(vi) + '_in_FOV']
            
            newlyApproached = newRoom or (not prevAppr)
            deliberate = appr and inFov            
            if newlyApproached and deliberate:
                acts.append(Victims.getPretriageAction(human, Victims.approachActs))
                actionTaken = True
                if printTrace:
                    self.logger.info('%s delib approach' % (color))
            else: # same room and previously approached
                # Either remain approached ==> noop
                # Or player moved away: a) to another victim ==> approached in another iteration of vi
                # or b) away from all vic's ==> set approached to none outside the loop
                pass
                
        return approachedColor, actionTaken
    
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
                    searchActs.append([Victims.getSearchAction(human), color])
                    if printTrace:
                        self.logger.info('Searched and found %s' % (color))
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
            searchActs.append([Victims.getSearchAction(human), 'none'])
            if printTrace:
                self.logger.info('Searched and found none')


    def getActionsAndEvents(self, human, printTrace=False, maxEvents=-1):
        self.pData = self.data.loc[self.data['player_ID'] == human]
        
        self.logger.info('Locations in player data but not map: %s' % 
            (','.join([l for l in self.data['Room_in'].unique() if not l in Locations.AllLocations])))
        self.logger.info('Locations in map but not player data: %s' % 
            (','.join([l for l in Locations.AllLocations if not l in self.data['Room_in'].unique()])))
        
        ## Sort by time
        self.pData = self.pData.loc[:, ['@timestamp', 'seconds'] + self.cols].sort_values('@timestamp', axis = 0)

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
            acts = []
            events = []
            moveActs = []
            searchActs = []
            stamp = row['@timestamp']
            duration = row['duration']
            triageAct = None
            
            ## Check that victim in CH is also in FoV
            if row['victim_in_crosshair_id'] != 'None':
                vicCH = row['victim_in_crosshair_id']
                for vi in range(self.maxVicsInLoc):
                    if row['victim_'+str(vi)+'_id'] == vicCH:
                        break
                
                # If this victim in CH isn't in FOV, skip and complain!
                if not row['victim_'+str(vi)+'_in_FOV']:
                    self.logger.error('%s vic in CH ID %s not in FOV' % (stamp,vi))
                    continue

            self.logger.debug('---- %d dur %d %s' % (row['seconds'], duration, np.sum([a[3] for a in actsAndEvents[:]])))
                
            # Entered a new room.
            if row['Room_in'] != lastLoc:
                if lastLoc == None:
                    # First elements in actions is the intial location
                    moveActs = [row['Room_in']]
                else:
                    # Add a move action
                    mv = Locations.getMoveAction(human, lastLoc, row['Room_in'])
                    for m in mv:
                        moveActs.append(m)
                    if mv == []:
                        self.logger.info('unreachable', lastLoc, row['Room_in'], row['@timestamp'])

                lastLoc = row['Room_in']
                self.logger.debug('moved to %s %s' % (lastLoc, stamp))

                self.parseFOV(row, True, prev, printTrace, human, searchActs)
                approachedColor, actionTaken = self.parseApproach(row, True, prev, printTrace, human, acts, events)

                # If there's a victim in crosshair, add action
                if row['victim_in_cross_hair_color'] != 'None':
                    acts.append(Victims.getPretriageAction(human, Victims.crosshairActs))
                    self.logger.debug('%s in CH' % (row['victim_in_cross_hair_color']))

                # Is a TIP in this new room? 
                if row['triage_in_progress']:
                    triageAct = Victims.getTriageAction(human)
                    acts.append(triageAct)
                    self.logger.debug('triage started in new room')

            # same room. Compare flag values to know what changed!
            else:
                self.parseFOV(row, False, prev, printTrace, human, searchActs)
                approachedColor, actionTaken = self.parseApproach(row, False, prev, printTrace, human, acts, events)

                # Compare color of victim in crosshairs
                var = 'victim_in_cross_hair_color'
                if row[var] != prev[var]:
                    if prev[var] != 'None':
                        events.append([Victims.STR_CROSSHAIR_VAR, 'none'])
                        self.logger.debug('%s out of CH' % (prev[var]))
                    if row[var] != 'None':
                        acts.append(Victims.getPretriageAction(human, Victims.crosshairActs))
                        self.logger.debug('%s in CH' % (row[var]))
                
                # If TIP changed
                var = 'triage_in_progress'
                if row[var] != prev[var]:
                    if row[var]:
                        triageAct = Victims.getTriageAction(human)
                        acts.append(triageAct)
                        self.logger.debug('triage started')
                    if prev[var]:
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
                sact.append(approachedColor)
                actsAndEvents.append([DataParser.SEARCH, sact, stamp, dur, attemptID])
            # acts includes approach, triage and crosshair actions
            for i, act in enumerate(acts):
                dur = 0
                if (act == triageAct) or ((triageAct == None) and (i == 0)):
                    dur = duration
                    duration = 0
                ## Enforce the value in the data on actions that don't otherwise affect approached victim
                act = [act]
                if act[0]['verb'] == 'actCH':
                    act.append(approachedColor)
                actsAndEvents.append([DataParser.ACTION, act, stamp, dur, attemptID])                
            for ev in events:
                dur = 0
                if i == 0:
                    dur = duration
                    duration = 0
                actsAndEvents.append([DataParser.SET_FLG, ev, stamp, dur, attemptID])
            
            prev = row
        return actsAndEvents

    def getTimelessAttempt(world, human, actsAndEvents, attemptID):
        attemptRows = [ae for ae in actsAndEvents if ae[-1] == attemptID]
        return attemptRows


    def runTimeless(world, human, actsAndEvents, start, end, ffwdTo=0):
        """
        Run actions and flag resetting events in the order they're given. No notion of timestamps
        """
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
                    world.setState(human, 'seenloc_'+actEv[0], True)
                    world.agents[human].setBelief(stateKey(human,'seenloc_'+actEv[0]),True)
            start = 1                

        apprKey = stateKey(human, Victims.STR_APPROACH_VAR)
        for t,actEvent in enumerate(actsAndEvents[start:end]):
            self.logger.info('\n%d) Running: %s' % (t+start, actEvent[1]))
            if t+start >= ffwdTo:
                input('press any key.. ')
            if actEvent[0] == DataParser.ACTION:
                act = actEvent[1][0]
                if act not in world.agents[human].getLegalActions():
                    raise ValueError('Illegal action!')
                if len(actEvent[1]) > 1:
                    world.step(act, select = {apprKey:world.value2float(apprKey,actEvent[1][1])})
                else:
                    world.step(act)
                
            elif actEvent[0] == DataParser.SET_FLG:
                [var, val] = actEvent[1]
                key = stateKey(human,var)
                world.state[key] = world.value2float(key,val)
                for model in world.getModel(human).domain():
                    if val not in world.getFeature(key,world.agents[human].models[model]['beliefs']).domain():
                        raise ValueError('Unbelievable data point at time %s: %s=%s' % (actEvent[2],var,val))
                    world.agents[human].models[model]['beliefs'][key] = world.value2float(key,val)
                
            elif actEvent[0] == DataParser.SEARCH:
                sact, color = actEvent[1][0], actEvent[1][1]
                selDict = {stateKey(human, Victims.STR_FOV_VAR):color}
                if len(actEvent[1]) > 2:
                    selDict[apprKey] = actEvent[1][2]
#                for nextAE in actsAndEvents[start+t+1:end]:
#                    if nextAE[0] != DataParser.SET_FLG:
#                        break
#                    [nextvar, nextval] = nextAE[1]
#                    nextkey = stateKey(human, nextvar)
#                    selDict[nextkey] = world.value2float(nextkey, nextval)
                
                world.step(sact, select={k:world.value2float(k,v) for k,v in selDict.items()})
            summarizeState(world,human,self.logger)

    def player_name(self):
        """
        :return: the name of the human player in this log file
        :rtype: str
        """
        return self.data['player_ID'].iloc[0]


def printAEs(aes,logger=logging):
    for ae in aes:
        logger.info(ae[2], ae[1])
                

def summarizeState(world,human,logger=logging):
    """
    Generates output about the player's current status
    :param world: the PsychSim simulation object
    :param human: the name of the player whose status is to be displayed
    :type human: str
    """
    time = world.getState(WORLD,'seconds',unique=True)
    logger.info('Time: %d' % (time))
    loc = world.getState(human,'loc',unique=True)
    logger.info('Player location: %s' % (loc))
    for name in sorted(world.agents):
        if name[:6] == 'victim' and world.getState(name,'loc',unique=True) == loc:
            logger.info('%s color: %s' % (name,world.getState(name,'color',unique=True)))
    logger.info('Approached: %s' % (world.getState(human,'vicApproached',unique=True)))
    logger.info('FOV: %s' % (world.getState(human,'vicInFOV',unique=True)))
    logger.info('CH: %s' % (world.getState(human,'vicInCH',unique=True)))    
    logger.info('JustSavedGr: %s' % (world.getState(human,'saved_Green',unique=True)))
    logger.info('JustSavedGd: %s' % (world.getState(human,'saved_Gold',unique=True)))
