# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey
from locations import Locations
from victims import Victims

world = World()
triageAgent = world.addAgent('TriageAg1')
agent = world.addAgent('ATOMIC')

################# Victims and triage actions
Victims.world = world
Victims.makeVictims([triageAgent.name])
Victims.makeTriageAction(triageAgent)
Victims.makeVictimObs(triageAgent)

################# Locations and Move actions
Locations.world = world
Locations.makeMap(4, [(0,1), (1,2), (2,3)])
Locations.makePlayerLocation(triageAgent, 1)

world.setOrder([{triageAgent.name}])


triageAgent.resetBelief()
Victims.ignoreVictims(triageAgent)
           
triageLoc = stateKey(triageAgent.name, 'loc')

Locations.move(triageAgent, 2)


'''  World shows triage player to correct belief about its location
     But beliefs include info about victims, which shouldn't be there. triageAgent.omega doesn't have
     victim info.
'''
print('world.printBeliefs')
world.printBeliefs(triageAgent.name)



''' The true model of triageAgent has incorrect beliefs about its location
    It also has info about victims, which shouldn't be there
'''
trueTriageModel = next(iter(triageAgent.models.keys())) 
print('triageAgent.models[trueTriageModel]')
print('triage loc', triageAgent.models[trueTriageModel]['beliefs'][triageLoc])
print('victim0 loc', triageAgent.models[trueTriageModel]['beliefs']['victim0\'s loc'])