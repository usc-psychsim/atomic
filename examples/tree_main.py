#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 21 11:27:19 2021

@author: mostafh
"""

import os.path
from rddl2psychsim.conversion.converter import Converter
from rddl2psychsim.conversion.task_tree import AllTrees, PROP, ACTION
from psychsim.action import ActionSet


RDDL_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'rddl_psim', 'know1_tree.rddl')
conv = Converter()
conv.convert_file(RDDL_FILE, verbose=False)

allTrees = AllTrees(True)

## Names of un-grounded actions
#generic_action_names = [act_fluent.name for act_fluent in conv.model.domain.action_fluents.values()]

## Create fluent nodes
for feat_name, psim_name in conv.features.items():
    val = conv.world.getFeature(psim_name)    
    allTrees.create_node(feat_name, PROP, psim_name, val)


def clean_strs(psim_strs, rmv):
    v1 = set(k.replace('\'', '') for k in psim_strs)
    v2 = [a[a.index('('):] for a in v1 if len(a)>0]
    v2.remove(rmv)
    return v2
    
for key, dyn_dict in conv.world.dynamics.items():
    if type(key) == ActionSet:
        a1lst = [a for a in key][0]
        a_name = a1lst['verb']
        ## Add the action node
        allTrees.create_node(a_name, ACTION, a_name, False)
        ## Add an edge for the action-fluent dependency
        for affected_psim_name in dyn_dict.keys():
            aff_name = affected_psim_name[affected_psim_name.index('('):]
            print('\nattaching: action', a_name, aff_name)
            allTrees.attach(aff_name, a_name)
            
    if type(key) == str:        
        affected_name = key[key.index('('):]
        ## If the single key in dyn_dict is True, this is a fluent that depends
        ## on other fluents and wasn't captured above
#        if (len(dyn_dict) == 1) and (True in dyn_dict.keys()):
        for tkey in dyn_dict.keys():
            affecting = clean_strs(dyn_dict[tkey].keys(), affected_name) 
#            print(affected_name, tkey, str(dyn_dict[tkey]))
            for affing in affecting:  
                print('\nattaching:', affected_name, affing, '\n')
                allTrees.attach(affected_name, affing)
#        else:
#            for 