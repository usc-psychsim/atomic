#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 20:35:23 2020

@author: mostafh
"""
import pandas as pd
from victims_clr import Victims
from new_locations_fewacts import Locations
from psychsim.action import ActionSet

class ActionTypes:
    MOVE = 0
    PRETRIAGE = 1
    TRIAGE = 2
    SEARCH = 3

class DataParser:
    ACTION = 0
    SET_FLG = 1

    def __init__(self, filename, maxDist=5):
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
                    'victim_0_in_FOV',
                    'victim_1_in_FOV',
                    'victim_in_crosshair_id',
                    'victim_in_cross_hair_color',
                    'event_triage_victim_id',
                    'triage_in_progress',
                    'triage_result']
        
        # Remove rows w/o locations
        print('Number of rows', len(self.data))
        self.data.dropna(axis=0, subset=['Room_in'], inplace=True)
        self.data= self.data.loc[self.data['Room_in']!='None',:]
        print('Number of rows after empty room removal', len(self.data))
        
        # Remove in_progress rows that were never back-filled
        self.data= self.data.loc[self.data['triage_result']!='IN_PROGRESS',:]
        print('Number of rows after triage in progress removal', len(self.data))
        
        # Remove triage_in_progress rows where victim being triaged different from victim in CH
        triageOn = self.data['triage_in_progress'] == True
        sameVic = self.data['event_triage_victim_id']==self.data['victim_in_crosshair_id']
        self.data= self.data.loc[~triageOn | sameVic,:]
        print('Number of rows after inconsistent triage vic and CH removal', len(self.data))
        
        # Rooms with numeric names: Prepend 'R'
        mask = self.data['Room_in'].str.startswith('2')
        newRoom = 'R' + self.data['Room_in']
        self.data.loc[mask, 'Room_in'] = newRoom.loc[mask]
        self.data['Room_in'] = self.data['Room_in'].astype(str)
#        self.data['triage_attempt'] = self.data['triage_attempt'].astype(str)

        self.maxVicsInLoc = 2
        # Collect names of locations
        self.locations = [str(loc) for loc in self.data['Room_in'].unique()]

    def getActionsAndEvents(self, human):
        self.pData = self.data.loc[self.data['player_ID'] == human]

        ## Create flag for whether each victim is within triage range
        for vi in range(self.maxVicsInLoc):
            self.pData['v'+str(vi)+'_dist'] = (self.pData['victim_'+str(vi)+'_dist'] > 0) & \
                                        (self.pData['victim_'+str(vi)+'_dist'] <= self.maxDist)

        ## Sort by time
        self.pData = self.pData.loc[:, ['@timestamp'] + self.cols].sort_values('@timestamp', axis = 0)

        ## Drop consecutive duplicate entries (ignoring the timestamp)
        self.pData = self.pData.loc[(self.pData[self.cols].shift() != self.pData[self.cols]).any(axis=1)]
        print('Dropped duplicates. Down to', len(self.pData))

        prev = None
        lastLoc = None
        actsAndEvents = []
        attemptID = 0
        for ir,row in self.pData.iterrows():
            print('----', len(actsAndEvents))
            acts = []
            events = []
            moveActs = []
            stamp = row['@timestamp']
            print('----')
            
            ## Check that victim in CH is also in FoV
            if row['victim_in_crosshair_id'] != 'None':
                vicCH = row['victim_in_crosshair_id']
                for vi in range(self.maxVicsInLoc):
                    if row['victim_'+str(vi)+'_id'] == vicCH:
                        break
                
                # If this victim in CH isn't in FOV, skip and complain!
                if not row['victim_'+str(vi)+'_in_FOV']:
                    print('===ERROR', stamp, 'vic in CH ID', vi, ' not in FOV')
                    continue

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
                        print('unreachable', lastLoc, row['Room_in'], row['@timestamp'])

                lastLoc = row['Room_in']
                print('moved to', lastLoc, stamp)

                # For each victim, if in FOV, set the FOV variable to victim's name
                for vi in range(self.maxVicsInLoc):
                    color = row['victim_'+str(vi)+'_color']
                    if row['victim_' + str(vi) + '_in_FOV'] == True:
                        events.append([Victims.STR_FOV_VAR, color])
                        print(color, 'in FOV')

                # For each victim, if in distance range, add approach action
                for vi in range(self.maxVicsInLoc):
                    color = row['victim_'+str(vi)+'_color']
                    if row['v' + str(vi) + '_dist'] == True:
                        acts.append(Victims.getPretriageAction(human, Victims.approachActs))
                        print(color, 'in range')

                # If there's a victim in crosshair, add action
                if row['victim_in_cross_hair_color'] != 'None':
                    acts.append(Victims.getPretriageAction(human, Victims.crosshairActs))
                    print(row['victim_in_cross_hair_color'], 'in CH')

                # Is a TIP in this new room? 
                if row['triage_in_progress']:
                    acts.append(Victims.getTriageAction(human))
                    print('triage started in new room')

            # same room. Compare flag values to know what changed!
            else:
                # Compare flags for victim in FOV
                for vi in range(self.maxVicsInLoc):
                    color = row['victim_'+str(vi)+'_color']
                    var = 'victim_' + str(vi) + '_in_FOV'
                    if row[var] and not prev[var]:
                        print(color, 'in FOV')
                        events.append([Victims.STR_FOV_VAR, color])
                    elif prev[var] and not row[var]:
                        print(color, 'out of FOV')
                        events.append([Victims.STR_FOV_VAR, 'none'])

                # Compare flags for victim within range
                for vi in range(self.maxVicsInLoc):
                    color = row['victim_'+str(vi)+'_color']
                    var = 'v' + str(vi) + '_dist'
                    if row[var] and not prev[var]:
                        print(color, 'in range')
                        acts.append(Victims.getPretriageAction(human, Victims.approachActs))
                    elif prev[var] and not row[var]:
                        print(color, 'out of range')
                        events.append([Victims.STR_APPROACH_VAR, 'none'])

                # Compare color of victim in crosshairs
                var = 'victim_in_cross_hair_color'
                if row[var] != prev[var]:
                    if prev[var] != 'None':
                        events.append([Victims.STR_CROSSHAIR_VAR, 'none'])
                        print(prev[var], 'out of CH')
                    if row[var] != 'None':
                        acts.append(Victims.getPretriageAction(human, Victims.crosshairActs))
                        print(row[var], 'in CH')
                
                # If TIP changed
                var = 'triage_in_progress'
                if row[var] != prev[var]:
                    if row[var]:
                        acts.append(Victims.getTriageAction(human))
                        print('triage started')
                    if prev[var]:
                        print('triage stopped')
                        attemptID = attemptID  + 1

            ## Inject move action(s), then events, then crosshair/approach actions
            for mact in moveActs:
                actsAndEvents.append([DataParser.ACTION, mact, stamp, attemptID])
            for ev in events:
                actsAndEvents.append([DataParser.SET_FLG, ev, stamp, attemptID])
            for act in acts:
                actsAndEvents.append([DataParser.ACTION, act, stamp, attemptID])

            prev = row
        return actsAndEvents

    def getTimelessAttempt(world, human, actsAndEvents, attemptID):
        attemptRows = [ae for ae in actsAndEvents if ae[-1] == attemptID]
        return attemptRows


    def runTimeless(world, human, actsAndEvents):
        """
        Run actions and flag resetting events in the order they're given. No notion of timestamps
        """
        [actOrEvFlag, actEv, stamp, attempt] = actsAndEvents[0]
        if actOrEvFlag == DataParser.SET_FLG:
            varName = actEv[0]
            varValue = actEv[1]
            world.setState(human, varName, varValue)
        else:
            # This first action can be an actual action or an initial location
            if type(actEv) == ActionSet:
                world.step(actEv)
            else:
                world.setState(human, 'loc', actEv)
                world.setState(human, 'seenloc_'+actEv, True)
                

        for actEvent in actsAndEvents[1:]:
            print('Running',  actEvent[1])
            if actEvent[0] == DataParser.ACTION:
                world.step(actEvent[1])
            elif actEvent[0] == DataParser.SET_FLG:
                [var, val] = actEvent[1]
                world.setState(human, var, val)
            world.printState(beliefs=False)
#            input('go on-->')

def printAEs(aes):
    for ae in aes:
        print(ae[2], ae[1])
                

