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
from atomic.parsing.count_features import CountEnterExit, CountRoleChanges, CountTriageInHallways, CountVisitsPerRole

logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.INFO)

### Extract initial victim locations from the first message on the bus
def getVictimsFromBus(vlist):
    room2Vics = dict()
    for vic in vlist:
        rm = vic['room_name']
        if rm not in room2Vics:
            room2Vics[rm] = []
        room2Vics[rm].append(vic['block_type'])
    return room2Vics

derivedFeats = []
derivedFeats.append(CountEnterExit(['mce3', 'scw1']))
derivedFeats.append(CountEnterExit(['el2', 'srbn']))
   

######### Get Map Data
DEFAULT_MAPS = get_default_maps()
fnames = []
ddir = '../data/ASU_DATA/'
fnames.append(ddir + 'study-2_pilot-2_2021.02_NotHSRData_TrialMessages_CondBtwn-IdvPlan_CondWin-SaturnA_Trial-T000293_Team-TM000010_Member-P000130-P000131-P000132_Vers-1.metadata')
fnames.append(ddir + 'study-2_pilot-2_2021.02_NotHSRData_TrialMessages_CondBtwn-IdvPlan_CondWin-SaturnB_Trial-T000292_Team-TM000010_Member-P000130-P000131-P000132_Vers-1.metadata')
fnames.append(ddir + 'TrialMessages_CondBtwn-1_CondWin-Saturn-StaticMap_Trial-1_Team-na_Member-Aptiminer1_Vers-hack-1.metadata')

mapNames = ['saturnA', 'saturnB', 'saturnA',]
chosen = 2
mapStruct = DEFAULT_MAPS[mapNames[chosen]]
SandRLocs = dict(mapStruct.adjacency)
parser = ProcessParsedJson(fnames[chosen], mapStruct, logger=logging)
parser.startProcessing(derivedFeats)
SandRVics = getVictimsFromBus(parser.vList)
#
#world, triageAgent, agent, victimsObj, world_map = make_single_player_world(
#    parser.player_name(), None, SandRLocs, SandRVics, False, True)
#
#maxNumEvents = 9999
#runStartsAt = 0
#runEndsAt = 9999
#parseFastFwdTo = 9999
#runFastFwdTo = 9999
#
##### Process the list of dicts into psychsim actions
#parser.setVictimLocations(SandRVics)
#parser.getActionsAndEvents(victimsObj, world_map, maxNumEvents)
######## Replay sequence of actions 
#parser.runTimeless(world, runStartsAt, runEndsAt, runFastFwdTo)
