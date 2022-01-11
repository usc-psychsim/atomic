#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 15 17:27:09 2021

@author: mostafh
"""

import pickle
import pandas as pd
import json
import os
from atomic.parsing.map_parser import read_semantic_map
from atomic.parsing.remap_connections import transformed_connections

SIMPLE_COLLAPSE = 0
MAX_NBR_COLLAPSE = 1
NO_COLLAPSE = 2

def generate_rddl_map(rooms, edges):
    nbr_str = ''
    for (rm1, rm2) in edges:
        nbr_str = nbr_str + 'nbr(%s, %s) = true;' % (rm1, rm2) + '\n'
    loc_str = ','.join(rooms)
    return loc_str, nbr_str


def generate_rddl_map_portals(neighbors):
    nbr_str = ''    
    for room, nbrs in neighbors.items():
        for i, nbr in enumerate(nbrs):
            nbr_str += f'NBR-{i}({room}) = {nbr};\n'
            nbr_str += f'HAS-NBR-{i}({room}) = true;\n'
    loc_str = ','.join(neighbors.keys())
    return loc_str, nbr_str

def generate_rddl_victims_from_list_named_vics(vList, rooms):
    vic_str = ''
    for vic in vList:
        rm = vic['room_name']
            
        if rm == '':
            print('WARNING: victim in empty room', vic)
            continue
                    
        if rm not in rooms:
            print('WARNING: victim in unknown room', rm)
            continue
        
        vic_str = vic_str + 'vloc(v' + str(vic['unique_id']) + ', ' + rm + ') = true;\n'
        
    return vic_str

def generate_rddl_victims_from_list(vList, rooms):
    reg_dict = {}
    crit_dict = {}

    for vic in vList:
        rm = vic['room_name']
            
        if rm == '':
            print('WARNING: victim in empty room', vic)
            continue
                    
        if rm not in rooms:
            print('WARNING: victim in unknown room', rm)
            continue
        
        if vic['block_type'] == 'critical':
            d = crit_dict
        else:
            d = reg_dict

        if rm not in d.keys():
            d[rm] = 0
        d[rm] = d[rm] + 1

    vic_str = ''
    for rm, ctr in crit_dict.items():
        vic_str = vic_str + 'vcounter_unsaved_critical(%s) = %d;\n' % (rm, ctr)
    for rm, ctr in reg_dict.items():
        vic_str = vic_str + 'vcounter_unsaved_regular(%s) = %d;\n' % (rm, ctr)
    return vic_str



def generate_rddl_victims(victim_pickle, rooms, room_name_lookup, collapse_method):
    with open(victim_pickle, 'rb') as f:
        vList = pickle.load(f)

    reg_dict = {}
    crit_dict = {}

    for vic in vList:
        rm = vic['room_name']
        if collapse_method == SIMPLE_COLLAPSE:
            rm = rm.split('_')[0]
            
        if rm == '':
            print('WARNING: victim in empty room', vic)
            continue
        
        if collapse_method == SIMPLE_COLLAPSE:
            if rm not in room_name_lookup.keys():
                print('WARNING: victim in room without a new name', vic)
                continue
            rm = room_name_lookup[rm]
            
        if rm not in rooms:
            print('WARNING: victim in unknown room', rm)
            continue
        
        if vic['block_type'] == 'critical':
            print(vic)
            d = crit_dict
        else:
            d = reg_dict

        if rm not in d.keys():
            d[rm] = 0
        d[rm] = d[rm] + 1

    vic_str = ''
    for rm, ctr in crit_dict.items():
        vic_str = vic_str + 'vcounter_unsaved_critical(%s) = %d;\n' % (rm, ctr)
    for rm, ctr in reg_dict.items():
        vic_str = vic_str + 'vcounter_unsaved_regular(%s) = %d;\n' % (rm, ctr)
    return vic_str


def generate_rddl_move_actions(neighbors):
    max_nbr = max([len(nbrs) for nbrs in neighbors.values()])
    nbr_consts = '\n\t'.join(f'NBR-{i}(loc) : {{ non-fluent, loc, default = null }};' for i in range(max_nbr)) + '\n\t'
    nbr_consts += '\n\t'.join(f'HAS-NBR-{i}(loc) : {{ non-fluent, bool, default = false }};' for i in range(max_nbr))
    move_vars = '\n\t'.join(f'move-{i}(agent) : {{ action-fluent, bool, default = false}};' for i in range(max_nbr))

    move_dyn = '\n\t'.join(f'if ( move-{i}(?p) ) then\n\t\tNBR-{i}(pLoc(?p))\nelse ' for i in range(max_nbr))
    move_dyn += '\n\tpLoc(?p);'

    move_pre_cond = '\n\t'.join(f'forall_{{?p: agent}} [ move-{i}(?p) => HAS-NBR-{i}(pLoc(?p)) ];'
                                for i in range(max_nbr))

    return nbr_consts, move_vars, move_dyn, move_pre_cond


def make_rddl_inst(rooms, edges,
                   victim_pickle='../data/rddl_psim/victims.pickle',
                   rddl_template='../data/rddl_psim/sar_mv_tr_template.rddl',
                   rddl_out='../data/rddl_psim/sar_mv_tr_inst1.rddl'):
    ''' Create a RDDL instance from a RDDL template containing everything but the locations and adjacency info 
        which are obtained from a semantic map.    '''

    loc_str, nbr_str = generate_rddl_map(rooms, edges)
    vic_str = generate_rddl_victims(victim_pickle)

    rddl_temp_file = open(rddl_template, "r")

    rddl_str = rddl_temp_file.read()
    rddl_str = rddl_str.replace('LOCSTR', loc_str).replace('NBRSTR', nbr_str).replace('VICSTR', vic_str)

    rddl_inst_file = open(rddl_out, "w")
    rddl_inst_file.write(rddl_str)

    rddl_temp_file.close()
    rddl_inst_file.close()


def make_rddl_inst_fol(edges, room_name_lookup, collapse_method, 
                       rddl_template,
                       rddl_out,
                       victim_pickles,
                       map_out_csv,
                       generate_victims):
    ''' Create a RDDL instance from a RDDL template containing everything but the locations and adjacency info
        which are obtained from a semantic map.    '''

    neighbors = {}
    for r1, r2 in edges:
        if collapse_method == SIMPLE_COLLAPSE:
            r1 = r1.split('_')[0]
            r2 = r2.split('_')[0]
            if r1 == r2:
                continue
            
        if r1 not in neighbors:
            neighbors[r1] = set()
        if r2 not in neighbors:
            neighbors[r2] = set()
        if len(neighbors[r1]) < MAX_NBRS:
            neighbors[r1].add(r2)
        else:
            print('WARNING: throwing away edge from', r1, 'to', r2)
        if len(neighbors[r2]) < MAX_NBRS:
             neighbors[r2].add(r1)
        else:
            print('WARNING: throwing away edge from', r2, 'to', r1)

    max_nbr = max([len(nbrs) for nbrs in neighbors.values()])
    print('Maximum number of neighbors', max_nbr)
    df = pd.DataFrame.from_dict(neighbors, orient='index', columns=[f'NBR{i}' for i in range(max_nbr)])
    df.index.name = 'ROOM'
    df.fillna("",inplace=True)    
    df.to_csv(map_out_csv)

    loc_str, nbr_str = generate_rddl_map_portals(neighbors)
    init_loc = list(neighbors.keys())[0]
    nbr_consts, move_vars, move_dyn, move_pre_cond = generate_rddl_move_actions(neighbors)

    rddl_temp_file = open(rddl_template, "r")

    master_rddl_str = rddl_temp_file.read()

    rddl_str = master_rddl_str.replace('LOCSTR', loc_str).replace('NBRSTR', nbr_str).\
                replace('NBR_CONSTS_STR', nbr_consts).replace('MOVE_VARS_STR', move_vars).replace('MOVE_DYN_STR', move_dyn). \
                replace('MOVE_PRE_COND', move_pre_cond).replace('LOC0', init_loc)
    
    if generate_victims:
        for tag, victim_pickle in victim_pickles.items():
            vic_str = generate_rddl_victims(victim_pickle, set(neighbors.keys()), room_name_lookup, collapse_method)
            rddl_str = rddl_str.replace('VICSTR', vic_str)   
            rddl_inst_file = open(rddl_out + tag + '.rddl', "w")
            rddl_inst_file.write(rddl_str)    
            rddl_inst_file.close()
    else:
        rddl_inst_file = open(rddl_out + '_novics.rddl', "w")
        rddl_inst_file.write(rddl_str)    
        rddl_inst_file.close()
        

    rddl_temp_file.close()


if __name__ == '__main__':
    collapse_method = MAX_NBR_COLLAPSE
    map_file = '../maps/Saturn/Saturn_1.5_3D_sm_v1.0.json'
    MAX_NBRS = 14
    edges = []
    
    if collapse_method == SIMPLE_COLLAPSE:
        rooms, edges = read_semantic_map(map_file)
        room_name_lookup = {rm:rm for rm in rooms.keys()}
    elif collapse_method == MAX_NBR_COLLAPSE:
        orig_map = json.load(open(map_file,'r'))
        one_way_edges, room_name_lookup, new_map, orig_map = transformed_connections(orig_map)
        has_edge = set( [a for a,b in one_way_edges] + [b for a,b in one_way_edges] )
        isolated_rooms = [rm for rm in room_name_lookup.values() if rm not in has_edge]
        
        
        for a,b in one_way_edges:
            edges.append((a,b))
            edges.append((b,a))
            
    generate_victims = False
    
    if generate_victims:
        victim_pickles = {}
        for tag in ['A', 'B']:
            victim_pickles[tag] = os.path.join(os.path.dirname(__file__), '..', 'data', 'rddl_psim', 'victims'+tag+'.pickle')
        make_rddl_inst_fol(edges, room_name_lookup, collapse_method, 
                           '../data/rddl_psim/newpickup_template.rddl',
                           '../data/rddl_psim/newpickup_v1',
                           victim_pickles,
                           '../maps/Saturn/rddl_clpsd_neighbors.csv', generate_victims)
    else:
        make_rddl_inst_fol(edges, room_name_lookup, collapse_method, 
                           '../data/rddl_psim/newpickup_template.rddl',
                           '../data/rddl_psim/newpickup_v1',
                           None,
                           '../maps/Saturn/rddl_clpsd_neighbors.csv', generate_victims)
