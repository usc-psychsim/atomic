#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""
import logging
import os.path
import sys
from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.parser import ProcessCSV
from atomic.scenarios.single_player import make_single_player_world

logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler('hala.log', 'w')],
    format='%(message)s', level=logging.DEBUG)

#### Parse the data file into a sequence of actions and events
maxDist = 5
try:
    fname = os.path.join(os.path.dirname(__file__), '../data', sys.argv[1])
    parser = ProcessCSV(fname, maxDist, logging)
except IndexError:
    fname = os.path.join(os.path.dirname(__file__), '../data',
                         'processed_20200728_Participant3_Cond1.csv')
    parser = ProcessCSV(fname, maxDist, logging)

######### Get Map Data
mapName = 'FalconEasy'
DEFAULT_MAPS = get_default_maps()
SandRLocs = DEFAULT_MAPS[mapName].adjacency
SandRVics = DEFAULT_MAPS[mapName].victims

## Fabricate a light switch map that maps each room with a switch to a list of rooms affected by the switch
shared = {'lh':8, 'rh':9, 'mb':5, 'wb':5}
lightMap = {k:[k] for k in SandRLocs.keys() if sum([k.startswith(shr) for shr in shared.keys()]) == 0}
for shr,num in shared.items():
    lightMap[shr + '1'] = []
    for i in range(1,num+1):
        lightMap[shr + '1'].append(shr + str(i))


#use_unobserved=True, full_obs=False, logger=logging):
world, triageAgent, agent, victimsObj, world_map = make_single_player_world(
    parser.player_name(), None, SandRLocs, SandRVics, False, True)


maxNumEvents = 350
runStartsAt = 0
runEndsAt = 20
fastFwdTo = 9999
parser.getActionsAndEvents(victimsObj, world_map, maxNumEvents)
parser.runTimeless(world, runStartsAt, runEndsAt, fastFwdTo)
