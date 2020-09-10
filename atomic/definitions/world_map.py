from psychsim.agent import Agent
from psychsim.pwl import stateKey, makeTree, equalRow, setToConstantMatrix, makeFuture, incrementMatrix, noChangeMatrix, \
    addFeatureMatrix, rewardKey
from atomic.definitions import Directions
from atomic.definitions.world import SearchAndRescueWorld


class WorldMap(object):
    """
    Represents a search and rescue world map with cardinal direction transitions (grid-world representation).
    """

    def __init__(self, world, loc_neighbors):
        """
        Creates a new map with the given locations.
        :param SearchAndRescueWorld world: the PsychSim world.
        :param dict[str, dict[int, str]] loc_neighbors: a dictionary where each key is a room, and the values are
        another dictionary with keys being `Directions.directions`, and the values are rooms in that direction.
        """
        self.world = world
        self.neighbors = []
        self.all_locations = []
        self.moveActions = {}
        self.makeMapDict(loc_neighbors)

    def makeMapDict(self, loc_neighbors):
        self.clear()
        locations = set()
        for _ in Directions:
            self.neighbors.append({})
        for room in loc_neighbors:
            for d in loc_neighbors[room]:
                n = loc_neighbors[room][d]
                self.neighbors[d][room] = n
                locations.add(n)
        self.all_locations = list(locations)

    def makePlayerLocation(self, agent, initLoc=None):
        self.world.defineState(agent, 'loc', list, list(self.all_locations))
        if initLoc is not None:
            self.world.setState(agent.name, 'loc', initLoc)

        # Add a seen flag per location
        for i in self.all_locations:
            self.world.defineState(agent, 'locvisits_' + str(i), int, description='Location seen or not')
            self.world.setState(agent.name, 'locvisits_' + str(i), 0)
        if initLoc:
            self.world.setState(agent.name, 'locvisits_' + str(initLoc), 1)

        # Make move actions
        self._makeMoveActions(agent)

    def _makeMoveActions(self, agent):
        """
        N/E/S/W actions
        Legality: if current location has a neighbor in the given direction
        Dynamics: 1) change human's location; 2) set the seen flag for new location to True
        3) Set the observable victim variables to the first victim at the new location, if any
        4) Reset the crosshair/approached vars to none
        """
        self.moveActions[agent.name] = []
        locKey = stateKey(agent.name, 'loc')

        for direction in Directions:
            # Legal if current location has a neighbor in the given direction
            locsWithNbrs = set(self.neighbors[direction.value].keys())
            legalityTree = makeTree({'if': equalRow(locKey, locsWithNbrs),
                                     True: True,
                                     False: False})
            action = agent.addAction({'verb': 'move', 'object': direction.name}, legalityTree)
            self.moveActions[agent.name].append(action)

            # Dynamics of this move action: change the agent's location to 'this' location
            lstlocsWithNbrs = list(locsWithNbrs)
            tree = {'if': equalRow(locKey, lstlocsWithNbrs)}
            for il, loc in enumerate(lstlocsWithNbrs):
                tree[il] = setToConstantMatrix(locKey, self.neighbors[direction.value][loc])
            self.world.setDynamics(locKey, action, makeTree(tree))

            # A move sets the seen flag of the location we moved to
            for dest in self.all_locations:
                destKey = stateKey(agent.name, 'locvisits_' + str(dest))
                tree = makeTree({'if': equalRow(makeFuture(locKey), dest),
                                 True: incrementMatrix(destKey, 1),
                                 False: noChangeMatrix(destKey)})
                self.world.setDynamics(destKey, action, tree)

    def makeExplorationBonus(self, agent, explore_bonus):
        """
        Adds an exploration reward (bonus) to the agent.
        :param Agent agent: the agent to which we want to set the exploration reward.
        :param float explore_bonus: the exploration bonus for moving to unseen locations.
        :return:
        """
        if explore_bonus <= 0:
            return
        for dest in range(len(self.all_locations)):
            bonus = makeTree({'if': equalRow(stateKey(agent.name, 'loc'), dest),
                              True: {'if': equalRow(stateKey(agent.name, 'locvisits_' + str(dest)), 0),
                                     True: addFeatureMatrix(rewardKey(agent.name), explore_bonus),
                                     False: noChangeMatrix(rewardKey(agent.name))},
                              False: noChangeMatrix(rewardKey(agent.name))})
            agent.setReward(bonus, 1)

    def move(self, agent, direction):
        self.world.step(self.moveActions[agent.name][direction])

    def getDirection(self, src, dest, isSecond=False):
        for d in Directions:
            if (src in self.neighbors[d.value].keys()) and (self.neighbors[d.value][src] == dest):
                return [d.value]
        if isSecond:
            return [-1]

        # If src and dest are 1 step removed, find a common nbr, if any and return
        # 2 move actions. Do NOT recurse indefinitely.
        for mid in self.all_locations:
            d1 = self.getDirection(src, mid, True)
            if d1[0] >= 0:
                d2 = self.getDirection(mid, dest, True)
                if d2[0] >= 0:
                    return [d1[0], d2[0]]

        return [-1]

    def moveToLocation(self, agent, src, dest):
        self.world.step(self.getMoveAction(agent, src, dest))

    def getMoveAction(self, agent, src, dest):
        if type(agent) == str:
            name = agent
        else:
            name = agent.name
        ds = self.getDirection(src, dest)
        if ds[0] == -1:
            return []
        return [self.moveActions[name][d] for d in ds]

    def clear(self):
        self.moveActions.clear()
        self.neighbors = []
        self.all_locations = []
