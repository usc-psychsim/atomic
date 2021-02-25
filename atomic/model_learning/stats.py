import numpy as np
from collections import OrderedDict
from psychsim.agent import Agent
from psychsim.probability import Distribution
from psychsim.world import World
from atomic.definitions.features import get_num_visits_location_key, get_mission_seconds_key

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'


def get_locations_frequencies(trajectories, agents, locations):
    """
    Gets the visitation frequencies of the agent for each location according to the provided trajectories.
    :param list[list[(World, Distribution)]] trajectories: the set of trajectories, containing sequences of state-action pairs.
    :param Agent or list[Agent] agents: a list with the agent for each trajectory set whose location frequencies we want to retrieve.
    :param list[str] locations: the list of possible world locations.
    :rtype: dict[str,float]
    :return: the visitation frequencies for each location.
    """
    if isinstance(agents, Agent):
        agents = [agents] * len(trajectories)
    assert len(trajectories) == len(agents), 'One agent per set of trajectories has to be provided'

    data = np.zeros(len(locations))
    for i in range(len(trajectories)):
        world = trajectories[i][-1][0]
        traj_data = []
        for loc in locations:
            loc_freq_feat = get_num_visits_location_key(agents[i], loc)
            traj_data.append(world.getFeature(loc_freq_feat).expectation())
        data += traj_data
    return dict(zip(locations, data))


def get_actions_frequencies(trajectories, agents):
    """
    Gets the mean action execution frequencies for each agent in the given trajectories.
    :param list[list[(World, Distribution)]] trajectories: the set of trajectories, containing sequences of state-action pairs.
    :param Agent or list[Agent] agents: a list with the agent for each trajectory set whose execution frequency we want to retrieve.
    :rtype: dict[str,(float,float)]
    :return: the mean and std error action execution frequencies per agent.
    """
    if isinstance(agents, Agent):
        agents = [agents] * len(trajectories)
    assert len(trajectories) == len(agents), 'One agent per set of trajectories has to be provided'

    data = {}
    for i in range(len(trajectories)):
        # collect agent data
        ag_data = {}
        for _, a_dist in trajectories[i]:
            for a, p in a_dist.items():
                a = str(a).replace('{}-'.format(agents[i].name), '').replace('_', ' ')  # get clean action name
                if a not in ag_data:
                    ag_data[a] = 0.
                ag_data[a] += p

        for a, freq in ag_data.items():
            if a not in data:
                data[a] = []
            data[a].append(freq)

    # get mean and std err per agent
    return OrderedDict({a: [np.mean(data[a]), np.std(data[a]) / len(data[a])] for a in sorted(data)})


def get_actions_durations(trajectories, agents):
    """
    Gets the average durations of actions according to the given trajectories.
    :param list[list[(World, Distribution)]] trajectories: the set of trajectories, containing sequences of state-action pairs.
    :param Agent or list[Agent] agents: a list with the agent for each trajectory set whose actions durations we want to retrieve.
    :rtype: dict[str,(float,float)]
    :return: the mean and std error action duration.
    """
    if isinstance(agents, Agent):
        agents = [agents] * len(trajectories)
    assert len(trajectories) == len(agents), 'One agent per set of trajectories has to be provided'

    data = {}
    clock_key = get_mission_seconds_key()
    for i in range(len(trajectories)):
        trajectory = trajectories[i]
        for t in range(len(trajectory) - 1):

            # compute clock diff
            duration = trajectory[t + 1][0].getFeature(clock_key, unique=True) - \
                       trajectory[t][0].getFeature(clock_key, unique=True)

            # get action and register duration
            a_dist = trajectory[t][1]
            for a, p in a_dist.items():
                a = str(a).replace('{}-'.format(agents[i].name), '').replace('_', ' ') # get clean action name
                if a not in data:
                    data[a] = []
                data[a].append(p * duration)

    return OrderedDict({a: [np.mean(data[a]), np.std(data[a]) / len(data[a])] for a in sorted(data)})
