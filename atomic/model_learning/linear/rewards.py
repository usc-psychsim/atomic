import numpy as np
from psychsim.pwl.plane import thresholdRow
from psychsim.agent import Agent
from psychsim.pwl import equalRow, rewardKey, makeTree, setToFeatureMatrix, dynamicsMatrix, noChangeMatrix, \
    setToConstantMatrix
from model_learning.features.linear import ValueComparisonLinearRewardFeature, LinearRewardVector, \
    NumericLinearRewardFeature, LinearRewardFeature, ActionLinearRewardFeature
from atomic.definitions.features import get_triaged_key, get_mission_seconds_key, get_num_visits_location_key, \
    get_location_key, get_num_victims_location_key
from atomic.definitions.world import MISSION_PHASES, MISSION_PHASE_END_TIMES, MIDDLE_STR

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'


def create_reward_vector(agent, locations, move_actions):
    """
    Creates the default linear reward vector.
    :param Agent agent: the PsychSim agent capable of retrieving the features' values given a state.
    :param list[str] locations: the list of possible world locations.
    :param list[ActionSet] move_actions: the list of the agent's move_actions.
    :rtype: LinearRewardVector
    :return: the linear reward vector.
    """
    world = agent.world
    features = []

    features.append(ValueComparisonLinearRewardFeature(
        'Before Middle', world, get_mission_seconds_key(),
        MISSION_PHASE_END_TIMES[MISSION_PHASES.index(MIDDLE_STR)], '<'))
    features.append(ValueComparisonLinearRewardFeature(
        'After Middle', world, get_mission_seconds_key(),
        MISSION_PHASE_END_TIMES[MISSION_PHASES.index(MIDDLE_STR)] - 1, '>'))

    # features.append(LocationFrequencyReward('Location Frequency', agent, locations, False))
    features.append(LocationVisitedReward('Location Visited', agent, locations))

    features.append(NumericLinearRewardFeature('Triaged Green', get_triaged_key(agent, 'Green')))
    features.append(NumericLinearRewardFeature('Triaged Gold', get_triaged_key(agent, 'Gold')))

    features.append(LocationVictimColorReward('See White', agent, 'White', locations))
    features.append(LocationVictimColorReward('See Red', agent, 'Red', locations))

    features.extend([ActionLinearRewardFeature(
        'Move ' + next(iter(action))['object'], agent, action) for action in move_actions])

    return LinearRewardVector(features)


class LocationVictimColorReward(LinearRewardFeature):
    """
    A binary reward feature that is True (1) if the agent is currently in a location where there is a victim of
    a given color, False (0) otherwise.
    """

    def __init__(self, name, agent, color, all_locations):
        """
        Creates a new reward feature.
        :param Agent agent: the PsychSim agent capable of retrieving the feature's value given a state.
        :param str name: the label for this reward feature.
        :param str color: the victim color.
        :param list[str] all_locations: all the world's locations.
        """
        super().__init__(name)
        self.agent = agent
        self.world = agent.world
        self.all_locations = all_locations
        self.color = color
        self.location_feat = get_location_key(agent)

    def get_value(self, state):
        # collects feature value distribution
        values = []
        probs = []
        for loc_kv, loc_p in state.distributions[state.keyMap[self.location_feat]].items():
            # gets current location and victim color counter
            loc = self.world.float2value(self.location_feat, loc_kv[self.location_feat])
            loc_color_feat = get_num_victims_location_key(loc, self.color)

            for loc_color_kv, loc_color_p in state.distributions[state.keyMap[loc_color_feat]].items():
                # gets amount of color victims at location
                num_vics = loc_color_kv[loc_color_feat]
                values.append(int(num_vics >= 1))
                probs.append(loc_p * loc_color_p)

        # returns weighted average
        return np.array(values).dot(np.array(probs)) * self.normalize_factor

    def set_reward(self, agent, weight, model=None):
        rwd_feat = rewardKey(agent.name)

        # compares agent's current location
        rwd_tree = {'if': equalRow(self.location_feat, self.all_locations),
                    None: noChangeMatrix(rwd_feat)}

        # get binary value according to color victims at location
        for i, loc in enumerate(self.all_locations):
            loc_color_feat = get_num_victims_location_key(loc, self.color)
            rwd_tree[i] = {'if': thresholdRow(loc_color_feat, 0),
                           True: setToConstantMatrix(rwd_feat, 1),
                           False: setToConstantMatrix(rwd_feat, 0)}

        agent.setReward(makeTree(rwd_tree), weight * self.normalize_factor, model)


class LocationVisitedReward(LinearRewardFeature):
    """
    A binary reward feature that is True (1) if the agent has visited the current location before, False (0) otherwise.
    """

    def __init__(self, name, agent, all_locations):
        """
        Creates a new reward feature.
        :param str name: the label for this reward feature.
        :param Agent agent: the PsychSim agent capable of retrieving the feature's value given a state.
        :param list[str] all_locations: all the world's locations.
        """
        super().__init__(name)
        self.agent = agent
        self.world = agent.world
        self.all_locations = all_locations
        self.location_feat = get_location_key(agent)

    def get_value(self, state):
        # collects feature value distribution
        values = []
        probs = []
        for loc_kv, loc_p in state.distributions[state.keyMap[self.location_feat]].items():
            # gets current location
            loc = self.world.float2value(self.location_feat, loc_kv[self.location_feat])
            loc_freq_feat = get_num_visits_location_key(self.agent, loc)

            for loc_freq_kv, loc_freq_p in state.distributions[state.keyMap[loc_freq_feat]].items():
                # gets visitation frequency at current location
                freq = loc_freq_kv[loc_freq_feat]

                values.append(int(freq > 1))
                probs.append(loc_p * loc_freq_p)

        # returns weighted average
        return np.array(values).dot(np.array(probs)) * self.normalize_factor

    def set_reward(self, agent, weight, model=None):
        rwd_feat = rewardKey(agent.name)

        # compares agent's current location
        rwd_tree = {'if': equalRow(self.location_feat, self.all_locations),
                    None: noChangeMatrix(rwd_feat)}

        # get binary value according to visitation of location
        for i, loc in enumerate(self.all_locations):
            loc_freq_feat = get_num_visits_location_key(agent, loc)
            rwd_tree[i] = {'if': thresholdRow(loc_freq_feat, 1),
                           True: setToConstantMatrix(rwd_feat, 1),
                           False: setToConstantMatrix(rwd_feat, 0)}

        agent.setReward(makeTree(rwd_tree), weight * self.normalize_factor, model)


class LocationFrequencyReward(LinearRewardFeature):
    """
    A reward feature that gets a reward proportional to the current location's visitation frequency.
    """

    def __init__(self, name, agent, all_locations, inverse=True, max_frequency=1):
        """
        Creates a new reward feature.
        :param Agent agent: the PsychSim agent capable of retrieving the feature's value given a state.
        :param str name: the label for this reward feature.
        :param list[str] all_locations: all the world's locations.
        :param bool inverse: whether to take the inverse frequency, i.e., `time - freq`.
        :param int max_frequency: the maximum frequency that the agent can achieve (either for any or all locations).
        """
        super().__init__(name, 1. / max_frequency)  # use max frequency as normalization factor to keep var in [0,1]
        self.agent = agent
        self.world = agent.world
        self.inverse = inverse
        self.all_locations = all_locations
        self.location_feat = get_location_key(agent)
        self.time_feat = get_mission_seconds_key()

    def get_value(self, state):
        # collects feature value distribution
        values = []
        probs = []
        for loc_kv, loc_p in state.distributions[state.keyMap[self.location_feat]].items():
            # gets current location
            loc = self.world.float2value(self.location_feat, loc_kv[self.location_feat])
            loc_freq_feat = get_num_visits_location_key(self.agent, loc)

            for loc_freq_kv, loc_freq_p in state.distributions[state.keyMap[loc_freq_feat]].items():
                # gets visitation frequency at current location
                freq = loc_freq_kv[loc_freq_feat]

                if self.inverse:
                    for time_kv, time_p in state.distributions[state.keyMap[self.time_feat]].items():
                        # gets current time
                        time = time_kv[self.time_feat]
                        values.append(time - freq)
                        probs.append(loc_p * loc_freq_p * time_p)
                else:
                    values.append(freq)
                    probs.append(loc_p * loc_freq_p)

        # returns weighted average
        return np.array(values).dot(np.array(probs)) * self.normalize_factor

    def set_reward(self, agent, weight, model=None):
        rwd_feat = rewardKey(agent.name)

        # compares agent's current location
        rwd_tree = {'if': equalRow(self.location_feat, self.all_locations),
                    None: noChangeMatrix(rwd_feat)}

        # get visitation count according to location
        for i, loc in enumerate(self.all_locations):
            loc_freq_feat = get_num_visits_location_key(agent, loc)
            rwd_tree[i] = dynamicsMatrix(rwd_feat, {self.time_feat: 1., loc_freq_feat: -1.}) \
                if self.inverse else setToFeatureMatrix(rwd_feat, loc_freq_feat)

        agent.setReward(makeTree(rwd_tree), weight * self.normalize_factor, model)
