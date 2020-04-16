# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:27:36 2020

@author: mostafh
"""
from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, andRow, stateKey, rewardKey, actionKey, makeFuture,\
                        setToFeatureMatrix, setFalseMatrix, noChangeMatrix, addFeatureMatrix
from psychsim.world import WORLD
from victims_fewacts import Victims

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
        if initLoc:
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

    def __makeMoveActions(human):
        """
        N/E/S/W actions
        Legality: if current location has a neighbor in the given direction
        Dynamics: 1) change human's location; 2) set the seen flag for new location to True
        3) Set the observable victim variables to the first victim at the new location, if any
        4) Reset the crosshair/approached vars to none
        """
        Locations.moveActions[human.name] = []
        locKey = stateKey(human.name, 'loc')

        for direction in range(4):            
            # Legal if current location has a neighbor in the given direction
            locsWithNbrs = set(Locations.Nbrs[direction].keys())
            legalityTree = makeTree({'if':equalRow(locKey, locsWithNbrs),
                                    True: True,
                                    False: False})
            action = human.addAction({'verb': 'move', 'object':Directions.Names[direction]},legalityTree)
            Locations.moveActions[human.name].append(action)

            # Unset the crosshair and FOV and approach variables
            for varname in [Victims.STR_APPROACH_VAR, Victims.STR_CROSSHAIR_VAR, Victims.STR_FOV_VAR]:
                vtKey = stateKey(human.name, varname)
                tree = makeTree(setToConstantMatrix(vtKey, 'none'))
                Locations.world.setDynamics(vtKey,action,tree)

            # Dynamics of this move action: change the agent's location to 'this' location
            lstlocsWithNbrs = list(locsWithNbrs)
            tree = {'if':equalRow(locKey, lstlocsWithNbrs)}
            for il, loc in enumerate(lstlocsWithNbrs):
                tree[il] = setToConstantMatrix(locKey, Locations.Nbrs[direction][loc])
            Locations.world.setDynamics(locKey,action,makeTree(tree))

            # A move sets the seen flag of the location we moved to
            for dest in Locations.AllLocations: 
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
