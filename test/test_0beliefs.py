# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World, WORLD
from psychsim.pwl import stateKey, actionKey
from new_locations_fewacts import Locations, Directions
from victims_fewacts import Victims
from helpers import runMMBelUpdate, setBeliefsNoVics

# MDP or POMDP
Victims.FULL_OBS = True

world = World()
triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')

VICTIMS_LOCS = ['E1']
VICTIM_TYPES = ['Orange']
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], ['BH1','E1'])
Victims.makePreTriageActions(triageAgent)
Victims.makeTriageAction(triageAgent)

Victims.P_VIC_FOV = (1.0 - Victims.P_EMPTY_FOV) / len(Victims.victimAgents)

################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMapDict({'BH1':{Directions.E:'E1'}, 'E1':{Directions.W:'BH1'}})
Locations.makePlayerLocation(triageAgent, "E1")

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])

## Set players horizons
triageAgent.setAttribute('horizon',4)

actions = [Locations.moveActions[triageAgent.name][Directions.W],
           Locations.moveActions[triageAgent.name][Directions.E]]

############### The following breaks the assertion len(agent.getBelief()) ==1 
## I think the fact that the player doesn't move W makes the obs that he moves E when he's still
## in E1 impossible. This causes a belief of 0
setBeliefsNoVics(world, agent, triageAgent)
runMMBelUpdate(world, agent, triageAgent, actions, Locations)