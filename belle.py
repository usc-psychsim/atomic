# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.agent import Agent
from psychsim.pwl import modelKey, rewardKey, Distribution, stateKey
from locations import Locations

# create world and add human triageAgents
world = World()
triageAgent = Agent('TriageAg1')
world.addAgent(triageAgent)
# ASIST Agent
agent = world.addAgent('ATOMIC')


################# Locations and Move actions
Locations.world = world
Locations.makeMap(4, [(0,1), (1,2), (2,3)])
Locations.makePlayerLocation(triageAgent, 1)

           
world.setOrder([{triageAgent.name}]) #, 
triageLoc = stateKey(triageAgent.name, 'loc')
trueTriageModel = next(iter(triageAgent.models.keys())) 

#print(triageAgent.models[trueTriageModel]['beliefs'])
#triageAgent.resetBelief()
#print(triageAgent.models[trueTriageModel]['beliefs'][triageLoc])

Locations.move(triageAgent, 2)
print(triageAgent.models[trueTriageModel]['beliefs'][triageLoc])
