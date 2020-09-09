from psychsim.pwl import stateKey, WORLD
from psychsim.agent import Agent
from atomic.definitions.world import PHASE_FEATURE
from atomic.definitions.victims import FOV_FEATURE


def get_mission_seconds_key():
    """
    Gets the named key of the feature corresponding to the number of seconds since the start of the mission.
    :rtype: str
    :return: the corresponding PsychSim feature key.
    """
    return stateKey(WORLD, 'seconds')


def get_mission_phase_key():
    """
    Gets the named key of the feature corresponding to the current phase of the mission (related with mission time).
    :rtype: str
    :return: the corresponding PsychSim feature key.
    """
    return stateKey(WORLD, PHASE_FEATURE)


def get_triaged_key(agent, color):
    """
    Gets the named key of the feature corresponding to whether the agent has triaged a victim of the given color.
    :param Agent agent: the agent for which to get the feature.
    :param str color: the victim's color.
    :rtype: str
    :return: the corresponding PsychSim feature key.
    """
    return stateKey(agent.name, 'saved_' + color)


def get_num_triaged_key(agent, color):
    """
    Gets the named key of the feature corresponding to the number of victims of a color that the agent has triaged.
    :param Agent agent: the agent for which to get the feature.
    :param str color: the victim's color.
    :rtype: str
    :return: the corresponding PsychSim feature key.
    """
    return stateKey(agent.name, 'numsaved_' + color)


def get_fov_key(agent):
    """
    Gets the named key of the feature corresponding to the color of the victim in the agent's field-of-view (FOV).
    :param Agent agent: the agent for which to get the feature.
    :rtype: str
    :return: the corresponding PsychSim feature key.
    """
    return stateKey(agent.name, FOV_FEATURE)


def get_location_key(agent):
    """
    Gets the named key of the feature corresponding to the agent's current location / room in the environment.
    :param Agent agent: the agent for which to get the feature.
    :rtype: str
    :return: the corresponding PsychSim feature key.
    """
    return stateKey(agent.name, 'loc')


def get_num_visits_location_key(agent, location):
    """
    Gets the named key of the feature corresponding to the number of visits to a location made by an agent.
    :param Agent agent: the agent for which to get the feature.
    :param str location: the location / room of the environment.
    :rtype: str
    :return: the corresponding PsychSim feature key.
    """
    return stateKey(agent.name, 'locvisits_' + location)


def get_num_victims_location_key(location, color):
    """
    Gets the named key of the feature corresponding to number of victims of some type in the given location.
    :param str location: the location / room of the environment.
    :param str color: the victim's color.
    :rtype: str
    :return: the corresponding PsychSim feature key.
    """
    return stateKey(WORLD, 'ctr_' + location + '_' + color)
