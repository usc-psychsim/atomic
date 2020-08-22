from locations_no_pre import Directions
from psychsim.agent import Agent
from psychsim.pwl import equalRow, thresholdRow, makeTree, noChangeMatrix, setToConstantMatrix, rewardKey, \
    dynamicsMatrix, actionKey, setToFeatureMatrix, modelKey
from psychsim.reward import achieveFeatureValue
from model_learning.trajectory import generate_trajectories
from simple.sar_world import SearchAndRescueWorld, INIT_LOC, VIC_COLORS, TRIAGE_COLORS

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

DEF_HORIZON = 3
DEF_RATIONALITY = 1 / 0.05  # inverse temperature
DEF_SELECTION = 'distribution'  # stochastic over all actions

LOCATION_FEATURE = 'loc'
LOCATION_FREQ_FEATURE = 'loc_freq'


class PlayerAgent(Agent):
    """
    A class that encapsulates the dynamics and beliefs of a player agent in the search & rescue environment.
    The 4 cardinal movement actions plus a stay-still/no-op action are added to allow the agent to move in the
    world. A triage action per type of victim is also added.
    """

    def __init__(self, name, world, init_loc=INIT_LOC,
                 selection=DEF_SELECTION, horizon=DEF_HORIZON, rationality=DEF_RATIONALITY):
        """
        Creates a new player agent in the given world by adding the corresponding actions and dynamics.
        :param str name: the name of the agent.
        :param SearchAndRescueWorld world: the world where to add the agent.
        :param str selection: the action-selection strategy for the agent.
        :param int horizon: the agent's planning horizon.
        :param float rationality: the agent's rationality, i.e., the temperature parameter in a soft-max selection.
        """
        super().__init__(name, world)
        world.addAgent(self)
        world.player_agents.append(self)

        self.setAttribute('selection', selection)
        self.setAttribute('horizon', horizon * 2)  # have to consider cleaning agent
        self.setAttribute('rationality', rationality)

        # creates agent's location feature
        self.location_feature = world.defineState(
            self.name, LOCATION_FEATURE + world.name, list, world.all_locations,
            description='{}\'s location'.format(self.name))
        world.setFeature(self.location_feature, init_loc)

        # creates agent locations' frequency features
        self.location_frequency_features = {}
        for loc in world.all_locations:
            loc_freq_feat = world.defineState(
                self.name, LOCATION_FREQ_FEATURE + loc + world.name, int,
                description='{}\'s visitation frequency for {}'.format(self.name, loc))
            world.setFeature(loc_freq_feat, 0)
            self.location_frequency_features[loc] = loc_freq_feat

        # creates triage actions
        self.triage_actions = {}
        for color in TRIAGE_COLORS:
            # legality: checks if there's a victim of this color in the agent's location
            legal_tree = {'if': equalRow(self.location_feature, world.all_locations),
                          None: False}
            for i, loc in enumerate(world.all_locations):
                vic_amount_feat = world.victim_amount_features[loc][color]
                legal_tree[i] = {'if': thresholdRow(vic_amount_feat, 1),
                                 True: True,
                                 False: False}
            action = self.addAction({'verb': 'triage' + world.name, 'object': color}, makeTree(legal_tree))
            world.setDynamics(self.location_feature, action, makeTree(noChangeMatrix(self.location_feature)))
            self.triage_actions[color] = action

        # creates dynamics for the agent's movement (cardinal directions)
        self.move_actions = []
        for dir_idx, direction in enumerate(Directions.Names):
            # legality: checks locations that have neighbors in this direction
            legal_tree = {'if': equalRow(self.location_feature, world.locs_with_neighbors[dir_idx]),
                          True: True,
                          False: False}
            action = self.addAction({'verb': 'move' + world.name, 'object': direction}, makeTree(legal_tree))

            # move dynamics
            locs_with_neighbors = list(world.locs_with_neighbors[dir_idx])
            tree = {'if': equalRow(self.location_feature, locs_with_neighbors),
                    None: noChangeMatrix(self.location_feature)}
            for i, loc in enumerate(locs_with_neighbors):
                tree[i] = setToConstantMatrix(self.location_feature, world.loc_neighbors[loc][dir_idx])
            world.setDynamics(self.location_feature, action, makeTree(tree))
            self.move_actions.append(action)

        # add explicit no-op
        self.no_op = self.addAction({'verb': 'do-nothing'})
        world.setDynamics(self.location_feature, self.no_op, makeTree(noChangeMatrix(self.location_feature)))

    def generate_trajectories(self, n_trajectories, trajectory_length, init_locs=None,
                              model=None, horizon=None, selection=None, processes=-1, seed=0, verbose=False):
        """
        Generates a number of fixed-length trajectories (state-action pairs) for this agent.
        :param int n_trajectories: the number of trajectories to be generated.
        :param int trajectory_length: the length of the generated trajectories.
        :param list[str] init_locs: a list of initial locations from which to randomly initialize the trajectories.
        :param str model: the agent model used to generate the trajectories.
        :param int horizon: the agent's planning horizon.
        :param str selection: the action selection criterion, to untie equal-valued actions.
        :param int processes: number of processes to use. `<=0` indicates all cores available, `1` uses single process.
        :param int seed: the seed used to initialize the random number generator.
        :param bool verbose: whether to show information at each timestep during trajectory generation.
        :rtype: list[list[tuple[SearchAndRescueWorld, ActionSet]]]
        :return: the generated agent trajectories.
        """
        # generate trajectories starting from given or random locations in the environment
        init_feats = None if init_locs is None else [init_locs]
        return generate_trajectories(
            self, n_trajectories, trajectory_length,
            [self.location_feature], init_feats, model, horizon, selection, processes, seed, verbose)

    def set_victim_beliefs(self, color_amounts, model=None):
        """
        Sets beliefs about the amount of victims of each color over all locations in the environment.
        :param dict[str, int] color_amounts: the victim amounts for each color used to set the beliefs.
        :param str model: the agent's model on which to set the belief.
        :return:
        """
        assert len(color_amounts) > 0, 'At least one color has to be provided in \'{color_amounts}\''

        # sets omega: agents can observe everything
        self.resetBelief(ignore=modelKey(self.name))
        self.omega = [key for key in self.world.state.keys() if key != modelKey(self.name)]

        # sets the same belief for each location
        for i, loc in enumerate(self.world.all_locations):
            if loc != INIT_LOC:
                for color in VIC_COLORS:
                    if color in color_amounts:
                        self.setBelief(self.world.victim_amount_features[loc][color], color_amounts[color], model)

    def set_reach_location_reward(self, loc, weight=1., model=None):
        """
        Sets a reward to the agent for reaching a certain location.
        :param str loc: the location we want the agent to reach.
        :param float weight: the weight/value associated with this reward.
        :param str model: the agent's model on which to set the reward.
        :return:
        """
        self.setReward(makeTree(achieveFeatureValue(self.location_feature, loc, self.name)), weight, model)

    def set_victim_triage_reward(self, color_weights, model=None):
        """
        Sets a reward to the agent for making a triage action for each type/color of victim.
        This corresponds to a linear combination of the amount of change for each victim color.
        :param dict[str, float] color_weights: the weights/values for the difference in victim amount for each color.
        :param str model: the agent's model on which to set the reward.
        :return:
        """
        assert len(color_weights) > 0, 'At least one color weight has to be provided in \'{color_weights}\''

        rwd_feat = rewardKey(self.name)
        action_feat = actionKey(self.name)
        colors = [color for color in TRIAGE_COLORS if color in color_weights]
        triage_actions = [self.triage_actions[color] for color in colors]

        # compares the agent's action and provides a reward accordingly
        rwd_tree = {'if': equalRow(action_feat, triage_actions),
                    None: noChangeMatrix(rwd_feat)}
        for i, color in enumerate(colors):
            rwd_tree[i] = setToConstantMatrix(rwd_feat, color_weights[color])

        self.setReward(makeTree(rwd_tree), 1., model)

    def set_victim_amount_reward(self, color_weights, model=None):
        """
        Sets a reward to the agent that is proportional to the amount of victims of each color in its current location.
        This corresponds to a linear combination of the amount of each victim color.
        :param dict[str, float] color_weights: the weights/values for the victim amount for each color.
        :param str model: the agent's model on which to set the reward.
        :return:
        """
        assert len(color_weights) > 0, 'At least one color weight has to be provided in \'{color_weights}\''

        # compares the agent's current location and set reward accordingly
        rwd_feat = rewardKey(self.name)
        rwd_tree = {'if': equalRow(self.location_feature, self.world.all_locations),
                    None: noChangeMatrix(rwd_feat)}

        for i, loc in enumerate(self.world.all_locations):
            # get the weighted sum of victim amounts' changes for each color
            weighted_sum = {}
            for color in VIC_COLORS:
                if color not in color_weights:
                    continue
                weighted_sum[self.world.victim_amount_features[loc][color]] = color_weights[color]
            rwd_tree[i] = dynamicsMatrix(rwd_feat, weighted_sum)

        self.setReward(makeTree(rwd_tree), 1., model)

    def set_move_reward(self, direction_weights, model=None):
        """
        Sets a reward to the agent for moving in each of the given directions.
        This corresponds to a linear combination of the amount of each victim color.
        :param dict[int, float] direction_weights: the weights/values for each direction.
        :param str model: the agent's model on which to set the reward.
        :return:
        """
        assert len(direction_weights) > 0, 'At least one direction weight has to be provided in \'{direction_weights}\''

        rwd_feat = rewardKey(self.name)
        action_feat = actionKey(self.name)
        directions = [direction for direction in range(len(self.move_actions)) if direction in direction_weights]
        move_actions = [self.move_actions[direction] for direction in directions]

        # compares the agent's action and provides a reward accordingly
        rwd_tree = {'if': equalRow(action_feat, move_actions),
                    None: noChangeMatrix(rwd_feat)}
        for i, direction in enumerate(directions):
            rwd_tree[i] = setToConstantMatrix(rwd_feat, direction_weights[direction])

        self.setReward(makeTree(rwd_tree), 1., model)

    def set_location_frequency_reward(self, weight=1., inverse=True, model=None):
        """
        Sets a reward to the agent that is proportional to the agent's location frequency.
        :param float weight: the weight/value associated with this reward.
        :param bool inverse: whether to take the inverse frequency, i.e., `time - freq`.
        :param str model: the agent's model on which to set the reward.
        :return:
        """
        # compares the agent's current location
        rwd_feat = rewardKey(self.name)
        rwd_tree = {'if': equalRow(self.location_feature, self.world.all_locations),
                    None: noChangeMatrix(rwd_feat)}

        for i, loc in enumerate(self.world.all_locations):
            loc_freq_feat = self.location_frequency_features[loc]
            rwd_tree[i] = dynamicsMatrix(rwd_feat, {self.world.time_feat: 1., loc_freq_feat: -1.}) if inverse else \
                setToFeatureMatrix(rwd_feat, loc_freq_feat)

        self.setReward(makeTree(rwd_tree), weight, model)
