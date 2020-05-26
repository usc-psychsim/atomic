#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 17:00:50 2020

@author: mostafh
"""

from psychsim.world import World, WORLD
from new_locations_fewacts import Locations
from victims_fewacts import Victims
from parser import DataParser
from SandRMap import getSandRMap


def printAEs(aes):
    for ae in aes:
        print(ae[1])

# MDP or POMDP
Victims.FULL_OBS = True

world = World()
k = world.defineState(WORLD, 'seconds', int)
world.setFeature(k, 0)

triageAgent = world.addAgent('Player279')
agent = world.addAgent('ATOMIC')

##### Get Map Data
SandRLocs = getSandRMap()

## Parse data file. NOTE: colors in file are ignored.
## An orange victim in every room that has 1+ victims.
## A green victim in every room that has 2 victims.
parser = DataParser('augmented_data_w_successful_triage_attempts_short.csv')


################# Victims and triage actions
Victims.world = world
Victims.makeOrangeGreenVictims(parser.rooms1Victim, parser.rooms23Victim, [triageAgent.name])
Victims.makePreTriageActions(triageAgent)
Victims.makeTriageAction(triageAgent)

################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMapDict(SandRLocs)
Locations.makePlayerLocation(triageAgent, "BH2")

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])


#
### Parse the data file into a sequence of actions and events
#aes = parser.getActionsAndEvents(triageAgent.name)
### Get actions and events related to a given triage attempt
#atm = DataParser.getTimelessAttempt(world, triageAgent.name, aes, 'SA8')
### Inject the player's location at the beginning of the attempt in question
#atm = [[0, 'R218', 'March 12th 2020, 19:13:00.022', 'nan']] + atm
#printAEs(atm)
#DataParser.runTimeless(world, triageAgent.name, atm)
