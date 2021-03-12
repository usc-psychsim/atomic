#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""
import logging
import sys
from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.json_parser import ProcessParsedJson
from atomic.scenarios.single_player import make_single_player_world

logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.INFO)

######### Get Map Data
mapName = 'saturn'
DEFAULT_MAPS = get_default_maps()
SandRLocs = DEFAULT_MAPS[mapName].adjacency
SandRVics = DEFAULT_MAPS[mapName].victims

# use_unobserved=True, full_obs=False, logger=logging):
fname = '../data/ASU_DATA/study-2_pilot-2_2021.02_NotHSRData_TrialMessages_CondBtwn-TmPlan_CondWin-SaturnA_Trial-T000288_Team-TM000008_Member-P000124-P000125-P000126_Vers-1.metadata'

parser = ProcessParsedJson(fname, DEFAULT_MAPS[mapName], logger=logging)

world, triageAgent, agent, victimsObj, world_map = make_single_player_world(
    parser.player_name(), None, SandRLocs, SandRVics, False, True)

maxNumEvents = 9999
runStartsAt = 0
runEndsAt = 9999
parseFastFwdTo = 9999
runFastFwdTo = 9999

#### Process the list of dicts into psychsim actions
parser.setVictimLocations(SandRVics)
parser.getActionsAndEvents(victimsObj, world_map, maxNumEvents)
#### Replay sequence of actions 
parser.runTimeless(world, runStartsAt, runEndsAt, runFastFwdTo)
