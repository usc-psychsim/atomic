# -*- coding: utf-8 -*-
"""
Created on Mon Mar  9 18:11:14 2020

@author: mostafh
"""

from psychsim.pwl import state2agent, isStateKey, modelKey, rewardKey, Distribution, actionKey, stateKey
import psychsim.action

def anding(rows, ifTrue, ifFalse):
    if rows == []:
        return ifTrue
    return {'if': rows[0],
            True: anding(rows[1:], ifTrue, ifFalse),
            False: ifFalse}

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
    
    triageAgent.resetBelief(ignore={modelKey(agent.name)})
    triageAgent.omega = {key for key in world.state.keys() if key not in \
                   {modelKey(agent.name)}} #

    # Agent starts with uniform distribution over triageAgent MMs
    triageAgent.addModel('myopicMod',horizon=2,parent=trueTriageModel ,rationality=.8,selection='distribution')
    triageAgent.addModel('strategicMod',horizon=4,parent=trueTriageModel ,rationality=.8,selection='distribution')
    world.setMentalModel(agent.name,triageAgent.name,Distribution({'myopicMod': 0.5,'strategicMod': 0.5}))
    
    # Agent observes everything except triageAgent's reward received and true models 
    agent.omega = {key for key in world.state.keys() if key not in \
                   {modelKey(triageAgent.name),modelKey(agent.name)}} #rewardKey(triageAgent.name),

def setBeliefsNoVics(world, agent, triageAgent):    
    # Get the canonical name of the "true" player model
    trueTriageModel = next(iter(triageAgent.models.keys())) 
    
    # Agent does not model itself
    agent.resetBelief(ignore={modelKey(agent.name)})
    
    # Triager does not model victims or the ASIST agent
    dontBelieve = set([modelKey(agent.name)] + \
                     [key for key in world.state.keys() if key.startswith('victim')])
    triageAgent.resetBelief(ignore=dontBelieve)
            
    # Agent starts with uniform distribution over triageAgent MMs
    triageAgent.addModel('myopicMod',horizon=2,parent=trueTriageModel ,rationality=.8,selection='distribution')
    triageAgent.addModel('strategicMod',horizon=4,parent=trueTriageModel ,rationality=.8,selection='distribution')
    world.setMentalModel(agent.name,triageAgent.name,Distribution({'myopicMod': 0.5,'strategicMod': 0.5}))
    
    # Agent observes everything except triageAgent's reward received and true models 
    agent.omega = {key for key in world.state.keys() if key not in \
                   {modelKey(triageAgent.name),modelKey(agent.name)}} #rewardKey(triageAgent.name),
    

def printASISTBel(world, triageAgent, agent):
    belief = next(iter(agent.getBelief().values()))
    print('Agent now models player as:')
    key = modelKey(triageAgent.name)
    print(world.float2value(key,belief[key]))
            
def runMMBelUpdate(world, agent, triageAgent, actions, Locations):
    for action in actions:
        if type(action) == psychsim.action.ActionSet:
            print('===Agent action: %s' % (action))
            world.step(action)  #result = 
            beliefs = agent.getBelief()
            print('len(beliefs)', len(beliefs))
            assert len(beliefs) == 1 # Because we are dealing with a known-identity agent
            belief = next(iter(agent.getBelief().values()))
            print('Agent now models player as:')
            key = modelKey(triageAgent.name)
            print(world.getFeature(key,belief))
        else:
            [var, val] = action
            print('===Setting feature', var, val)
            world.setState(triageAgent.name, var, val)
        print('--World state')
        world.printState(beliefs=False)
#    world.printState()
    
        
def tryHorizon(world, hz, triageAgent, initLoc):
    pos = stateKey(triageAgent.name, 'loc')
    for i in range(1, hz + 1):
        print('====================================')
        print('Horizon: {}'.format(str(i)), 'init pos', initLoc)
    
        # reset
        world.setFeature(pos, initLoc)
        triageAgent.setHorizon(i)
    
        for t in range(i):
            print(triageAgent.getActions())
            world.step()
            print('>>> Took Action', world.getValue(actionKey(triageAgent.name)), triageAgent.reward())