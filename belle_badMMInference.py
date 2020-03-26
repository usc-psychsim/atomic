# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey, Distribution, actionKey
from locations import Locations
from victims import Victims
from helpers import testMMBelUpdate, tryHorizon

Victims.FULL_OBS = True

world = World()
triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')

################# Victims and triage actions
## One entry per victim
VICTIMS_LOCS = [3]
VICTIM_TYPES = [0]
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name])
Victims.makeTriageAction(triageAgent)

################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMap([(0,1), (1,2), (1,3)])
Locations.makePlayerLocation(triageAgent, 0)

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])

## Set player horizon
triageAgent.setAttribute('horizon',4)
    
""" 
Setting: 1) full obs, 2) no exploration bonus, 3) Victim at loc 3
Player init at loc 0
Both myopic and strategic would move to loc 1
If player then moves to 2, no way he's strategic.
But in the following, agent doesn't correctly update belief over MM
and has 50-50 belief over myopic/strategic after player moves to 2.
"""          
testMMBelUpdate(world, agent, triageAgent, [1,2])
