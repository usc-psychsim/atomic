#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""
import logging
import os.path
import sys
from atomic.definitions.map_utils import getSandRMap, getSandRVictims, DEFAULT_MAPS
from atomic.parsing.parserFromJson import ProcessParsedJson
from atomic.scenarios.single_player import make_single_player_world

logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.DEBUG)

######### Get Map Data
small = False
mapName = 'FalconEasy'
SandRLocs = getSandRMap(fname=DEFAULT_MAPS[mapName]['room_file'], logger=logging)
SandRVics = getSandRVictims(fname=DEFAULT_MAPS[mapName]['victim_file'])

## Fabricate a light switch map that maps each room with a switch to a list of rooms affected by the switch
shared = {'lh':8, 'rh':9, 'mb':5, 'wb':5}
lightMap = {k:[k] for k in SandRLocs.keys() if sum([k.startswith(shr) for shr in shared.keys()]) == 0}
for shr,num in shared.items():
    lightMap[shr + '1'] = []
    for i in range(1,num+1):
        lightMap[shr + '1'].append(shr + str(i))


#use_unobserved=True, full_obs=False, logger=logging):
playerName = 'Research_Account'
world, triageAgent, agent, victimsObj, world_map = make_single_player_world(playerName, None, SandRLocs, SandRVics, False, True, lightMap)

### Process the message into actions and events
from atomic.parsing.parserFromJson import ProcessParsedJson
jsonPrpcessor = ProcessParsedJson(playerName, world_map, victimsObj, logger=logging)
allMs = [m.mdict for m in reader.messages]

jsonPrpcessor.processJson(iter(allMs), SandRVics, 9999)
### Replay sequence of actions and events
jsonPrpcessor.runTimeless(world, 0, 9999, 9999)
