# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey, actionKey, modelKey, Distribution
from new_locations_fewacts import Locations, Directions
from victims_fewacts import Victims

def test_belief_reset():
	# MDP or POMDP
	Victims.FULL_OBS = True

	world = World()

	triageAgent = world.addAgent('TriageAg1')
	agent = world.addAgent('ATOMIC')


	VICTIMS_LOCS = ['E1']
	VICTIM_TYPES = ['Yellow']
	Victims.world = world
	Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], ['BH1','E1'])
	Victims.makePreTriageActions(triageAgent)
	Victims.makeTriageAction(triageAgent)

	Victims.P_VIC_FOV = (1.0 - Victims.P_EMPTY_FOV) / len(Victims.victimAgents)

	################# Locations and Move actions
	Locations.EXPLORE_BONUS = 0
	Locations.world = world
	Locations.makeMapDict({'BH1':{Directions.E:'E1'}, 'E1':{Directions.W:'BH1'}})
	Locations.makePlayerLocation(triageAgent, "E1")

	## These must come before setting triager's beliefs
	world.setOrder([{triageAgent.name}])

	## Set players horizons
	triageAgent.setAttribute('horizon',4)

	################ Belief manipulation
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

	# Agent observes everything except triageAgent's true model
	agent.omega = {key for key in world.state.keys() if key not in \
	               {modelKey(triageAgent.name),modelKey(agent.name)}} #rewardKey(triageAgent.name),
	################ 
	################ 

	assert len(agent.getBelief()) == 1

	####### Somehow there seems to be 2 ATOMIC agent models!
	Locations.move(triageAgent, Directions.W)

	assert len(agent.getBelief()) == 2 # Correct so long as FOV outcome is stochastic


if __name__ == '__main__':
	test_belief_reset()