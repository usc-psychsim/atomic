# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World, WORLD
from psychsim.pwl import stateKey, Distribution, actionKey
from new_locations import Locations, Directions
from victims import Victims
from helpers import testMMBelUpdate
from SandRMap import getSandRMap, getSandRVictims, getSmallSandRMap, getSmallSandRVictims

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
SandRLocs = getSmallSandRMap()
SandRVics = getSmallSandRVictims()
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
#  ictims.makePreTriageAction(triageAgent)
Victims.makeTriageAction(triageAgent)

## Create triage agent's observation variables related to victims
if not Victims.FULL_OBS:
    Victims.makeVictimObservationVars(triageAgent)

################# Locations and Move actions
Locations.EXPLORE_BONUS = 0
Locations.world = world
#Locations.makeMap([(0,1), (1,2), (1,3)])
#  Locations.makeMap([])
Locations.makeMapDict(SandRLocs)
input("press key to proceed")
Locations.makePlayerLocation(triageAgent, "LH2")
input("completed")

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


######################
## Beign Simulation
######################
print('Initial State')
world.printBeliefs(triageAgent.name)

cmd = 'blank'
#
#while cmd != '':
#    legalActions = triageAgent.getActions()
#    agent_state = triageAgent.getState('loc')
#    print("Player state: ", agent_state)
#    print("reward: ",triageAgent.reward())
#    #  print(triageAgent.getAttribute('R',model='TriageAg10'))
#    print('Legal Actions:')
#    for a,n in zip(legalActions,range(len(legalActions))):
#        print(n,': ',a)
#
#    print()
#    cmd = input('select action, or type "s" to print belief, press return with no entry to stop: ')
#    try:
#        cmd_int = int(cmd)
#        Victims.world.step(list(legalActions)[cmd_int])
#    except:
#        #do nothing
#        pass
#
#    if cmd == 's':
#        world.printBeliefs(triageAgent.name)
#        print('Triage Agent Reward: ', triageAgent.reward())
#    elif cmd == '':
#        print('Finishing Simulation')
