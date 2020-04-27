#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 20:35:23 2020

@author: mostafh
"""
import pandas as pd
from victims_fewacts import Victims
from new_locations_fewacts import Locations

class ActionTypes:
    MOVE = 0
    PRETRIAGE = 1
    TRIAGE = 2

class DataParser:
    ACTION = 0
    SET_FLG = 1

    def __init__(self, filename, maxDist=5):
        self.maxDist = maxDist
        if filename.endswith('xlsx'):
            self.data = pd.read_excel(filename)
        elif filename.endswith('csv'):
            self.data = pd.read_csv(filename)
        self.cols = ['Room_in', 'num_victims', 'victim_0_id', 'victim_1_id',
                     'victim_0_in_CrossHair','victim_1_in_CrossHair',
                     'victim_0_in_FOV','victim_1_in_FOV',
                     'v0_dist', 'v1_dist', 'triage_attempt']
        
        # Remove rows w/o locations
        print('Number of rows', len(self.data))
        self.data.dropna(axis=0, subset=['Room_in'], inplace=True)
        print('Number of rows after nan removal', len(self.data))
        
        # Rooms with numeric names: Prepend 'R'
        mask = self.data['Room_in'].str.startswith('2')
        newRoom = 'R' + self.data['Room_in']
        self.data.loc[mask, 'Room_in'] = newRoom.loc[mask]
        self.data['Room_in'] = self.data['Room_in'].astype(str)
        self.data['triage_attempt'] = self.data['triage_attempt'].astype(str)
        
#        # Change Yellow victims to Green
#        for vi in range(self.maxVicsInLoc):
#            self.data['victim_'+str(vi)+'_id'].replace('Yellow', 'Green', inplace=True)
        
        # Rooms with 1 victim: victim is Orange
        # Rooms with 2 victims: Orange and Green
        # Rooms with 3 victims: Orange and Green. Ignore the 3rd
        mask1 = self.data['num_victims']==1
        mask2 = self.data['num_victims']==2
        mask3 = self.data['num_victims']==3
        self.data.loc[mask1 | mask2 | mask3, 'victim_0_id'] = 'Orange'
        self.data.loc[mask2 | mask3, 'victim_1_id'] = 'Green'
        self.maxVicsInLoc = 2
        
        # Collect names of locations
        self.locations = [str(loc) for loc in self.data['Room_in'].unique()]
        self.rooms1Victim = self.data.loc[mask1, 'Room_in'].unique()
        self.rooms23Victim = self.data.loc[mask2|mask3, 'Room_in'].unique()
        
    def getActionsAndEvents(self, human):
        pData = self.data.loc[self.data['player_ID'] == human]

        ## Create flag for whether each victim is within triage range
        for vi in range(self.maxVicsInLoc):
            pData['v'+str(vi)+'_dist'] = (pData['victim_'+str(vi)+'_dist'] > 0) & (pData['victim_'+str(vi)+'_dist'] <= self.maxDist)

        ## Sort by time
        pData = pData.loc[:, ['@timestamp'] + self.cols].sort_values('@timestamp', axis = 0)

        ## Drop consecutive duplicate entries (ignoring the timestamp)
        pData = pData.loc[(pData[self.cols].shift() != pData[self.cols]).any(axis=1)]
        
        prev = None
        lastLoc = None
        actsAndEvents = []
        for ir,row in pData.iterrows():
            acts = []
            events = []
            moveActs = []
            attemptID = row['triage_attempt']
            stamp = row['@timestamp']
            if attemptID != 'nan':
                print('----', attemptID)
            else:
                print('----')
                
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
                    if row['victim_' + str(vi) + '_in_FOV'] == True:
                        ## Get the ID of this victim 
                        color = row['victim_'+str(vi)+'_id']
                        vicName = Victims.getVicName(lastLoc, color)
                        if vicName == '':
                            print('ERRPAR', color, lastLoc)
                        else:
                            events.append([Victims.STR_FOV_VAR, vicName])
                            print(vi, 'in FOV')

                # For each victim, if in distance range, add approach action
                for vi in range(self.maxVicsInLoc):
                    if row['v' + str(vi) + '_dist'] == True:
                        acts.append(Victims.getPretriageAction(human, Victims.approachActs))
                        print(vi, 'in range')
                
                # For each victim, if in crosshairs, add crosshair action
                for vi in range(self.maxVicsInLoc):
                    if row['victim_' + str(vi) + '_in_CrossHair'] == True:
                        acts.append(Victims.getPretriageAction(human, Victims.crosshairActs))
                        print(vi, 'in CH')
                
            # same room. Compare flag values to know what changed!
            else:
                # Compare flags for victim in FOV
                for vi in range(self.maxVicsInLoc):
                    var = 'victim_' + str(vi) + '_in_FOV'
                    if row[var] and not prev[var]:
                        print(vi, 'in FOV')
                        color = row['victim_'+str(vi)+'_id']
                        vicName = Victims.getVicName(lastLoc, color)
                        if vicName != '':
                            events.append([Victims.STR_FOV_VAR, vicName])
                    elif prev[var] and not row[var]:
                        print(vi, 'out of FOV')
                        events.append([Victims.STR_FOV_VAR, 'none'])
                        
                # Compare flags for victim within range
                for vi in range(self.maxVicsInLoc):
                    var = 'v' + str(vi) + '_dist'
                    if row[var] and not prev[var]:
                        print(vi, 'in range')
                        acts.append(Victims.getPretriageAction(human, Victims.approachActs))
                    elif prev[var] and not row[var]:
                        print(vi, 'out of range')
                        events.append([Victims.STR_APPROACH_VAR, 'none'])

                # Compare flags for victim in crosshairs
                for vi in range(self.maxVicsInLoc):
                    var = 'victim_' + str(vi) + '_in_CrossHair'
                    if row[var] and not prev[var]:
                        print(vi, 'in CH')
                        acts.append(Victims.getPretriageAction(human, Victims.crosshairActs))
                    elif prev[var] and not row[var]:
                        print(vi, 'out of CH')
                        events.append([Victims.STR_CROSSHAIR_VAR, 'none'])
                        
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
        
        ## TODO don't assume we're starting at the beginning
        # First is the initial location of the human
        print('\n\n====Running actions and events for', human)
        world.setState(human, 'loc', actsAndEvents[0][1])
        world.setState(human, 'seenloc_'+actsAndEvents[0][1], True)
        
        for actEvent in actsAndEvents[1:]:
            print('Running',  actEvent[1])
            if actEvent[0] == DataParser.ACTION:
                world.step(actEvent[1])
            elif actEvent[0] == DataParser.SET_FLG:
                [var, val] = actEvent[1]
                world.setState(human, var, val)
            world.printState()

