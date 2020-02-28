# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:24:46 2020

@author: mostafh
"""
from locations import Locations
from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, stateKey, rewardKey, actionKey
from psychsim.world import WORLD

class Fires:
    FIRE_PENALTY = -100
    fireLocations = []
    fireActions = {}
    world = None
    
    def makeFires(locs):
        """
        Assume locations set at time 0 and don't change except if extinguished
        """
        Fires.fireLocations = locs
        for i in range(Locations.numLocations):
            key = Fires.world.defineState(WORLD, 'fire_'+str(i), bool)
            if i in locs:
                Fires.world.setFeature(key, True)
            else:
                Fires.world.setFeature(key, False)
    

    def makeExtinguishActions(human):
        """
        Create an extinguish action per location. 
        Legal if 1) location's fire flag is on; and 2) agent adjacent to location
        Action effects: reset fire flag
        """
        Fires.fireActions[human.name] = {}   
 
        for fireLoc in Fires.fireLocations:
            action = human.addAction({'verb': 'extinguish', 'object':str(fireLoc)})
            
            legalityTree = makeTree({'if': equalRow(stateKey(WORLD, 'fire_'+str(fireLoc)), True),
                                True:  Locations.makeIsNeighborTree(fireLoc, human),
                                False: False})
                                
            human.setLegal(action,legalityTree)
            Fires.fireActions[human.name][fireLoc] = action
            
            key = stateKey(WORLD, 'fire_'+str(fireLoc))
            tree = makeTree(setToConstantMatrix(key, False))
            Fires.world.setDynamics(key,action,tree)

    def makeFirePenalty(human):
        """
        Fire penalty: For every fire location, add a reward tree
        """
        for fire in Fires.fireLocations:
            costTree = makeTree({'if': equalRow(stateKey(human.name, 'loc'),fire),
                                True: {'if': equalRow(stateKey(WORLD, 'fire_'+str(fire)), True),
                                    True: setToConstantMatrix(rewardKey(human.name), Fires.FIRE_PENALTY) ,
                                    False: setToConstantMatrix(rewardKey(human.name),0)},
                                False: setToConstantMatrix(rewardKey(human.name),0)})        
            human.setReward(costTree, 1)

    def extinguish(human, fireLoc):
        Fires.world.step(Fires.fireActions[human.name][fireLoc])