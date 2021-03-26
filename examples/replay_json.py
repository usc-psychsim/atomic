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
DEFAULT_MAPS = get_default_maps()
fnames = []
ddir = '../data/ASU_DATA/'
fnames.append(ddir + 'study-2_pilot-2_2021.02_NotHSRData_TrialMessages_CondBtwn-TmPlan_CondWin-SaturnA_Trial-T000290_Team-TM000009_Member-P000127-P000128-P000129_Vers-2.metadata')
fnames.append(ddir + 'study-2_pilot-2_2021.02_NotHSRData_TrialMessages_CondBtwn-TmPlan_CondWin-SaturnB_Trial-T000291_Team-TM000009_Member-P000127-P000128-P000129_Vers-2.metadata')


mapNames = ['saturnA', 'saturnB']
chosen = 1
mapStruct = DEFAULT_MAPS[mapNames[chosen]]
SandRLocs = dict(mapStruct.adjacency)
SandRVics = dict(mapStruct.victims)
parser = ProcessParsedJson(fnames[chosen], mapStruct, logger=logging)

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
##### Replay sequence of actions 
#parser.runTimeless(world, runStartsAt, runEndsAt, runFastFwdTo)
