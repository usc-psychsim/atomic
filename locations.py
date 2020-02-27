# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:27:36 2020

@author: mostafh
"""
from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, andRow, stateKey, rewardKey, actionKey
from psychsim.world import WORLD

import numpy as np

class Locations:
    numLocations = 0
    moveActions = {}
    world = None
    nbrs = []
    
    def makeMap(n, pairsList):
        """
        Ground truth of initial map
        """
        Locations.numLocations = n    
        for i in range(Locations.numLocations):
            Locations.nbrs.append([])
            
        for (i,j) in pairsList:        
            Locations.nbrs[i].append(j)
            Locations.nbrs[j].append(i)
            
        for i in range(Locations.numLocations):
            for j in range(Locations.numLocations):
                key = Locations.world.defineState(WORLD, 'adj_'+str(i) + str(j), bool)                
                Locations.world.setFeature(key, ((i,j) in pairsList) or ((j,i) in pairsList))
                
    def makePlayerLocation(human, initLoc):
        Locations.world.defineState(human,'loc',int,lo=0,hi=Locations.numLocations-1, description='Location')
        Locations.world.setState(human.name, 'loc', initLoc)

    def makeLegalTree(destNbrs, key):
        if destNbrs == []:
            return False
        new = {'if': equalRow(key, destNbrs[0]), 
               True:True, 
               False:Locations.makeLegalTree(destNbrs[1:], key)}
        return new

    def makeMoveActions(human):
        Locations.moveActions[human.name] = []
        
        for dest in range(Locations.numLocations):         
            legalityTree = makeTree(Locations.makeLegalTree(Locations.nbrs[dest], stateKey(human.name, 'loc')))
            action = human.addAction({'verb': 'move', 'object':str(dest)}, legalityTree)
            Locations.moveActions[human.name].append(action)
            
            # Dynamics of this move action: change the agent's location to 'this' location
            key = stateKey(human.name,'loc')
            tree = makeTree(setToConstantMatrix(key, dest))
            Locations.world.setDynamics(key,action,tree)

    def move(human, dest):
        Locations.world.step(Locations.moveActions[human.name][dest])
