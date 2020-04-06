#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""

from psychsim.world import World, WORLD
from new_locations import Locations, Directions
from victims import Victims
from parser import DataParser

parser = DataParser('test.xlsx')

# MDP or POMDP
Victims.FULL_OBS = True

world = World()
k = world.defineState(WORLD, 'seconds', int)
world.setFeature(k, 0)

triageAgent = world.addAgent('Player279')
agent = world.addAgent('ATOMIC')

################# Victims and triage actions
## One entry per victim
VICTIMS_LOCS = ['Janitor_Closet_(J)', '201', '201', '205']
VICTIM_TYPES = [0, 0, 1, 0]
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], parser.locations)
Victims.makePreTriageAction(triageAgent)
Victims.makeTriageAction(triageAgent)

## Create triage agent's observation variables related to victims
if not Victims.FULL_OBS:
    Victims.makeVictimObservationVars(triageAgent)

################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMap([('Left_Hallway_Branch',Directions.E, 'Janitor_Closet_(J)'), \
                   ('Left_Hallway_Branch',Directions.W,'201'), \
                   ('Left_Hallway_Branch',Directions.N,'205')])
Locations.makePlayerLocation(triageAgent)

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])


