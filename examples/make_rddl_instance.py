#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 15 17:27:09 2021

@author: mostafh
"""

import pickle

from atomic.parsing.map_parser import read_semantic_map
from atomic.definitions import GOLD_STR, GREEN_STR


#with open('../data/rddl_psim/victims.pickle', 'wb') as f:    
#    pickle.dump(SandRVics, f)

def generate_rddl_map(map_file):
    rooms, edges = read_semantic_map(map_file)
    nbr_str = ''
    for (rm1, rm2) in edges:
        nbr_str = nbr_str + 'nbr(%s, %s) = true;' % (rm1, rm2) + '\n'
    loc_str = ','.join(rooms)
    return loc_str, nbr_str

def generate_rddl_victims(victim_pickle):
    with open(victim_pickle, 'rb') as f:    
        SandRVics = pickle.load(f)
    vic_str = ''
    for room, vics in SandRVics.items():
        if room == '':
            continue
        gold_ct = vics.count(GOLD_STR)
        green_ct = vics.count(GREEN_STR)
        if gold_ct > 0:
            vic_str = vic_str + 'vcounter_unsaved_critical(%s) = %d;\n' % (room, gold_ct)
        if green_ct > 0:
            vic_str = vic_str + 'vcounter_unsaved_regular(%s) = %d;\n' % (room, green_ct)
    return vic_str

def make_rddl_inst(victim_pickle = '../data/rddl_psim/victims.pickle',
                    map_file =       '../maps/Saturn/Saturn_1.5_3D_sm_v1.0.json',
                    rddl_template =  '../data/rddl_psim/sar_mv_tr_template.rddl',
                    inst_name = 'inst1'):
    ''' Create a RDDL instance from a RDDL template containing everything but the locations and adjacency info 
        which are obtained from a semantic map.    '''


    loc_str, nbr_str = generate_rddl_map(map_file)
    vic_str = generate_rddl_victims(victim_pickle)
    
    rddl_temp_file = open(rddl_template, "r")
    
    rddl_str = rddl_temp_file.read()
    rddl_str = rddl_str.replace('LOCSTR', loc_str).replace('NBRSTR', nbr_str).replace('VICSTR', vic_str)
    
    rddl_out = rddl_template.replace('template', inst_name)
    rddl_inst_file = open(rddl_out, "w")
    rddl_inst_file.write(rddl_str)
    
    rddl_temp_file.close()
    rddl_inst_file.close()