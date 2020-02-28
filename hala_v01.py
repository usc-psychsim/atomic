# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.agent import Agent
from psychsim.pwl import modelKey, rewardKey, Distribution, stateKey

from fires import Fires
from victims import Victims
from locations import Locations

# create world and add human triageAgents
world = World()
fireAgent = Agent('FireAg1')
world.addAgent(fireAgent)
triageAgent = Agent('TriageAg1')
world.addAgent(triageAgent)
# ASIST Agent
agent = world.addAgent('ATOMIC')


################# Locations and Move actions
Locations.world = world
Locations.makeMap(6, [(0,1), (1,2), (2,3), (3,4), (1,5)])
Locations.makePlayerLocation(fireAgent, 0)
Locations.makePlayerLocation(triageAgent, 1)

Locations.makeMoveActions(fireAgent)
Locations.makeMoveActions(triageAgent)

################# Victims and triage actions
Victims.world = world
Victims.makeVictims([human.name for human in [fireAgent, triageAgent]])
Victims.makeTriageAction(triageAgent)
Victims.makeVictimReward(triageAgent)

################# Fires and extinguish actions
Fires.world = world
Fires.makeFires([2])
Fires.makeExtinguishActions(fireAgent)
Fires.makeFirePenalty(triageAgent)
Fires.makeFirePenalty(fireAgent)

################# Do stuff !!
           
#world.setOrder([{fireAgent.name}, {triageAgent.name}]) #, 
world.setOrder([{triageAgent.name}]) #, 

print('================= INIT')
world.printState()


## Set players horizons and make them unuaware of agent
for human in [triageAgent, fireAgent]:
    human.setAttribute('horizon',4)
    human.ignore(agent.name)

## 2 possible mental models with uniform belief over them
trueTriageModel = next(iter(triageAgent.models.keys())) # Get the canonical name of the "true" player model
triageAgent.addModel('myopicMod',horizon=2,parent=trueTriageModel ,rationality=.8,selection='distribution')
triageAgent.addModel('strategicMod',horizon=4,parent=trueTriageModel ,rationality=.8,selection='distribution')

# Agent does not model itself
agent.resetBelief(ignore={modelKey(agent.name)})

# Agent starts with uniform distribution over possible triageAgent models
world.setMentalModel(agent.name,triageAgent.name,Distribution({'myopicMod': 0.5,'strategicMod': 0.5}))

# Agent observes everything except triageAgent's reward received and true models ,rewardKey(triageAgent.name)
agent.omega = {key for key in world.state.keys() if key not in {modelKey(triageAgent.name),modelKey(agent.name)}}

#Locations.move(triageAgent, 2)
#world.printBeliefs(agent.name)
#Locations.move(triageAgent, 3)
#world.printBeliefs(agent.name)
#
for model in ['myopicMod','strategicMod']:
    result = triageAgent.decide(model=model)
    print(model, 'chooses:\n%s' % (result['action']))


sequence = [Locations.moveActions[triageAgent.name][2], Locations.moveActions[triageAgent.name][3]]
for action in sequence:
    print('Agent observes: %s' % (action))
    result = world.step(action)
    beliefs = agent.getBelief()
    assert len(beliefs) == 1 # Because we are dealing with a known-identity agent
    belief = next(iter(agent.getBelief().values()))
    print('Agent now models player as:')
    key = modelKey(triageAgent.name)
    print(world.float2value(key,belief[key]))
