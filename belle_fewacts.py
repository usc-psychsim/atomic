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
from helpers import runMMBelUpdate, setBeliefs, setBeliefsNoVics
from ftime import FatherTime

# MDP or POMDP
Victims.FULL_OBS = True

##################
##### Get Map Data
SandRLocs = getSmallSandRMap()
SandRVics = getSmallSandRVictims()
##################

world = World()

triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')
clock = FatherTime(world, False)


VICTIMS_LOCS = list(SandRVics.keys())
VICTIM_TYPES = [SandRVics[v] for v in VICTIMS_LOCS]
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], list(SandRLocs.keys()))
Victims.makePreTriageActions(triageAgent)
Victims.makeTriageAction(triageAgent)

Victims.P_VIC_FOV = (1.0 - Victims.P_EMPTY_FOV) / len(Victims.victimAgents)

################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMapDict(SandRLocs)
Locations.makePlayerLocation(triageAgent, "E2")

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])

## Set players horizons
triageAgent.setAttribute('horizon',4)

####### Test if action effects are back
#Locations.move(triageAgent, Directions.W)
#clock.tick()
#world.printState(beliefs=False)


###############  ACTIVATE *ONE* OF THE FOLLOWING BLOCKS TO SEE THE ASSOCIATED ISSUE ############### 

############### The following shows incorrect beleifs of the triager about his own last 
############### action and thus new location.
#setBeliefsNoVics(world, agent, triageAgent)
#Locations.move(triageAgent, Directions.W)
#world.printBeliefs(triageAgent.name)


########## Empty world state!
#setBeliefsNoVics(world, agent, triageAgent)
#Locations.move(triageAgent, Directions.W)
#world.printState(beliefs=False)


############### The following breaks the assertion len(agent.getBelief()) ==1 
############### action and thus new location.
actions = [Locations.moveActions[triageAgent.name][Directions.W],
           [Victims.STR_FOV_VAR, 'victim3'],
           Locations.moveActions[triageAgent.name][Directions.E]]
#           Victims.getPretriageAction(triageAgent.name, Victims.crosshairActs)]
runMMBelUpdate(world, agent, triageAgent, actions, Locations)