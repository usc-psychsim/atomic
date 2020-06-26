#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""

from new_locations_fewacts import Locations, Directions
from victims_clr import Victims
from parser_v2 import DataParser, printAEs
from SandRMap import getSandRMap, getSandRVictims
from maker import makeWorld

# MDP or POMDP
Victims.FULL_OBS = False

##### Get Map Data
small = False
SandRLocs = getSandRMap(small)
SandRVics = getSandRVictims(small)

### Parse the data file into a sequence of actions and events
parser = DataParser('data/processed_ASIST_data_study_id_000001_condition_id_000002_trial_id_000010_messages.csv')
name =	parser.data['player_ID'].iloc[0]

world, triageAgent, agent = makeWorld(name, 'BH2', SandRLocs, SandRVics)

Locations.move(triageAgent, Directions.S)
Victims.search(triageAgent, True)
Victims.approach(triageAgent)
Victims.putInCH(triageAgent)
Victims.triage(triageAgent)
print(triageAgent.reward())

aes = parser.getActionsAndEvents(triageAgent.name)
DataParser.runTimeless(world, triageAgent.name, aes)
