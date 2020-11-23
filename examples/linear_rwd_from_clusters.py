import logging
import os
import numpy as np
import random
from model_learning.trajectory import generate_trajectory
from model_learning.util.io import create_clear_dir, save_object, change_log_handler
from atomic.definitions.plotting import plot_trajectories, plot_agent_location_frequencies, \
    plot_agent_action_frequencies, plot_environment
from atomic.model_learning.linear.post_process.clustering import load_cluster_reward_weights
from atomic.model_learning.linear.rewards import create_reward_vector
from atomic.scenarios.single_player import make_single_player_world
from atomic.parsing.parser import summarizeState
from atomic.definitions.map_utils import getSandRMap, getSandRVictims, DEFAULT_MAPS, getSandRCoords

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__description__ = 'Loads the results of linear reward vector clustering and sets the agent with the weights of the ' \
                  'first cluster.'

CLUSTERS_FILE = 'data/rewards/linear/hackathon_cluster_weights.csv'
MAP_TABLE = DEFAULT_MAPS['sparky']
OUTPUT_DIR = 'output/linear_rwd_from_clusters'
DEBUG = False
FULL_OBS = True

# agents properties
AGENT_NAME = 'Player'
SELECTION = 'distribution'
RATIONALITY = 1 / 0.1  # inverse temperature
HORIZON = 2

NUM_STEPS = 100

if __name__ == '__main__':
    np.set_printoptions(precision=2, suppress=True)

    # create output
    create_clear_dir(OUTPUT_DIR)

    # sets up log to file
    change_log_handler(os.path.join(OUTPUT_DIR, 'output.log'), 2 if DEBUG else 1)

    # loads clusters
    cluster_weights = load_cluster_reward_weights(CLUSTERS_FILE)
    logging.info('Loaded {} clusters from {}:'.format(len(cluster_weights), CLUSTERS_FILE))
    for cluster in sorted(cluster_weights):
        logging.info('\tCluster {}: {}'.format(cluster, cluster_weights[cluster]))

    # create world and agent
    loc_neighbors = getSandRMap(fname=MAP_TABLE['room_file'])
    locations = list(loc_neighbors.keys())
    victims_color_locs = getSandRVictims(fname=MAP_TABLE['victim_file'])
    coords = getSandRCoords(fname=MAP_TABLE['coords_file'])
    init_loc = random.sample(locations, 1)[0]

    world, agent, observer, victims, world_map = \
        make_single_player_world(AGENT_NAME, init_loc, loc_neighbors, victims_color_locs, False, FULL_OBS)
    plot_environment(world, locations, loc_neighbors, os.path.join(OUTPUT_DIR, 'env.pdf'), coords)

    # set agent params
    agent.setAttribute('horizon', HORIZON)
    agent.setAttribute('selection', SELECTION)
    agent.setAttribute('rationality', RATIONALITY)

    # set agent rwd function
    rwd_vector = create_reward_vector(agent, locations, world_map.moveActions[agent.name])
    rwd_weights = random.sample(list(cluster_weights.values()), 1)[0]
    rwd_vector.set_rewards(agent, rwd_weights, model=None)
    logging.info('Set reward vector: {}'.format(dict(zip(rwd_vector.names, rwd_weights))))

    # generates trajectory
    logging.info('Generating trajectory of length {}...'.format(NUM_STEPS))
    trajectory = generate_trajectory(agent, NUM_STEPS, verbose=lambda: summarizeState(world, agent.name))
    save_object(trajectory, os.path.join(OUTPUT_DIR, 'trajectory.pkl.gz'), True)

    # print stats
    plot_trajectories(agent, [trajectory], locations, loc_neighbors,
                      os.path.join(OUTPUT_DIR, 'trajectory.pdf'), coords, title='Trajectory')
    plot_agent_location_frequencies(agent, [trajectory], locations, os.path.join(OUTPUT_DIR, 'loc-frequencies.pdf'))
    plot_agent_action_frequencies(agent, [trajectory], os.path.join(OUTPUT_DIR, 'action-frequencies.pdf'))
