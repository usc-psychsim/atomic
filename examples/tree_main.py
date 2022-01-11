#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 21 11:27:19 2021

@author: mostafh
"""

import os.path
from rddl2psychsim.conversion.converter import Converter
from rddl2psychsim.conversion.task_tree import AllTrees, PROP

RDDL_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'rddl_psim', 'study3/other.rddl')
conv = Converter()
conv.convert_file(RDDL_FILE, verbose=False)

allTrees = AllTrees(True)

## From the RDDL model: un-grounded actions
#generic_action_names = [act_fluent.name for act_fluent in conv.model.domain.action_fluents.values()]

## Create fluent nodes
for feat_name, psim_name in conv.features.items():
    val = conv.world.getFeature(psim_name)    
    allTrees.create_node(psim_name, PROP, psim_name, val)
    

allTrees.build(conv.world.dynamics, {player.name:player.legal for player in conv.world.agents.values()})
allTrees.print()

#conv.world.step(actions, debug=debug, threshold=args.threshold, select=args.select)