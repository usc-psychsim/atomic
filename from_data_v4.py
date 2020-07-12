#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""
import sys

from new_locations_fewacts import Locations, Directions
from victims_clr import Victims
from parser_v2 import DataParser, printAEs
from SandRMap import getSandRMap, getSandRVictims
from maker import makeWorld

# MDP or POMDP
Victims.FULL_OBS = False

def ptree(tree, level):
    
    pre = ' '.ljust(4*level)
    if type(tree) == dict:
        for k in tree.keys():
            print(pre, k)
            ptree(tree[k], level+1)
    else:
        print(pre, tree)

### Parse the data file into a sequence of actions and events
try:
       parser = DataParser(sys.argv[1])
except IndexError:
       parser = DataParser('Florian_processed_1.csv')
name = parser.data['player_ID'].iloc[0]

##### Get Map Data
small = True
SandRLocs = getSandRMap(small)
SandRVics = getSandRVictims(small)

world, triageAgent, agent, debug = makeWorld(name, 'BH2', SandRLocs, SandRVics)
#world, triageAgent, agent, debug = makeWorld('TriageAg1', 'CH4', SandRLocs, SandRVics)

#Locations.move(triageAgent, Directions.N)
#Victims.search(triageAgent, True)
#Victims.approach(triageAgent)
#Victims.putInCH(triageAgent)
#Victims.triage(triageAgent)
#print(triageAgent.reward())

### Replay sequence of actions and events
aes = parser.getActionsAndEvents(triageAgent.name)

DataParser.runTimeless(world, triageAgent.name, aes)
