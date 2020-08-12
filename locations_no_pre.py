# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 11:27:36 2020

@author: mostafh
"""
from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, andRow, stateKey, rewardKey, actionKey, makeFuture,\
                        setToFeatureMatrix, setFalseMatrix, noChangeMatrix, addFeatureMatrix, incrementMatrix
from psychsim.world import WORLD

class Directions:
    """
    Dicretions class

    """
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

    def makePlayerLocation(human, victimsObj, initLoc=None):
        Locations.world.defineState(human,'loc',list, list(Locations.AllLocations))
        if initLoc != None:
            Locations.world.setState(human.name, 'loc', initLoc)

        ## Add a seen flag per location
        for i in Locations.AllLocations:
            Locations.world.defineState(human,'locvisits_' + str(i),int, description='Location seen or not')
            Locations.world.setState(human.name, 'locvisits_' + str(i), 0)
        if initLoc:
            Locations.world.setState(human.name, 'locvisits_' + str(initLoc), 1)

        ## Make move actions
        Locations.__makeMoveActions(human, victimsObj)
        Locations.__makeExplorationBonus(human)

    def __makeMoveActions(human, victimsObj):
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
#            print('Dir', direction, 'legal in', locsWithNbrs)
            legalityTree = makeTree({'if':equalRow(locKey, locsWithNbrs),
                                    True: True,
                                    False: False})
            action = human.addAction({'verb': 'move', 'object':Directions.Names[direction]},legalityTree)
            Locations.moveActions[human.name].append(action)

            # Dynamics of this move action: change the agent's location to 'this' location
            lstlocsWithNbrs = list(locsWithNbrs)
            tree = {'if':equalRow(locKey, lstlocsWithNbrs)}
            for il, loc in enumerate(lstlocsWithNbrs):
                tree[il] = setToConstantMatrix(locKey, Locations.Nbrs[direction][loc])
            Locations.world.setDynamics(locKey,action,makeTree(tree))

            # A move sets the seen flag of the location we moved to
            for dest in Locations.AllLocations:
                destKey = stateKey(human.name,'locvisits_'+str(dest))
                tree = makeTree({'if': equalRow(makeFuture(locKey), dest),
                                 True: incrementMatrix(destKey, 1),
                                 False: noChangeMatrix(destKey)})
                Locations.world.setDynamics(destKey,action,tree)
                
            # A move resets the flags of whether I just saved someone
            victimsObj.resetJustSavedFlags(human, action)

            fovKey  = stateKey(human.name, 'vicInFOV')
            ## If we're using search actions, a move resets the FOV
            tree = makeTree(setToConstantMatrix(fovKey, 'none'))
            Locations.world.setDynamics(fovKey,action,tree)

    def __makeExplorationBonus(human):
        if Locations.EXPLORE_BONUS <= 0:
            return
        for dest in range(Locations.numLocations):
            bonus = makeTree({'if': equalRow(stateKey(human.name, 'loc'), dest),
                                True: {'if': equalRow(stateKey(human.name, 'locvisits_'+str(dest)), 0),
                                    True: addFeatureMatrix(rewardKey(human.name), Locations.EXPLORE_BONUS) ,
                                    False: noChangeMatrix(rewardKey(human.name))},
                                False: noChangeMatrix(rewardKey(human.name))})
            human.setReward(bonus, 1)

    def move(human, direction):
        Locations.world.step(Locations.moveActions[human.name][direction])

    def getDirection(src, dest, isSecond=False):
        for d in range(4):
            if (src in Locations.Nbrs[d].keys()) and (Locations.Nbrs[d][src] == dest):
                return [d]
        if isSecond:
            return [-1]

        # If src and dest are 1 step removed, find a common nbr, if any and return
        # 2 move actions. Do NOT recurse indefinitely.
        for mid in Locations.AllLocations:
            d1 = Locations.getDirection(src, mid, True)
            if d1[0] >= 0:
                d2 = Locations.getDirection(mid, dest, True)
                if d2[0] >= 0:
                    return [d1[0], d2[0]]

        return [-1]

    def moveToLocation(human, src, dest):
        Locations.world.step(Locations.getMoveAction(human, src, dest))

    def getMoveAction(human, src, dest):
        if type(human) == str:
            name = human
        else:
            name = human.name
        ds = Locations.getDirection(src, dest)
        if ds[0] == -1:
            return []
        return [Locations.moveActions[name][d] for d in ds]
