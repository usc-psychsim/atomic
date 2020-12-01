#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""
import logging
import sys
from atomic.definitions.map_utils import getSandRMap, getSandRVictims, DEFAULT_MAPS
from atomic.parsing.parserFromJson import ProcessParsedJson
from atomic.scenarios.single_player import make_single_player_world

logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.ERROR)

######## Get Map Data
mapName = 'FalconEasy'
SandRLocs = getSandRMap(fname=DEFAULT_MAPS[mapName]['room_file'], logger=logging)

## Fabricate a light switch map that maps each room with a switch to a list of rooms affected by the switch
shared = {'lh':8, 'rh':9, 'mb':5, 'wb':5}
lightMap = {k:[k] for k in SandRLocs.keys() if sum([k.startswith(shr) for shr in shared.keys()]) == 0}
for shr,num in shared.items():
    lightMap[shr + '1'] = []
    for i in range(1,num+1):
        lightMap[shr + '1'].append(shr + str(i))

#use_unobserved=True, full_obs=False, logger=logging):
SandRVics = getSandRVictims(fname=DEFAULT_MAPS[mapName]['victim_file'])
fname = '../data/HSRData_TrialMessages_CondBtwn-NoTriageNoSignal_CondWin-FalconEasy-StaticMap_Trial-120_Team-na_Member-51_Vers-3.metadata'
parser = ProcessParsedJson(fname, logger=logging)

world, triageAgent, agent, victimsObj, world_map = make_single_player_world(parser.player_name(), None, SandRLocs, SandRVics, False, True, lightMap)

maxNumEvents = 350
runStartsAt = 0
runEndsAt = 20
fastFwdTo = 9999

### Process the list of dicts into psychsim actions
parser.getActionsAndEvents(victimsObj, world_map, SandRVics, maxNumEvents)
### Replay sequence of actions 
parser.runTimeless(world, runStartsAt, runEndsAt, fastFwdTo)
