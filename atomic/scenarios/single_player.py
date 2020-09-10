import logging
from psychsim.pwl import modelKey, rewardKey, setToConstantMatrix, makeTree
from atomic.definitions.world_map import WorldMap
from atomic.definitions.victims import Victims
from atomic.definitions.world import SearchAndRescueWorld
from atomic.inference import make_observer

COLOR_PRIOR_P = {'Green': 0.3, 'Gold': 0.4}
COLOR_FOV_P = {'Green': 0.2, 'Gold': 0.2, 'Red': 0.2, 'White': 0.4}
COLOR_REQD_TIMES = {'Green': {5: 0.2, 8: 0.4}, 'Gold': {5: 0.2, 15: 0.4}}


def make_single_player_world(
        player_name, init_loc, loc_neighbors, victims_color_locs, use_unobserved=True, full_obs=False, logger=logging):
    # create world and map
    world = SearchAndRescueWorld()
    world_map = WorldMap(world, loc_neighbors)

    # create victims info
    victims = Victims(world, victims_color_locs, world_map, full_obs=full_obs,
                      color_prior_p=COLOR_PRIOR_P, color_fov_p=COLOR_FOV_P, color_reqd_times=COLOR_REQD_TIMES)

    # (single) triage agent
    triage_agent = world.addAgent(player_name)
    world_map.makePlayerLocation(triage_agent, init_loc)
    victims.setupTriager(triage_agent)
    victims.createTriageActions(triage_agent)
    victims.makeExpiryDynamics()
    victims.stochasticTriageDur()
    if not full_obs:
        if use_unobserved:
            logger.debug('Start to make observable variables and priors')
            victims.createObsVars4Victims(triage_agent)
        logger.debug('Made observable variables and priors')
    victims.makeSearchAction(triage_agent)
    logger.debug('Made actions for triage agent: {}'.format(triage_agent.name))
    triage_agent.setReward(makeTree(setToConstantMatrix(rewardKey(triage_agent.name), 0)))  # dummy reward

    world.setOrder([{triage_agent.name}])

    # observer agent
    observer = make_observer(world, [triage_agent.name], 'ATOMIC')

    # adjust agent's beliefs and observations
    triage_agent.resetBelief()
    triage_agent.omega = [key for key in world.state.keys()
                          if not ((key in {modelKey(observer.name), rewardKey(triage_agent.name)})
                                  or (key.find('unobs') > -1))]

    return world, triage_agent, observer, victims, world_map
