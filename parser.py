#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 20:35:23 2020

@author: mostafh
"""
import pandas as pd
from victims import Victims
from new_locations import Locations

class ActionTypes:
    MOVE = 0
    PRETRIAGE = 1
    TRIAGE = 2

class DataParser:
    ACTION = 0
    RESET_FLG = 1

    def __init__(self, filename, maxDist=5):
        self.maxDist = maxDist
        self.maxVicsInLoc = 3
        self.data = pd.read_excel(filename)
        self.cols = ['Room_in', 'num_victims', 'victim_0_id', 'victim_1_id','victim_2_id', \
                     'victim_0_in_CrossHair','victim_1_in_CrossHair','victim_2_in_CrossHair',
                     'v0_dist', 'v1_dist', 'v2_dist']
        self.locations = [str(loc) for loc in self.data['Room_in'].unique()]
        self.data['Room_in'] = self.data['Room_in'].astype(str)

    def getActionsAndEvents(self, human):
        actsAndEvents = []
        lastLoc = None

        pData = self.data[self.data['player_ID'] == human]

        ## Create flag for whether each victim is within triage range
        for vi in range(self.maxVicsInLoc):
            pData['v'+str(vi)+'_dist'] = (pData['victim_'+str(vi)+'_dist'] > 0) & (pData['victim_'+str(vi)+'_dist'] <= self.maxDist)

        pData = pData.loc[:, ['@timestamp'] + self.cols]
        pData.sort_values('@timestamp', axis = 0, inplace = True)

        ## Drop consecutive duplicate entries (ignoring the timestamp)
        pData = pData.loc[(pData[self.cols].shift() != pData[self.cols]).any(axis=1)]
        prev = None
        for ir,row in pData.iterrows():
            acts = []
            events = []
            # Entered a new room.
            if row['Room_in'] != lastLoc:
                stamp = row['@timestamp']
                if lastLoc == None:
                    # First elements in actions is the intial location
                    acts.append(row['Room_in'])
                else:
                    # Add a move action
                    acts.append(Locations.getMoveAction(human, lastLoc, row['Room_in']))
                lastLoc = row['Room_in']
                print('moved to', lastLoc)

                # For each victim, if in distance range, add pre-target action
                for vi in range(self.maxVicsInLoc):
                    if row['v' + str(vi) + '_dist'] == True:
                        acts.append(Victims.getPretriageAction(human, lastLoc, row['victim_' + str(vi) + '_id']))
                        print('got', vi, 'in range')

            else:  # same location. Compare flag values to know what changed!
                for vi in range(self.maxVicsInLoc):
                    if row['v' + str(vi) + '_dist'] and not prev['v' + str(vi) + '_dist']:
                        print(lastLoc, vi, 'got in range')
                        acts.append(Victims.getPretriageAction(human, lastLoc, row['victim_' + str(vi) + '_id']))
                    elif prev['v' + str(vi) + '_dist'] and not row['v' + str(vi) + '_dist']:
                        print(lastLoc, vi, 'got out of range')
                        events.append('victim in crosshair')

            for act in acts:
                actsAndEvents.append([DataParser.ACTION, act, stamp])
            for ev in events:
                actsAndEvents.append([DataParser.RESET_FLG, ev, stamp])

            prev = row
        return actsAndEvents, pData

    def runTimeless(world, human, actsAndEvents):
        """
        Run actions and flag resetting events in the order they're given. No notion of timestamps
        """
        # First is the initial location of the human
        print('\n\n====Running actions and events for', human)
        world.setState(human, 'loc', actsAndEvents[0][1])
        world.setState(human, 'seenloc_'+actsAndEvents[0][1], True)
        for actEvent in actsAndEvents[1:]:
            print('Running',  actEvent[1])
            if actEvent[0] == DataParser.ACTION:
                world.step(actEvent[1])
            elif actEvent[0] == DataParser.RESET_FLG:
                world.setState(human, actEvent[1], False)
            world.printState()

