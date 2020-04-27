# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:27:36 2020

@author: mostafh
"""
from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, andRow, stateKey, rewardKey, actionKey, makeFuture,\
                        setToFeatureMatrix, setFalseMatrix, noChangeMatrix, addFeatureMatrix
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
    """
    Nbrs: a list. The element corresponding to each direction is a map of each location that has a
    neighbor in this direction to that neighbor
    """
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

    def makeMapDict(pairsDict):
        """
        Each key in parisDict is a room, and the values are another dictionary with keys
        being Directions.directions, and the values are rooms in that direction.
        """
        for i in range(4):
            Locations.Nbrs.append({})
        for room in pairsDict:
            for d in pairsDict[room]:
                n = pairsDict[room][d]
                Locations.Nbrs[d][room] = n
                Locations.AllLocations.add(n)

    def makePlayerLocation(human, initLoc=None):
        Locations.world.defineState(human,'loc',list, list(Locations.AllLocations))
        if initLoc != None:
            Locations.world.setState(human.name, 'loc', initLoc)

        ## Add a seen flag per location
        for i in Locations.AllLocations:
            Locations.world.defineState(human,'seenloc_' + str(i),bool, description='Location seen or not')
            Locations.world.setState(human.name, 'seenloc_' + str(i), False)
        if initLoc:
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
        res = makeTree(Locations.__makeHasNeighborDict(locKey, direction, list(Locations.Nbrs[direction].keys())))
        return res

    def __makeGetNeighborDict(locKey, direction, locsWithNbrs):
        if locsWithNbrs == []:
            res = setToConstantMatrix(locKey, -1)
            return res
        new = {'if': equalRow(locKey, locsWithNbrs[0]),
               True:setToConstantMatrix(locKey, Locations.Nbrs[direction][locsWithNbrs[0]]),
               False:Locations.__makeGetNeighborDict(locKey, direction, locsWithNbrs[1:])}
        return new

    def __makeGetNeighborTree(locKey, direction):
        res = makeTree(Locations.__makeGetNeighborDict(locKey, direction, list(Locations.Nbrs[direction].keys())))
        return res


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
            action = human.addAction({'verb': 'move', 'object':Directions.Names[direction]},legalityTree)
            Locations.moveActions[human.name].append(action)

            # Unset the crosshair flag
            vtKey = stateKey(human.name,'victim in crosshair')
            tree = makeTree(setFalseMatrix(vtKey))
            Locations.world.setDynamics(vtKey,action,tree)

            # Unset the within range flag
            wrKey = stateKey(human.name,'victim within range')
            tree = makeTree(setFalseMatrix(wrKey))
            Locations.world.setDynamics(wrKey,action,tree)

            # Dynamics of this move action: change the agent's location to 'this' location
            tree = Locations.__makeGetNeighborTree(locKey, direction)
            Locations.world.setDynamics(locKey,action,tree)

            # A move in direction D can set the seen flag of any location to the D of another
            # I.e., any location with a neighbor in direction d+2
            for dest in Locations.AllLocations: # Locations.Nbrs[(direction + 2) % 4].keys():
                destKey = stateKey(human.name,'seenloc_'+str(dest))
                tree = makeTree({'if': equalRow(makeFuture(locKey), dest),
                                 True: setToConstantMatrix(destKey, True),
                                 False: noChangeMatrix(destKey)})
                Locations.world.setDynamics(destKey,action,tree)


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
                                    True: addFeatureMatrix(rewardKey(human.name), Locations.EXPLORE_BONUS) ,
                                    False: noChangeMatrix(rewardKey(human.name))},
                                False: noChangeMatrix(rewardKey(human.name))})
            human.setReward(bonus, 1)

    def move(human, direction):
        Locations.world.step(Locations.moveActions[human.name][direction])

    def getDirection(src, dest):
        for d in range(4):
            if (src in Locations.Nbrs[d].keys()) and (Locations.Nbrs[d][src] == dest):
                return d
        print('Source cannot reach dest', src, dest)
        return -1

    def moveToLocation(human, src, dest):
        Locations.world.step(Locations.getMoveAction(human, src, dest))

    def getMoveAction(human, src, dest):
        if type(human) == str:
            name = human
        else:
            name = human.name
        return Locations.moveActions[name][Locations.getDirection(src, dest)]
