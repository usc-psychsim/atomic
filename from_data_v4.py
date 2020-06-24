#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""

from new_locations_fewacts import Locations
from victims_clr import Victims
from parser_v2 import DataParser, printAEs
from SandRMap import getSandRMap, getSandRVictims
from maker import makeWorld
import pandas as pd 

# MDP or POMDP
Victims.FULL_OBS = False

#### Get Map Data
SandRLocs = getSandRMap()
SandRVics = getSandRVictims()

world, triageAgent, agent = makeWorld('Player173', 'BH2', SandRLocs, SandRVics)


## Parse the data file into a sequence of actions and events
parser = DataParser('Florian_processed_1.csv')
aes = parser.getActionsAndEvents(triageAgent.name)
##printAEs(aes)
#
#aeDF = pd.DataFrame(columns = ['ts', 'ae', 'attID'])
#aeDF['ts'] = [r[2] for r in aes]
#aeDF['attID'] = [r[3] for r in aes]
#aeDF['ae'] = [str(r[1]) for r in aes]

### Inject the player's location at the beginning of the attempt in question
#atm = [[0, 'R218', 'March 12th 2020, 19:13:00.022', 'nan']] + atm

#DataParser.runTimeless(world, triageAgent.name, aes)
