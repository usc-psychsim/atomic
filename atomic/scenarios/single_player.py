import logging
from psychsim.pwl import modelKey, rewardKey, setToConstantMatrix, makeTree
from atomic.definitions.world_map import WorldMap
from atomic.definitions.victims import Victims
from atomic.definitions.world import SearchAndRescueWorld
from atomic.inference import make_observer

OBSERVER_NAME = 'ATOMIC'
COLOR_PRIOR_P = {'Green': 0.3, 'Gold': 0.4}
COLOR_REQD_TIMES = {'Green': {5: 0.2, 8: 0.4}, 'Gold': {5: 0.2, 15: 0.4}}


def make_single_player_world(
        player_name, init_loc, loc_neighbors, victims_color_locs, use_unobserved=True, full_obs=False,
        create_observer=True, logger=logging):
    # create world and map
    world = SearchAndRescueWorld()
    world_map = WorldMap(world, loc_neighbors)

    # create victims info
    victims = Victims(world, victims_color_locs, world_map, full_obs=full_obs,
                      color_prior_p=COLOR_PRIOR_P, color_reqd_times=COLOR_REQD_TIMES)

    # create (single) triage agent
    triage_agent = world.addAgent(player_name)

    world_map.makePlayerLocation(triage_agent, init_loc)
    victims.setupTriager(triage_agent)
    victims.createTriageActions(triage_agent)
    if not full_obs:
        if use_unobserved:
            logger.debug('Start to make observable variables and priors')
            victims.createObsVars4Victims(triage_agent)
        logger.debug('Made observable variables and priors')
    logger.debug('Made actions for triage agent: {}'.format(triage_agent.name))
    triage_agent.setReward(makeTree(setToConstantMatrix(rewardKey(triage_agent.name), 0)))  # dummy reward

    # after all agents are created
    victims.makeExpiryDynamics()
    victims.stochasticTriageDur()

    world.setOrder([{triage_agent.name}])

    # observer agent
    observer = make_observer(world, [triage_agent.name], OBSERVER_NAME) if create_observer else None

    # adjust agent's beliefs and observations
    triage_agent.resetBelief()
    triage_agent.omega = [key for key in world.state.keys()
                          if not ((key in {modelKey(observer.name if observer is not None else ''),
                                           rewardKey(triage_agent.name)})
                                  or (key.find('unobs') > -1))]

    return world, triage_agent, observer, victims, world_map


if __name__ == '__main__':
    # Create a world using the simple map and save the file out (for use in generating a graphical visualization of the model)
    import sys
    import atomic.definitions.map_utils as utils
    import atomic.inference as inference

    map_data = utils.get_default_maps()['simple']
    world, triage_agent, observer, victims, world_map = make_single_player_world(
        'player', map_data.init_loc, map_data.adjacency, map_data.victims, False)
    inference.set_player_models(world, observer.name, triage_agent.name, victims,
                                [{'name': 'player0', 'reward': {'Green': 1, 'Gold': 3}}])
    world.save('world.psy' if len(sys.argv) == 1 else sys.argv[1])
