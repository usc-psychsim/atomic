# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey, Distribution, actionKey
from locations import Locations
from victims import Victims

Victims.FULL_OBS = False

world = World()
triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')

################# Victims and triage actions
## One entry per victim
VICTIMS_LOCS = [2]
VICTIM_TYPES = [0]
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name])
Victims.makeTriageAction(triageAgent)

## Create triage agent's observation variables related to victims
if not Victims.FULL_OBS:
    Victims.makeVictimObservationVars(triageAgent)

################# Locations and Move actions
Locations.world = world
Locations.makeMap([(0,1), (1,2)])
initTLoc = 0
Locations.makePlayerLocation(triageAgent, initTLoc)

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])
triageAgent.omega = {actionKey(triageAgent.name)}

## Set uncertain beliefs
if not Victims.FULL_OBS:
    triageAgent.omega = triageAgent.omega.union(\
                        {stateKey(triageAgent.name, obs) for obs in \
                        ['obs_victim_status', 'obs_victim_reward', 'obs_victim_danger']})
    Victims.beliefAboutVictims(triageAgent)

print('======= Init at', initTLoc)
world.printBeliefs(triageAgent.name)

"""
Victim is in loc 2.
Triager originally in loc 0 where it has uniform belief over victim being in 0,1,2
When Triager moves to 1, its belief should assign 0 to victim being in 1. But that only happens
when triager moves to 2.
When Triager moves to 2, its belief should assign 1 to victim being in 2. But that only happens
when triager moves to back to 1.
"""

for nxt in [1,2,1]:
    Locations.move(triageAgent, nxt)
    print('======= After moving to ', nxt)    
    world.printBeliefs(triageAgent.name)
