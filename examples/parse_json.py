#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 21 10:28:16 2021

@author: mostafh
"""

from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.count_features import CountEnterExit
from atomic.parsing.pilot2_message_reader import createJSONParser

featuresToExtract = []
featuresToExtract.append(CountEnterExit(['mce3', 'scw1']))
featuresToExtract.append(CountEnterExit(['el2', 'srbn']))
   

ddir = '../data/ASU_DATA/'
DEFAULT_MAPS = get_default_maps()
fnames = []
fnames.append(ddir + 'TrialMessages_CondBtwn-1_CondWin-Saturn-StaticMap_Trial-1_Team-na_Member-Aptiminer1_Vers-hack-1.metadata')

mapNames = ['saturnA']
chosen = 0
mapStruct = DEFAULT_MAPS[mapNames[chosen]]
SandRLocs = dict(mapStruct.adjacency)

jsonParser = createJSONParser(mapStruct.room_file)
jsonParser.registerFeatures(featuresToExtract)
jsonParser.process_json_file(fnames[chosen])

print(len(jsonParser.messages))
