# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 14:35:40 2020

@author: mostafh
"""
from psychsim.world import World
from psychsim.pwl import stateKey, actionKey, modelKey, Distribution
from new_locations_fewacts import Locations, Directions
from victims_clr import Victims

if True:
    # MDP or POMDP
    Victims.FULL_OBS = False

    world = World()
    triageAgent = world.addAgent('TriageAg1')
    agent = world.addAgent('ATOMIC')

    VICTIMS_LOCS = ['E1', 'BH2', 'BH2']
    VICTIM_TYPES = ['Green','Green','Yellow']
    Victims.COLOR_PRIOR_P = {'Green':0.3, 'Yellow':0.4}
    Victims.world = world
    Victims.makeVictims(VICTIMS_LOCS, VICTIM_TYPES, [triageAgent.name], ['BH1','E1','BH2'])
    Victims.makePreTriageActions(triageAgent)
    Victims.makeTriageAction(triageAgent)

    ################# Locations and Move actions
    Locations.EXPLORE_BONUS = 0
    Locations.world = world
    Locations.makeMapDict({'BH1':{Directions.E:'E1'},
                           'E1' :{Directions.W:'BH1',Directions.E:'BH2'},
                           'BH2':{Directions.W:'E1'}})
    
    Locations.makePlayerLocation(triageAgent, "BH2")
    Locations.AllLocations = list(Locations.AllLocations)
    
	## These must come before setting triager's beliefs
    world.setOrder([{triageAgent.name}])

    Victims.beliefAboutVictims(triageAgent, ['BH1','E1','BH2'])
    fovTree2 = Victims.makeSearchAction(triageAgent, Locations.AllLocations)
    

    print('before anyting')
    world.printState()
    
    world.step(Victims.searchActs[triageAgent.name])    
    print('=== after searching once')
    world.printState()
    
    world.setFeature(stateKey('victim1', 'color'), 'White')
    world.step(Victims.searchActs[triageAgent.name])    
    print('=== after the victim is rescued')
    world.printState()
    
    
    world.step(Victims.searchActs[triageAgent.name])    
    print('=== again after the victim is rescued')
    world.printState()
    

