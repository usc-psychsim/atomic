# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey, Distribution, actionKey
from locations import Locations
from victims import Victims

def print_methods(obj):
    # useful for finding methods of an object
    obj = triageAgent
    object_methods = [method_name for method_name in dir(obj)
                      if callable(getattr(obj, method_name))]
    print(object_methods)

# MDP or POMDP
Victims.FULL_OBS = True

world = World()
triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')

# create a 'victim targeted' state that must be true for triage to be successful
vic_trgt = world.defineState(triageAgent.name,'vic_targeted',bool)
vic_targeted = False
triageAgent.setState('vic_targeted',vic_targeted)

################# Victims and triage actions
## One entry per victim
VICTIMS_LOCS = [2]
VICTIM_TYPES = [0]
Victims.world = world
Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name])
Victims.makePreTriageAction(triageAgent)
Victims.makeTriageAction(triageAgent)

## Create triage agent's observation variables related to victims
if not Victims.FULL_OBS:
    Victims.makeVictimObservationVars(triageAgent)

################# Locations and Move actions
Locations.world = world
Locations.makeMap([(0,1), (1,2)])
Locations.makePlayerLocation(triageAgent, 0)

## These must come before setting triager's beliefs
world.setOrder([{triageAgent.name}])

## Set uncertain beliefs
if not Victims.FULL_OBS:
    triageAgent.omega = {actionKey(triageAgent.name)}
    triageAgent.omega = triageAgent.omega.union({stateKey(triageAgent.name, obs) for obs in \
                                                 ['obs_victim_status', 'obs_victim_reward', 'obs_victim_danger']})
    Victims.beliefAboutVictims(triageAgent)


print("Initial State")
world.printBeliefs(triageAgent.name)

# move to victim and triage
move_to = 2
print("moving to ", move_to)
Locations.move(triageAgent, 2)
x = input("Press 'y' to do preTriage, 'n' to skip preTriage: ")
if x == 'y':
    Victims.pre_triage(triageAgent, 0)
elif x == 'n':
    # do nothing since default is False
    pass
else:
    print("did not recognize key, proceeding without preTriage")

print('##########')
print('victim_targeted:', triageAgent.getState('vic_targeted'))
print('##########')

input('Press key to apply triage')
Victims.triage(triageAgent, 0)
print(triageAgent.reward())

print('Final State')
world.printBeliefs(triageAgent.name)

#belief = next(iter(triageAgent.getBelief().values()))
#print(world.float2value(triageLoc,belief[triageLoc]))

#
#
#
#''' The true model of triageAgent has incorrect beliefs about its location
#    It also has info about victims, which shouldn't be there
#'''
#trueTriageModel = next(iter(triageAgent.models.keys()))
#print('triageAgent.models[trueTriageModel]')
#print('triage loc', triageAgent.models[trueTriageModel]['beliefs'][triageLoc])
#print('victim0 loc', triageAgent.models[trueTriageModel]['beliefs']['victim0\'s loc'])
