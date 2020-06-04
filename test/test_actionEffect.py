# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World, WORLD
from psychsim.pwl import stateKey, actionKey
from new_locations_fewacts import Locations, Directions
from victims_fewacts import Victims
from helpers import runMMBelUpdate, setBeliefs, setBeliefsNoVics

def test_actionEffects():
	# MDP or POMDP
	Victims.FULL_OBS = True

	world = World()

	triageAgent = world.addAgent('TriageAg1')
	agent = world.addAgent('ATOMIC')


	VICTIMS_LOCS = ['E1']
	VICTIM_TYPES = ['Orange']
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

	assert world.getState(triageAgent.name,'loc',unique=True) == 'E1'
	####### Test if action effects are back
	Locations.move(triageAgent, Directions.W)
	assert world.getState(triageAgent.name,'loc',unique=True) == 'BH1'

if __name__ == '__main__':
	test_actionEffects()