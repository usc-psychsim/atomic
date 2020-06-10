# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey, modelKey, Distribution
from new_locations_fewacts import Locations, Directions
from victims_clr import Victims

if True:
    # MDP or POMDP
    Victims.FULL_OBS = False

    world = World()
    triageAgent = world.addAgent('TriageAg1')
    agent = world.addAgent('ATOMIC')

    VICTIMS_LOCS = ['E1']
    VICTIM_TYPES = ['Green']
    Victims.COLOR_PRIOR_P = {'Green':0.3, 'Yellow':0.4}
    Victims.COLOR_FOV_P = {'Green':0.2, 'Yellow':0.2, 'Red':0.2, 'White':0.4}
    Victims.world = world
    Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], ['E1'])
    Victims.makePreTriageActions(triageAgent)
    Victims.makeTriageAction(triageAgent)

    ################# Locations and Move actions
    Locations.EXPLORE_BONUS = 0
    Locations.world = world
    Locations.makeMapDict({'BH1':{Directions.E:'E1'},
                           'E1' :{Directions.W:'BH1'}})
    
    Locations.makePlayerLocation(triageAgent, "E1")
    Locations.AllLocations = list(Locations.AllLocations)
    
	## These must come before setting triager's beliefs
    world.setOrder([{triageAgent.name}])

    Victims.beliefAboutVictims(triageAgent, ['E1'])
    dynTrees = Victims.makeSearchAction(triageAgent, ['E1'])
    

    print('before anyting')
    world.printState(beliefs=False)
    
    world.step(Victims.searchActs[triageAgent.name], select=True)
    print('=== after searching once')
    world.printState(beliefs=False)
    
    world.setFeature(stateKey('victim0', 'color'), 'White')
    world.step(Victims.searchActs[triageAgent.name])    
    print('=== after the victim is rescued')
    world.printState(beliefs=False)
        
    world.step(Victims.searchActs[triageAgent.name], select=True)
    print('=== again after the victim is rescued')
    world.printState(beliefs=False)
    
#
