#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 21 10:28:16 2021

@author: mostafh
"""

import logging, sys
from atomic.parsing.message_processing import ProcessParsedJson
from atomic.parsing.count_features import CountEnterExit
from atomic.parsing.map_parser import read_semantic_map

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
   

ddir = '../data/ASU_DATA/'
fnames = []
fnames.append(ddir + 'TrialMessages_CondBtwn-1_CondWin-Saturn-StaticMap_Trial-1_Team-na_Member-Aptiminer1_Vers-hack-1.metadata')
fnames.append(ddir + 'study-2_pilot-2_2021.02_NotHSRData_TrialMessages_Trial-T000294_Team-TM000011_CondBtwn-TmPlan_CondWin-SaturnA_Vers-1_.metadata')
map_file = '/home/mostafh/Documents/psim/new_atomic/atomic/maps/Saturn/Saturn_1.4_3D_sm_v1.0.json'

room_node_names, room_edges = read_semantic_map(map_file)
fname = fnames[1]


parser = ProcessParsedJson(fname, room_node_names, logger=logging)
parser.startProcessing(derivedFeats)

SandRVics = getVictimsFromBus(parser.vList)
parser.setVictimLocations(SandRVics)
parser.getActionsAndEvents(None, None, 99)
