# -*- coding: utf-8 -*-
"""
Created on Mon Mar  9 18:11:14 2020

@author: mostafh
"""

from psychsim.pwl import state2agent, isStateKey, modelKey, rewardKey, Distribution
from victims import Victims
from locations import Locations

def printAgent(world, name):
    for key in world.state.keys():
        if isStateKey(key) and (state2agent(key) == name):
            print(key, world.getFeature(key))

def showOptions(triageAgent):
    for model in ['myopicMod','strategicMod']:
        result = triageAgent.decide(model=model)
        print(model, 'chooses:\n%s' % (result['action']))
#        print(model, 'chooses:\n%s' % (result[trueTriageModel]['action']))            
            
def setBeliefs(world, agent, triageAgent):    
    # Get the canonical name of the "true" player model
    trueTriageModel = next(iter(triageAgent.models.keys())) 
    
    # Agent does not model itself
    agent.resetBelief(ignore={modelKey(agent.name)})
    
    # Agent starts with uniform distribution over triageAgent MMs
    triageAgent.addModel('myopicMod',horizon=2,parent=trueTriageModel ,rationality=.8,selection='distribution')
    triageAgent.addModel('strategicMod',horizon=4,parent=trueTriageModel ,rationality=.8,selection='distribution')
    world.setMentalModel(agent.name,triageAgent.name,Distribution({'myopicMod': 0.5,'strategicMod': 0.5}))
    
    # Agent observes everything except triageAgent's reward received and true models 
    agent.omega = {key for key in world.state.keys() if key not in \
                   {modelKey(triageAgent.name),modelKey(agent.name)}} #rewardKey(triageAgent.name), 
    
            
def testMMBelUpdate(world, agent, triageAgent, destinations):
    setBeliefs(world, agent, triageAgent)
    sequence = [Locations.moveActions[triageAgent.name][dest] for dest in destinations]
    for action in sequence:
        print('Agent action: %s' % (action))
        world.step(action)  #result = 
        beliefs = agent.getBelief()
        assert len(beliefs) == 1 # Because we are dealing with a known-identity agent
        belief = next(iter(agent.getBelief().values()))
        print('Agent now models player as:')
        key = modelKey(triageAgent.name)
        print(world.float2value(key,belief[key]))