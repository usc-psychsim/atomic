#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun 20 15:39:15 2020

@author: mostafh
"""
from psychsim.world import World, WORLD
from new_locations_fewacts import Locations
from victims_clr import Victims
from psychsim.pwl import modelKey


def makeWorld(playerName, initLoc, SandRLocs, SandRVics):
    world = World()
    k = world.defineState(WORLD, 'seconds', int)
    world.setFeature(k, 0)
    
    triageAgent = world.addAgent(playerName)
    agent = world.addAgent('ATOMIC')
    
    
    ################# Victims and triage actions
    Victims.world = world
    VICTIMS_LOCS = []
    VICTIM_TYPES = []
    for loc, vics in SandRVics.items():
        for vic in vics:
            if loc.startswith('2'):
                loc = 'R' + loc
            VICTIMS_LOCS.append(loc)
            VICTIM_TYPES.append(vic)
    Victims.world = world
    Victims.COLOR_PRIOR_P = {'Green':0.3, 'Gold':0.4}
    # if the following prob's add up to 1, FOV will never be empty after a search
    Victims.COLOR_FOV_P = {'Green':0.2, 'Gold':0.2, 'Red':0.2, 'White':0.4}
    Victims.setupTriager(VICTIMS_LOCS, VICTIM_TYPES, triageAgent, list(SandRLocs.keys()))
    
    ################# Locations and Move actions
    Locations.EXPLORE_BONUS = 0
    Locations.world = world
    Locations.makeMapDict(SandRLocs)
    Locations.makePlayerLocation(triageAgent,Victims,  initLoc)
    Locations.AllLocations = list(Locations.AllLocations)
    print('Made move actions')
    
    ## These must come before setting triager's beliefs
    world.setOrder([{triageAgent.name}])
    
    if not Victims.FULL_OBS:
        print('Start to make observable variables and priors')
        Victims.createObsVars4Victims(triageAgent, Locations.AllLocations)
        print('Made observable variables and priors')
        Victims.makeSearchAction(triageAgent, Locations.AllLocations)
        print('Made search action')

    triageAgent.resetBelief()
    triageAgent.omega = [key for key in world.state.keys() \
                         if not ((key in {modelKey(agent.name)}) or key.startswith('victim')\
                                 or (key.find('unobs')>-1))]
    

    return world, triageAgent, agent