#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""

from psychsim.world import World, WORLD
from new_locations_fewacts import Locations
from victims_clr import Victims
from parser_v2 import DataParser, printAEs
from SandRMap import getSandRMap, getSandRVictims

# MDP or POMDP
Victims.FULL_OBS = False

world = World()
k = world.defineState(WORLD, 'seconds', int)
world.setFeature(k, 0)

triageAgent = world.addAgent('Player173')
agent = world.addAgent('ATOMIC')

##### Get Map Data
#SandRLocs = getSandRMap()
#SandRVics = getSandRVictims()
## Parse data file. 
parser = DataParser('Florian_processed_1.csv')


################# Victims and triage actions
Victims.world = world
VICTIMS_LOCS = []
VICTIM_TYPES = []
for loc, vics in SandRVics.items():
    for vic in vics:
        if loc.startswith('2'):
            loc = 'R' + loc
        VICTIMS_LOCS.append(loc)
        VICTIM_TYPES.append(vic)
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], list(SandRLocs.keys()))
Victims.makePreTriageActions(triageAgent)
Victims.makeTriageAction(triageAgent)

################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMapDict(SandRLocs)
Locations.makePlayerLocation(triageAgent,Victims,  "BH2")

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])



## Parse the data file into a sequence of actions and events
aes = parser.getActionsAndEvents(triageAgent.name)
printAEs(aes)

### Get actions and events related to a given triage attempt
#atm = DataParser.getTimelessAttempt(world, triageAgent.name, aes, 'SA8')
### Inject the player's location at the beginning of the attempt in question
#atm = [[0, 'R218', 'March 12th 2020, 19:13:00.022', 'nan']] + atm
#printAEs(atm)
#DataParser.runTimeless(world, triageAgent.name, atm)
