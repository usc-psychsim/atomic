# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World, WORLD
from psychsim.pwl import stateKey, actionKey
from new_locations_fewacts import Locations, Directions
from victims_fewacts import Victims
from SandRMap import getSandRMap, getSandRVictims, getSmallSandRMap, getSmallSandRVictims, checkSRMap
from helpers import testMMBelUpdate

# MDP or POMDP
Victims.FULL_OBS = True

##################
##### Get Map Data
SandRLocs = getSmallSandRMap() # getSandRMap()
SandRVics = getSmallSandRVictims() # getSandRVictims()
##################

world = World()
#k = world.defineState(WORLD, 'seconds', int)
#world.setFeature(k, 0)

triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')


VICTIMS_LOCS = list(SandRVics.keys())
VICTIM_TYPES = [SandRVics[v] for v in VICTIMS_LOCS]
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], list(SandRLocs.keys()))
Victims.makePreTriageActions(triageAgent)
Victims.makeTriageAction(triageAgent)
    
################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMapDict(SandRLocs)
Locations.makePlayerLocation(triageAgent, "BH2")

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])

## Set players horizons
triageAgent.setAttribute('horizon',4)

actions = [Locations.moveActions[triageAgent.name][Directions.E],
           [Victims.STR_FOV_VAR, 'victim3']
#           Victims.getPretriageAction(triageAgent.name, Victims.crosshairActs),
#           Victims.getPretriageAction(triageAgent.name, Victims.approachActs)
        ]
#Locations.move(triageAgent, Directions.E)
testMMBelUpdate(world, agent, triageAgent, actions, Locations)