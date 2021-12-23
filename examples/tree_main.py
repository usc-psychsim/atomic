#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 21 11:27:19 2021

@author: mostafh
"""

import os.path
from rddl2psychsim.conversion.converter import Converter
from rddl2psychsim.conversion.task_tree import AllTrees, PROP, ACTION

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

allTrees.bulid(conv.world.dynamics)

#conv.world.step(actions, debug=debug, threshold=args.threshold, select=args.select)