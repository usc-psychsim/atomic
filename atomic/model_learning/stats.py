import copy
import numpy as np
from collections import OrderedDict
from psychsim.agent import Agent
from psychsim.probability import Distribution
from psychsim.world import World
from atomic.definitions.features import get_num_visits_location_key

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'


def get_location_frequencies(agent, trajectories, locations):
    """
    Gets the visitation frequencies of the agent for each location according to the provided trajectories.
    :param Agent agent: the agent whose visitation frequency we want to retrieve.
    :param list[list[tuple[World, Distribution]]] trajectories: the set of trajectories containing sequences of
    state-action pairs.
    :param list[str] locations: the list of possible world locations.
    :rtype: dict[str,float]
    :return: the visitation frequencies for each location.
    """
    world = agent.world
    data = np.zeros(len(locations))
    for trajectory in trajectories:
        traj_data = []
        for loc in locations:
            freq_feat = get_num_visits_location_key(agent, loc)
            state = copy.deepcopy(trajectory[-1][0].state)
            state.select(True)
            freq = world.getFeature(freq_feat, state, True)
            traj_data.append(freq)
        data += traj_data
    data = dict(zip(locations, data))
    return data


def get_action_frequencies(agent, trajectories):
    """
    Gets the action-execution frequencies of the agent according to the provided trajectories.
    :param Agent agent: the agent whose execution frequency we want to retrieve.
    :param list[list[tuple[World, Distribution]]] trajectories: the set of trajectories containing sequences of
    state-action pairs.
    :rtype: dict[str,float]
    :return: the execution frequencies for each action.
    """
    # gets action execution frequencies
    actions = sorted(agent.actions, key=lambda a: str(a))
    data = OrderedDict({a: 0 for a in actions})
    for trajectory in trajectories:
        for _, dist in trajectory:
            for a, p in dist.items():
                data[a] += p
    return data
