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
from atomic.parsing.message_reader import getMessages

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


allMs, playerName = getMessages({})

#use_unobserved=True, full_obs=False, logger=logging):
SandRVics = getSandRVictims(fname=DEFAULT_MAPS[mapName]['victim_file'])
world, triageAgent, agent, victimsObj, world_map = make_single_player_world(playerName, None, SandRLocs, SandRVics, False, True, lightMap)

jsonPrpcessor = ProcessParsedJson(playerName, world_map, victimsObj, logger=logging)
### Process the list of dicts into psychsim actions
jsonPrpcessor.processJson(iter(allMs), SandRVics, 9999)
### Replay sequence of actions 
jsonPrpcessor.runTimeless(world, 0, 9999, 9999)


### Replay sequence of actions and events
#maxDist = 5
#try:
#    parser = DataParser(os.path.join(os.path.dirname(__file__), '../data', sys.argv[1]), maxDist, logging)
#except IndexError:
#    parser = DataParser(os.path.join(os.path.dirname(__file__), '../data',
#                                     'processed_20200728_Participant3_Cond1.csv'),
#                        maxDist, logging)
#aes, data = parser.getActionsAndEvents(triageAgent.name, victimsObj, world_map, True, 350)
#DataParser.runTimeless(world, triageAgent.name, aes,  0, 148, 0)
#