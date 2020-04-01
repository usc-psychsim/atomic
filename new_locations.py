# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:27:36 2020

@author: mostafh
"""
from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, andRow, stateKey, rewardKey, actionKey, makeFuture,\
                        setToFeatureMatrix, setFalseMatrix
from psychsim.world import WORLD
from victims import Victims

class Directions:
    N = 0
    E = 1
    S = 2
    W = 3
    Names = ['N', 'E', 'S', 'W']

class Locations:
    """ Exploration bonus"""
    EXPLORE_BONUS = 0
    moveActions = {}
    world = None
    Nbrs = []
    AllLocations = set()

    def makeMap(pairsList):
        """
        Each tuple in the list is of the form (z1, dir, z2) meaning z1 is to the <dir> of z2
        """
        for i in range(4):
            Locations.Nbrs.append({})
        for (z1, d, z2) in pairsList:
            Locations.Nbrs[d][z1] = z2
            Locations.Nbrs[(d + 2) % 4][z2] = z1
            Locations.AllLocations.add(z1)
            Locations.AllLocations.add(z2)

    def makePlayerLocation(human, initLoc):
        Locations.world.defineState(human,'loc',int, description='Location')
        Locations.world.setState(human.name, 'loc', initLoc)

        ## Add a seen flag per location
        for i in Locations.AllLocations:
            Locations.world.defineState(human,'seenloc_' + str(i),bool, description='Location seen or not')
            Locations.world.setState(human.name, 'seenloc_' + str(i), False)
        Locations.world.setState(human.name, 'seenloc_' + str(initLoc), True)

        ## Make move actions
        Locations.__makeMoveActions(human)
        Locations.__makeExplorationBonus(human)

    def __makeHasNeighborDict(locKey, direction, locsWithNbrs):
        if locsWithNbrs == []:
            return False
        new = {'if': equalRow(locKey, locsWithNbrs[0]),
               True:True,
               False:Locations.__makeHasNeighborDict(locKey, direction, locsWithNbrs[1:])}
        return new

    def __makeHasNeighborTree(locKey, direction):
        return makeTree(Locations.__makeHasNeighborDict(locKey, direction, list(Locations.Nbrs[direction].keys())))

    def __makeGetNeighborDict(locKey, direction, locsWithNbrs):
        if locsWithNbrs == []:
            return setToConstantMatrix(locKey, -1)
        new = {'if': equalRow(locKey, locsWithNbrs[0]),
               True:setToConstantMatrix(locKey, Locations.Nbrs[direction][locsWithNbrs[0]]),
               False:Locations.__makeGetNeighborDict(locKey, direction, locsWithNbrs[1:])}
        return new

    def __makeGetNeighborTree(locKey, direction):
        return makeTree(Locations.__makeGetNeighborDict(locKey, direction, list(Locations.Nbrs[direction].keys())))


    def __makeMoveActions(human):
        """
        N/E/S/W actions
        Legality: if current location has a neighbor in the given direction
        Dynamics: 1) change human's location; 2) set the seen flag for new location to True
        3) Set the observable victim variables to the first victim at the new location, if any
        """
        Locations.moveActions[human.name] = []
        locKey = stateKey(human.name, 'loc')

        for direction in range(4):
            legalityTree = Locations.__makeHasNeighborTree(locKey, direction)
            action = human.addAction({'verb': 'move', 'object':Directions.Names[direction]}, legalityTree)
            Locations.moveActions[human.name].append(action)

            # Dynamics of this move action: change the agent's location to 'this' location
            tree = Locations.__makeGetNeighborTree(locKey, direction)
            Locations.world.setDynamics(locKey,action,tree)

            # A move in direction D can set the seen flag of any location to the D of another
            # I.e., any location with a neighbor in direction d+2
            for dest in Locations.Nbrs[(direction + 2) % 4].keys():
                key = stateKey(human.name,'seenloc_'+str(dest))
                tree = makeTree({'if': equalRow(makeFuture(locKey), dest),
                                 True: setToConstantMatrix(stateKey(human.name,'seenloc_'+str(dest)), True),
                                 False: setToFeatureMatrix(stateKey(human.name,'seenloc_'+str(dest)), stateKey(human.name,'seenloc_'+str(dest)))})
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
                                    True: setToConstantMatrix(rewardKey(human.name), Locations.EXPLORE) ,
                                    False: setToConstantMatrix(rewardKey(human.name),0)},
                                False: setToConstantMatrix(rewardKey(human.name),0)})
            human.setReward(bonus, 1)

    def move(human, direction):
        Locations.world.step(Locations.moveActions[human.name][direction])
