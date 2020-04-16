# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World, WORLD
from psychsim.pwl import stateKey, Distribution, actionKey
from new_locations_fewacts import Locations, Directions
from victims_fewacts import Victims
from SandRMap import getSandRMap, getSandRVictims, getSmallSandRMap, getSmallSandRVictims, checkSRMap

def print_methods(obj):
    # useful for finding methods of an object
    obj = triageAgent
    object_methods = [method_name for method_name in dir(obj)
                      if callable(getattr(obj, method_name))]
    print(object_methods)


# MDP or POMDP
Victims.FULL_OBS = True

##################
##### Get Map Data
SandRLocs = getSandRMap()
SandRVics = getSandRVictims()
##################

world = World()
k = world.defineState(WORLD, 'seconds', int)
world.setFeature(k, 0)

triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')


VICTIMS_LOCS = list(SandRVics.keys())
VICTIM_TYPES = [SandRVics[v] for v in VICTIMS_LOCS]
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], list(SandRLocs.keys()))
Victims.makePreTriageActions(triageAgent)
Victims.makeTriageAction(triageAgent)

## Create triage agent's observation variables related to victims
if not Victims.FULL_OBS:
    Victims.makeVictimObservationVars(triageAgent)
    
################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMapDict(SandRLocs)
Locations.makePlayerLocation(triageAgent, "BH2")

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])

## Set players horizons
triageAgent.setAttribute('horizon',4)

## Set uncertain beliefs
if not Victims.FULL_OBS:
    triageAgent.omega = {actionKey(triageAgent.name)}
    triageAgent.omega = triageAgent.omega.union({stateKey(triageAgent.name, obs) for obs in \
                                                 ['obs_victim_status', 'obs_victim_reward', 'obs_victim_danger']})
    Victims.beliefAboutVictims(triageAgent)


