from psychsim.pwl import makeTree, setToConstantMatrix, equalRow, stateKey, rewardKey, Distribution, noChangeMatrix, \
    makeFuture, differenceRow, incrementMatrix, setFalseMatrix, dynamicsMatrix, thresholdRow, addFeatureMatrix
from psychsim.world import WORLD
from atomic.definitions.world_map import WorldMap
from atomic.definitions.world import SearchAndRescueWorld
from atomic.util.psychsim import anding

"""
Contains classes and methods for dealing with victims in the ASIST S&R problem.
"""

# overall constants
GREEN_STR = 'Green'
GOLD_STR = 'Gold'
WHITE_STR = 'White'
RED_STR = 'Red'
COLORS = [GREEN_STR, GOLD_STR, RED_STR, WHITE_STR]
STR_TRIAGE_ACT = 'actTriage'
FOV_FEATURE = 'vicInFOV'

# defaults
COLOR_REWARDS = {'Green': 10, 'Gold': 200}
COLOR_REQD_TIMES = {'Green': {5: 0.2, 8: 0.4}, 'Gold': {5: 0.2, 15: 0.4}}
COLOR_EXPIRY = {'Green': int(10 * 60), 'Gold': int(7 * 60)}
COLOR_PRIOR_P = {'Green': 0, 'Gold': 0}
COLOR_FOV_P = {'Green': 0, 'Gold': 0, 'Red': 0, 'White': 0}


class Victims(object):
    """ Methods for modeling victims within a PsychSim world. """

    def __init__(self, world, victims_color_locs, world_map,
                 color_names=None, color_expiry=None, color_reqd_times=None, color_prior_p=None, color_fov_p=None,
                 full_obs=False):
        """
        Creates a new representation over victims for the given world.
        :param SearchAndRescueWorld world: the PsychSim world.
        :param dict[str, list[str]] victims_color_locs: dictionary containing the location (key) and colors (value) of victims.
        :param WorldMap world_map: map with the location names that constitute legal values for the `loc` state of each victim.
        :param list[str] color_names: the names of the possible colors of victims.
        :param dict[str, int] color_expiry: a dictionary containing the expiration times (seconds) for each victim color.
        :param dict[str, dict[int, float]] color_reqd_times: a dictionary containing the distribution of triage times (seconds) for each victim color.
        :param dict[str, float] color_prior_p: a dictionary containing the prior probability for each victim color of the victim being present in a room
        :param dict[str, float] color_fov_p: a dictionary containing the prior probability for each victim color that a player's FOV has a victim of a given color after a search action.
        :param bool full_obs: whether the world is partially (`True`) or fully (`False`) observable, in the agents' perspective.
        """
        self.world = world
        self.world_map = world_map
        self.color_names = color_names if color_names is not None else COLORS
        self.color_expiry = color_expiry if color_expiry is not None else COLOR_EXPIRY
        self.color_reqd_times = color_reqd_times if color_reqd_times is not None else COLOR_REQD_TIMES
        self.color_prior_p = color_prior_p if color_prior_p is not None else COLOR_PRIOR_P
        self.color_fov_p = color_fov_p if color_fov_p is not None else COLOR_FOV_P
        self.full_obs = full_obs

        # A dict mapping a room to a dict mapping a color to the corresponding victim object
        self.victimsByLocAndColor = {}
        self.victimClrCounts = {}

        # A map from a player to her triage actions
        self.triageActs = {}

        # A map from a player to her search actions
        self.searchActs = {}

        # Create location-centric counters for victims of each of the 2 victims_colors
        self.victimClrCounts = {loc: {clr: 0 for clr in self.color_expiry} for loc in world_map.all_locations}
        for loc, vics in victims_color_locs.items():
            if loc.startswith('2'):
                loc = 'R' + loc
            for clr in vics:
                self.victimClrCounts[loc][clr] += 1

        # Create the psychsim version of these counters, including WHITE and RED
        for loc in world_map.all_locations:
            for clr in self.color_names:
                ctr = self.world.defineState(WORLD, 'ctr_' + loc + '_' + clr, int)
                self.world.setFeature(ctr, self.victimClrCounts[loc][clr] if clr in self.victimClrCounts[loc] else 0)

    def setupTriager(self, agent):
        # Create counter of victims I saved of each color
        for color in self.color_names:
            key = self.world.defineState(agent.name, 'numsaved_' + color, int)
            self.world.setFeature(key, 0)
            key = self.world.defineState(agent.name, 'saved_' + color, bool)
            self.world.setFeature(key, False)

        # create and initialize fov
        self.world.defineState(agent.name, FOV_FEATURE, list, ['none'] + self.color_names)
        agent.setState(FOV_FEATURE, 'none')

    def createTriageActions(self, agent):
        # Create a triage action per victim color
        self.triageActs[agent.name] = {}
        for color in self.color_expiry.keys():
            self._createTriageAction(agent, color)

    def _createTriageAction(self, agent, color):

        fov_key = stateKey(agent.name, FOV_FEATURE)
        loc_key = stateKey(agent.name, 'loc')

        legal = {'if': equalRow(fov_key, color), True: True, False: False}
        action = agent.addAction({'verb': 'triage_' + color}, makeTree(legal))

        if color == GREEN_STR:
            threshold = 7
        else:
            threshold = 14
        longEnough = differenceRow(makeFuture(self.world.time), self.world.time, threshold)

        for loc in self.world_map.all_locations:
            # successful triage conditions
            conds = [equalRow(fov_key, color),
                     equalRow(loc_key, loc),
                     longEnough]

            # location-specific counter of vics of this color: if successful, decrement
            vicsInLocOfClrKey = stateKey(WORLD, 'ctr_' + loc + '_' + color)
            tree = makeTree(anding(conds,
                                   incrementMatrix(vicsInLocOfClrKey, -1),
                                   noChangeMatrix(vicsInLocOfClrKey)))
            self.world.setDynamics(vicsInLocOfClrKey, action, tree)

            # white: increment
            vicsInLocOfClrKey = stateKey(WORLD, 'ctr_' + loc + '_' + WHITE_STR)
            tree = makeTree(anding(conds,
                                   incrementMatrix(vicsInLocOfClrKey, 1),
                                   noChangeMatrix(vicsInLocOfClrKey)))
            self.world.setDynamics(vicsInLocOfClrKey, action, tree)

        # Fov update to white
        tree = {'if': longEnough,
                True: setToConstantMatrix(fov_key, WHITE_STR),
                False: noChangeMatrix(fov_key)}
        self.world.setDynamics(fov_key, action, makeTree(tree))

        # Color saved counter: increment
        saved_key = stateKey(agent.name, 'numsaved_' + color)
        tree = {'if': longEnough,
                True: incrementMatrix(saved_key, 1),
                False: noChangeMatrix(saved_key)}
        self.world.setDynamics(saved_key, action, makeTree(tree))

        # Color saved: according to difference
        diff = {makeFuture(saved_key): 1, saved_key: -1}
        saved_key = stateKey(agent.name, 'saved_' + color)
        self.world.setDynamics(saved_key, action, makeTree(dynamicsMatrix(saved_key, diff)))
        self.world.setDynamics(saved_key, True, makeTree(setFalseMatrix(saved_key)))  # default: set to False

        self.triageActs[agent.name][color] = action

    @staticmethod
    def getUnObsName(loc, color):
        return 'unobs' + loc + '_' + color

    def createObsVars4Victims(self, agent):
        """
        Create a boolean per room per victim color.
        room_color=T means player knows this color victim is in room.
        room_color=F means player knows this color victim is not in room.
        Use a prior over P(room_color=T)
        """
        ks = []
        ds = []
        for loc in self.world_map.all_locations:
            for color in self.color_prior_p.keys():
                ks.append(self.world.defineState(agent.name, self.getUnObsName(loc, color), bool))
                ds.append(Distribution({True: self.color_prior_p[color], False: 1 - self.color_prior_p[color]}))

        if self.full_obs:
            for key in ks:
                self.world.setFeature(key, False)
        else:
            for i, (key, dist) in enumerate(zip(ks, ds)):
                agent.setBelief(key, dist)
                self.world.setFeature(key, dist)

    def _make_fov_color_dist(self, loc, cur_idx):
        if cur_idx == len(self.color_names):
            dist = {'none': 1}
            return dist, [dist]

        color = self.color_names[cur_idx]
        clr_counter = stateKey(WORLD, 'ctr_' + loc + '_' + color)
        tree = {'if': equalRow(clr_counter, 0)}

        branch, branch_leaves = self._make_fov_color_dist(loc, cur_idx + 1)
        for dist in branch_leaves:
            dist[color] = 0
        tree[True] = branch
        tree_leaves = branch_leaves

        branch, branch_leaves = self._make_fov_color_dist(loc, cur_idx + 1)
        for dist in branch_leaves:
            dist[color] = 2
        tree[False] = branch
        tree_leaves.extend(branch_leaves)

        return tree, tree_leaves

    def makeRandomFOVDistr(self, agent):
        fov_key = stateKey(agent.name, FOV_FEATURE)
        tree = {'if': equalRow(stateKey(agent.name, 'loc'), self.world_map.all_locations),
                None: noChangeMatrix(fov_key)}

        for il, loc in enumerate(self.world_map.all_locations):
            if loc not in self.victimClrCounts.keys():
                tree[il] = setToConstantMatrix(fov_key, 'none')
                continue

            sub_tree, leaves = self._make_fov_color_dist(loc, 0)
            for dist in leaves:
                prob_dist = Distribution(dist)
                prob_dist.normalize()
                dist.clear()
                weights = [(setToConstantMatrix(fov_key, c), p) for c, p in prob_dist.items() if p > 0]
                if len(weights) == 1:
                    weights.append((noChangeMatrix(fov_key), 0))
                dist['distribution'] = weights
            tree[il] = sub_tree

        return tree

    def makeSearchAction(self, agent):
        action = agent.addAction({'verb': 'search'})

        # A victim can randomly appear in FOV
        fov_key = stateKey(agent.name, FOV_FEATURE)
        fov_tree = self.makeRandomFOVDistr(agent)
        self.world.setDynamics(fov_key, action, makeTree(fov_tree))
        self.world.setDynamics(fov_key, True, makeTree(setToConstantMatrix(fov_key, 'none')))  # default: FOV is none

        self.searchActs[agent.name] = action

    def makeExpiryDynamics(self):

        # set every player's FOV to RED if they are seeing a victim
        vic_colors = [color for color in self.color_names if color not in {WHITE_STR, RED_STR}]
        for agent in self.triageActs.keys():
            fovKey = stateKey(agent, FOV_FEATURE)
            deathTree = {'if': equalRow(fovKey, vic_colors),
                         None: noChangeMatrix(fovKey)}
            for i, color in enumerate(vic_colors):
                expire = self.color_expiry[color]
                deathTree[i] = {'if': thresholdRow(self.world.time, expire),
                                True: setToConstantMatrix(fovKey, 'Red'),
                                False: noChangeMatrix(fovKey)}
            self.world.setDynamics(fovKey, True, makeTree(deathTree))

        # update victim loc counters
        for loc in self.world_map.all_locations:
            red_ctr = stateKey(WORLD, 'ctr_' + loc + '_' + 'Red')
            for color in vic_colors:
                ctr = stateKey(WORLD, 'ctr_' + loc + '_' + color)
                expire = self.color_expiry[color]

                # RED: if death time is reached, copy amount of alive victims to counter
                deathTree = {'if': thresholdRow(self.world.time, expire),
                             True: addFeatureMatrix(red_ctr, ctr),
                             False: noChangeMatrix(red_ctr)}
                self.world.setDynamics(red_ctr, True, makeTree(deathTree))

                # GREEN and GOLD: if death time reached, zero-out alive victims of that color
                deathTree = {'if': thresholdRow(self.world.time, expire),
                             True: setToConstantMatrix(ctr, 0),
                             False: noChangeMatrix(ctr)}
                self.world.setDynamics(ctr, True, makeTree(deathTree))

    def stochasticTriageDur(self):
        vic_colors = [color for color in self.color_names if color not in {WHITE_STR, RED_STR}]
        for color in vic_colors:
            stochTree = {'distribution': [
                (incrementMatrix(self.world.time, c), p) for c, p in self.color_reqd_times[color].items()]}
            for actions in self.triageActs.values():
                triageActColor = actions[color]
                self.world.setDynamics(self.world.time, triageActColor, makeTree(stochTree))

    def makeVictimReward(self, agent, model=None, rwd_dict=None):
        """ Human gets reward if flag is set
        """

        # collects victims saved of each color
        weights = {}
        for color in self.color_names:
            rwd = rwd_dict[color] if rwd_dict is not None and color in rwd_dict else \
                COLOR_REWARDS[color] if color in COLOR_REWARDS else None
            if rwd is None or rwd == 0:
                continue
            saved_key = stateKey(agent.name, 'saved_' + color)
            weights[saved_key] = rwd

        rwd_key = rewardKey(agent.name)
        agent.setReward(makeTree(dynamicsMatrix(rwd_key, weights)), 1., model)

    def getTriageAction(self, agent, color):
        if type(agent) == str:
            name = agent
        else:
            name = agent.name
        return self.triageActs[name][color]

    def getSearchAction(self, agent):
        if type(agent) == str:
            return self.searchActs[agent]
        else:
            return self.searchActs[agent.name]

    def triage(self, agent, select, color):
        self.world.step(self.getTriageAction(agent, color), select=select)

    def search(self, agent, select):
        self.world.step(self.getSearchAction(agent), select=select)
