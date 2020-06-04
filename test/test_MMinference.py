# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from new_locations_fewacts import Locations, Directions
from victims_fewacts import Victims
from helpers import testMMBelUpdate

Victims.FULL_OBS = True

world = World()
triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')

################# Victims and triage actions
## One entry per victim
VICTIMS_LOCS = ['3']
VICTIM_TYPES = ['Green']
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], ['0', '1', '2', '3'])
Victims.makePreTriageActions(triageAgent)
Victims.makeTriageAction(triageAgent)

################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
Locations.makeMap([('0',Directions.E, '1'), ('1',Directions.E,'2'), ('1',Directions.S,'3')])
Locations.makePlayerLocation(triageAgent, '1')

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
#testMMBelUpdate(world, agent, triageAgent, [Directions.E, Directions.E], Locations)
