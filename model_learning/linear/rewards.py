import numpy as np
from psychsim.agent import Agent
from psychsim.pwl import equalRow, rewardKey, makeTree, setToFeatureMatrix, dynamicsMatrix, noChangeMatrix
from model_learning.features.linear import ValueComparisonLinearRewardFeature, LinearRewardVector, \
    NumericLinearRewardFeature, LinearRewardFeature, ActionLinearRewardFeature
from atomic_domain_definitions.features import get_mission_phase_key, get_triaged_key, get_mission_seconds_key, \
    get_num_visits_location_key, get_location_key, get_fov_key
from ftime import MISSION_PHASES, MISSION_PHASE_END_TIMES, MIDDLE_STR

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

    # features.extend([ValueComparisonLinearRewardFeature(
    #     'Mission ' + phase.title().replace('_', ' '), world, get_mission_phase_key(), phase, '==')
    #     for phase in MISSION_PHASES])

    features.append(ValueComparisonLinearRewardFeature(
        'Before Middle', world, get_mission_seconds_key(),
        MISSION_PHASE_END_TIMES[MISSION_PHASES.index(MIDDLE_STR)], '<'))
    features.append(ValueComparisonLinearRewardFeature(
        'After Middle', world, get_mission_seconds_key(),
        MISSION_PHASE_END_TIMES[MISSION_PHASES.index(MIDDLE_STR)] - 1, '>'))

    features.append(LocationFrequencyReward('Location Frequency', agent, locations, False))

    features.append(NumericLinearRewardFeature('Triaged Green', get_triaged_key(agent, 'Green')))
    features.append(NumericLinearRewardFeature('Triaged Gold', get_triaged_key(agent, 'Gold')))

    features.append(ValueComparisonLinearRewardFeature('See White', world, get_fov_key(agent), 'White', '=='))
    features.append(ValueComparisonLinearRewardFeature('See Red', world, get_fov_key(agent), 'Red', '=='))

    features.extend([ActionLinearRewardFeature(
        'Move ' + next(iter(action))['object'], agent, action) for action in move_actions])

    return LinearRewardVector(features)


class LocationFrequencyReward(LinearRewardFeature):
    """
    A reward feature that gets a reward proportional to the current location's visitation frequency.
    """

    def __init__(self, name, agent, all_locations, inverse=True):
        """
        Creates a new reward feature.
        :param Agent agent: the PsychSim agent capable of retrieving the feature's value given a state.
        :param str name: the label for this reward feature.
        :param list[str] all_locations: all the world's locations.
        :param bool inverse: whether to take the inverse frequency, i.e., `time - freq`.
        """
        super().__init__(name)
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
        return np.array(values).dot(np.array(probs))

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

        agent.setReward(makeTree(rwd_tree), weight, model)
