# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:27:36 2020

@author: mostafh
"""
from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, andRow, stateKey, rewardKey, actionKey, makeFuture, setFalseMatrix
from psychsim.world import WORLD
from victims import Victims

class Locations:
    """ Exploration bonus"""
    EXPLORE_BONUS = 1
    numLocations = 0
    moveActions = {}
    world = None
    nbrs = []

    def makeMap(pairsList):
        """
        Ground truth of initial map
        """
        Locations.numLocations = max(max(pairsList)) + 1
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
        
        ## Add a seen flag per location
        for i in range(Locations.numLocations):
            Locations.world.defineState(human,'seenloc_' + str(i),bool, description='Location seen or not')
            Locations.world.setState(human.name, 'seenloc_' + str(i), False)
        Locations.world.setState(human.name, 'seenloc_' + str(initLoc), True)
        
        ## Make move actions
        Locations.__makeMoveActions(human)
        Locations.__makeExplorationBonus(human)

    def __makeIsNeighborDict(destNbrs, key):
        if destNbrs == []:
            return False
        new = {'if': equalRow(key, destNbrs[0]),
               True:True,
               False:Locations.__makeIsNeighborDict(destNbrs[1:], key)}
        return new
    
    def makeIsNeighborTree(loc, human):
        return makeTree(Locations.__makeIsNeighborDict(Locations.nbrs[loc], stateKey(human.name, 'loc')))

    def __makeMoveActions(human):
        """
        An action per destination
        Legality: if neigbor to current location
        Dynamics: 1) change human's location; 2) set the seen flag for new location to True
        3) Set the observable victim variables to the first victim at the new location, if any
        """
        Locations.moveActions[human.name] = []
        
        for dest in range(Locations.numLocations):
            legalityTree = Locations.makeIsNeighborTree(dest, human)
            action = human.addAction({'verb': 'move', 'object':str(dest)}, legalityTree)
            Locations.moveActions[human.name].append(action)
            
            # Dynamics of this move action: change the agent's location to 'this' location
            locKey = stateKey(human.name,'loc')
            tree = makeTree(setToConstantMatrix(locKey, dest))
            Locations.world.setDynamics(locKey,action,tree)
            
            # Set the seenloc flag
            key = stateKey(human.name,'seenloc_'+str(dest))
            tree = makeTree(setToConstantMatrix(key, True))
            Locations.world.setDynamics(key,action,tree)

            # Unset the vic_targeted flag
            vtKey = stateKey(human.name,'vic_targeted')
            tree = makeTree(setFalseMatrix(vtKey))
            Locations.world.setDynamics(vtKey,action,tree)


            if not Victims.FULL_OBS:
                # Set observed variables to victim's features
                # 1. Observe status of victim in destination
                key = stateKey(human.name, 'obs_victim_status')
                tree1 = Victims.makeNearVTree(makeFuture(locKey), key, 'status', 'none')
                Locations.world.setDynamics(key,action,tree1)
                
                # 2. Observe danger of victim in destination
                key = stateKey(human.name, 'obs_victim_danger')
                tree2 = Victims.makeNearVTree(makeFuture(locKey), key, 'danger', 0)
                Locations.world.setDynamics(key,action,tree2)
                
                # 3. Observe reward of victim in destination
                key = stateKey(human.name, 'obs_victim_reward')
                tree3 = Victims.makeNearVTree(makeFuture(locKey), key, 'reward', 0)
                Locations.world.setDynamics(key,action,tree3)
            
    def __makeExplorationBonus(human):    
        if Locations.EXPLORE_BONUS <= 0:
            return
        for dest in range(Locations.numLocations):
            bonus = makeTree({'if': equalRow(stateKey(human.name, 'loc'), dest),
                                True: {'if': equalRow(stateKey(human.name, 'seenloc_'+str(dest)), False),
                                    True: setToConstantMatrix(rewardKey(human.name), Locations.EXPLORE_BONUS) ,
                                    False: setToConstantMatrix(rewardKey(human.name),0)},
                                False: setToConstantMatrix(rewardKey(human.name),0)})
            human.setReward(bonus, 1)

    def move(human, dest):
        Locations.world.step(Locations.moveActions[human.name][dest])
