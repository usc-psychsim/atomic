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
    def __init__(self, filename, maxDist=5):
        self.maxDist = maxDist
        self.maxVicsInLoc = 3
        self.data = pd.read_excel(filename)        
        self.cols = ['Room_in', 'num_victims', 'victim_0_id', 'victim_1_id','victim_2_id'\
                     'victim_0_in_CrossHair','victim_1_in_CrossHair','victim_2_in_CrossHair	',
                     'v0_dist', 'v1_dist', 'v2_dist']
        self.locations = [str(loc) for loc in self.data['Room_in'].unique()]
    
    def getActions(self, human):
        actions = []
        lastLoc = None
        
        pData = self.data[self.data['player_ID' == human]]
        
        ## Create flag for whether each victim is within triage range
        for vi in range(self.maxVicsInLoc):
            pData['v'+str(vi)+'_dist'] = pData['victim_'+str(vi)+'_dist' > 0] & pData['victim_'+str(vi)+'_dist' <= self.maxDist]
        
        pData = pData[:, ['@timestamp'] + self.cols]
        pData.sort('@timestamp', inplace = True)
        pData.drop_duplicates(subset=self.cols, inplace=True, keep='first')
        
        for ir,row in pData.iterrows():            
            # Entered a new room.
            if row['Room_in'] != lastLoc:
                lastLoc = row['Room_in']
                stamp = row['@timestamp']
                # Add a move action
                actions.append((Locations.moveToLocation(human, lastLoc, row['Room_in']), stamp))
                # For each victim, if in crosshairs, add crosshair action
                for vi in range(self.maxVicsInLoc):
                    if row['v' + str(vi) + '_dist'] == True:
                        actions.append((Victims.getTriageAction(human, lastLoc, row['victim_' + str(vi) + '_id'])))
                # For each victim, if in distance range, add distance action
                for vi in range(self.maxVicsInLoc):
                    if row['v' + str(vi) + '_dist'] == True:
                        actions.append((Victims.getTriageAction(human, lastLoc, row['victim_' + str(vi) + '_id'])))
                
                
    
        return actions
    
