#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""
import logging
import sys
from atomic.parsing.multi_message_processing import ProcessParsedJson
from atomic.parsing.count_features import CountEnterExit
from atomic.parsing.map_parser import read_semantic_map

logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.DEBUG)

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
   

ddir = '../data/ASU_DATA/'
fname = ddir + 'study-2_pilot-2_2021.02_NotHSRData_TrialMessages_Trial-T000315_Team-TM000021_Member-na_CondBtwn-1_CondWin-SaturnA_Vers-1.metadata'
map_file = '../maps/Saturn/Saturn_1.5_3D_sm_v1.0.json'

room_node_names, room_edges = read_semantic_map(map_file)

parser = ProcessParsedJson(fname, room_node_names, logger=logging)
parser.startProcessing(derivedFeats)

SandRVics = getVictimsFromBus(parser.vList)
parser.setVictimLocations(SandRVics)

##### Process the list of dicts into psychsim actions
parser.getActionsAndEvents(0, 0, 0)
