#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec 11 11:25:42 2020

@author: mostafh
"""

import logging
import sys
import os
from atomic.parsing.message_reader import getMessages
from atomic.definitions.map_utils import get_default_maps
from atomic.parsing.parserFromJson import ProcessParsedJson
from atomic.scenarios.single_player import make_single_player_world

logging.root.setLevel(logging.DEBUG)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.ERROR)

## Make sure all the files in your batch directory have this map name
## Otherwise, extract the map name from the file name
mapName = 'FalconEasy'

### Batch parsing of ASU json files into json files containing the dicts we care about
jdir = '../data/ASU_DATA/'
outdir = '../data/ASU_DATA/parsed/'

DEFAULT_MAPS = get_default_maps()    
SandRLocs = DEFAULT_MAPS[mapName].adjacency
SandRVics = DEFAULT_MAPS[mapName].victims
map_data = DEFAULT_MAPS[mapName]

batchOfFiles = {
    '--roomfile': map_data.room_file,
    '--portalfile': map_data.portals_file,
    '--victimfile' : map_data.victim_file,
    '--multitrial' : jdir,
    '--psychsimdir': outdir
}
## No return value. This will parse and write output files to outdir
getMessages(batchOfFiles)

############## Batch creaing and running psychsim actions
maxNumEvents = 9999
runStartsAt = 0
runEndsAt = 9999
parseFastFwdTo = 9999
runFastFwdTo = 9999

## For each parsed file, create a world and run it in
parsedFiles = os.listdir(outdir)
dones = []
for fi, fname in enumerate(parsedFiles):
    DEFAULT_MAPS = get_default_maps()    
    SandRLocs = DEFAULT_MAPS[mapName].adjacency
    SandRVics = DEFAULT_MAPS[mapName].victims
    map_data = DEFAULT_MAPS[mapName]

    msgfile = os.path.join(outdir, fname)
    parser = ProcessParsedJson('', DEFAULT_MAPS[mapName], logger=logging)
    parser.useParsedFile(msgfile)
    world, triageAgent, agent, victimsObj, world_map = make_single_player_world(
                        parser.player_name(), None, SandRLocs, SandRVics, False, True)

    #### Process the list of dicts into psychsim actions
    parser.getActionsAndEvents(victimsObj, world_map, SandRVics, parseFastFwdTo, maxNumEvents)
    #### Replay sequence of actions 
    parser.runTimeless(world, runStartsAt, runEndsAt, runFastFwdTo)

    dones.append(msgfile)