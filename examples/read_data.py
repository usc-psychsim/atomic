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
from atomic.parsing.parser import DataParser
from atomic.scenarios.single_player import make_single_player_world

logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler('hala.log', 'w')],
    format='%(message)s', level=logging.DEBUG)

#### Parse the data file into a sequence of actions and events
maxDist = 5
try:
    parser = DataParser(os.path.join(os.path.dirname(__file__), 'data', sys.argv[1]), maxDist, logging)
except IndexError:
    parser = DataParser(os.path.join(os.path.dirname(__file__), 'data',
                                     'processed_20200805_Participant7_Cond1.csv'),
                        maxDist, logging)
name = parser.player_name()

#
####### Get Map Data
small = False
mapName = 'falcon'
SandRLocs = getSandRMap(fname=DEFAULT_MAPS[mapName]['room_file'], logger=logging)
SandRVics = getSandRVictims(fname=DEFAULT_MAPS[mapName]['victim_file'])

world, triageAgent, agent, victimsObj, world_map = make_single_player_world(name, 'BH2', SandRLocs, SandRVics)

### Replay sequence of actions and events
aes, data = parser.getActionsAndEvents(triageAgent.name, victimsObj, world_map, True, 350)
# DataParser.runTimeless(world, triageAgent.name, aes,  0, 148, 0)
