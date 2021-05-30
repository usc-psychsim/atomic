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
#    pickle.dump(msg_qs.jsonParser.vList, f)

def generate_rddl_map(rooms, edges):
    nbr_str = ''
    for (rm1, rm2) in edges:
        nbr_str = nbr_str + 'nbr(%s, %s) = true;' % (rm1, rm2) + '\n'
    loc_str = ','.join(rooms)
    return loc_str, nbr_str

def generate_rddl_victims(victim_pickle):
    with open(victim_pickle, 'rb') as f:    
        vList = pickle.load(f)
    
    reg_dict = {}
    crit_dict = {}
    
    for vic in vList:
        rm = vic['room_name']
        if rm == '':
            continue
        if vic['block_type'] == 'critical':
            d = crit_dict
        else:
            d = reg_dict
        
        if rm not in d.keys():
            d[rm] = 0
        d[rm] = d[rm] +1

    vic_str = ''
    for rm, ctr in crit_dict.items():
        vic_str = vic_str + 'vcounter_unsaved_critical(%s) = %d;\n' % (rm, ctr)
    for rm, ctr in reg_dict.items():
        vic_str = vic_str + 'vcounter_unsaved_regular(%s) = %d;\n' % (rm, ctr)
    return vic_str

def make_rddl_inst(rooms, edges,
                   victim_pickle = '../data/rddl_psim/victims.pickle',                    
                    rddl_template =  '../data/rddl_psim/sar_mv_tr_template.rddl',
                    inst_name = 'inst1'):
    ''' Create a RDDL instance from a RDDL template containing everything but the locations and adjacency info 
        which are obtained from a semantic map.    '''


    loc_str, nbr_str = generate_rddl_map(rooms, edges)
    vic_str = generate_rddl_victims(victim_pickle)
    
    rddl_temp_file = open(rddl_template, "r")
    
    rddl_str = rddl_temp_file.read()
    rddl_str = rddl_str.replace('LOCSTR', loc_str).replace('NBRSTR', nbr_str).replace('VICSTR', vic_str)
    
    rddl_out = rddl_template.replace('template', inst_name)
    rddl_inst_file = open(rddl_out, "w")
    rddl_inst_file.write(rddl_str)
    
    rddl_temp_file.close()
    rddl_inst_file.close()