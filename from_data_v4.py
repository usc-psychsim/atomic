#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""
import os.path
import sys
import logging

from parser_no_pre import DataParser
from SandRMap import getSandRMap, getSandRVictims
from maker import makeWorld


logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler('hala.log', 'w')],
        format='%(message)s', level=logging.DEBUG)
        
default_maps = {'sparky': {'room_file': 'sparky_adjacency',
                           'victim_file': 'sparky_vic_locs',
                           'coords_file': 'sparky_coords'},
                'falcon': {'room_file': 'falcon_adjacency_v1.1_OCN',
                           'victim_file': 'falcon_vic_locs_v1.1_OCN',
                           'coords_file': None}}
      

#### Parse the data file into a sequence of actions and events
maxDist=5
try:
       parser = DataParser(os.path.join(os.path.dirname(__file__),'data',sys.argv[1]), maxDist, logging)
except IndexError:
       parser = DataParser(os.path.join(os.path.dirname(__file__),'data',
                                        'processed_20200805_Participant7_Cond1.csv'),
                maxDist, logging)
name = parser.player_name()

#
###### Get Map Data
#mapName = 'falcon'
#SandRLocs = getSandRMap(fname=default_maps[mapName]['room_file'],logger=logging)
#SandRVics = getSandRVictims(fname=default_maps[mapName]['victim_file'])



world, triageAgent, agent, victimsObj = makeWorld(name, None, SandRLocs, SandRVics, logging)
parser.victimsObj = victimsObj

### Replay sequence of actions and events
aes, data = parser.getActionsAndEvents(triageAgent.name, True, 350)
#DataParser.runTimeless(world, triageAgent.name, aes,  0, 148, 0)