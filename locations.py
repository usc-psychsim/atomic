# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:27:36 2020

@author: mostafh
"""
from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, andRow, stateKey, rewardKey, actionKey
from psychsim.world import WORLD


class Locations:
    ADJ_MAT = [[1,1,0,0], [1,1,1,1], [0,1,1,0], [0, 1,0,1]]
    numLocations = len(ADJ_MAT)
    moveActions = {}
    world = None

    def makeMap():    
        ## Ground truth of initial map
        for i in range(Locations.numLocations):
            for j in range(Locations.numLocations):
                key = Locations.world.defineState(WORLD, 'adj_'+str(i) + str(j), bool)
                Locations.world.setFeature(key, Locations.ADJ_MAT[i][j])
                
    def makePlayerLocation(human, initLoc):
        Locations.world.defineState(human,'loc',int,lo=0,hi=Locations.numLocations-1, description='Location')
        Locations.world.setState(human.name, 'loc', initLoc)


    def makeMoveActions(human):
        Locations.moveActions[human.name] = []
        
        for dest in range(Locations.numLocations):
            
            # legal if adjacency flag of agent's location and destination is True
            legalityTree = makeTree({'if': equalRow(stateKey(WORLD, 'adj_' + \
                                                                     str(Locations.world.getState(human.name, 'loc').max()) + \
                                                                     str(dest)), 
                                                    True),        
                                True: True,
                                False: False})
            action = human.addAction({'verb': 'move', 'object':str(dest)}, legalityTree)
            Locations.moveActions[human.name].append(action)
            
            # Dynamics of this move action: change the agent's location to 'this' location
            key = stateKey(human.name,'loc')
            tree = makeTree(setToConstantMatrix(key, dest))
            Locations.world.setDynamics(key,action,tree)

    def move(human, dest):
        Locations.world.step(Locations.moveActions[human.name][dest])