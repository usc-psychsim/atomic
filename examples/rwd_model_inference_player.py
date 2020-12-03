import logging
import os
import random
from atomic.definitions.plotting import plot_environment
from atomic.inference import set_player_models
from atomic.parsing.replayer import Replayer
from atomic.scenarios.single_player import make_single_player_world
from psychsim.pwl import stateKey
from model_learning.inference import track_reward_model_inference
from model_learning.util.io import create_clear_dir, change_log_handler
from model_learning.util.plot import plot_evolution
from atomic.model_learning.parser import TrajectoryParser

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__description__ = 'Perform reward model inference in the ASIST world based on human player data.' \
                  'There is an observer agent that has 4 models of the moving agent (uniform prior):' \
                  '  - a model with the true reward function;' \
                  '  - a model with a zero reward function, resulting in a random behavior;' \
                  '  - other models with different weights for each victim type.' \
                  'We collect a trajectory where the world is updated for some steps and the observer updates its ' \
                  'belief over the models of the triaging agent via PsychSim inference. ' \
                  'A plot is show with the inference evolution.'

DATA_FILE = 'data/glasgow/processed_20200724_Participant1_Cond1.csv'
MAP = 'falcon'

YELLOW_VICTIM = 'Gold'
GREEN_VICTIM = 'Green'

# models
TRUE_MODEL = 'task_scores'
PREFER_NONE_MODEL = 'prefer_none'
PREFER_YELLOW_MODEL = 'prefer_gold'
PREFER_GREEN_MODEL = 'prefer_green'
RANDOM_MODEL = 'zero_rwd'

# agents properties
MODEL_SELECTION = 'distribution'  # TODO 'consistent' or 'random' gives an error
MODEL_RATIONALITY = .5

# victim reward values
HIGH_VAL = 200
LOW_VAL = 10
MEAN_VAL = (HIGH_VAL + LOW_VAL) / 2

OUTPUT_DIR = 'output/reward-model-inference-data'
DEBUG = False
SHOW = True
INCLUDE_RANDOM_MODEL = False
FULL_OBS = True  # False

PRUNE_THRESHOLD = 1e-3
MAX_TRAJ_LENGTH = -1
SEED = 0


def _get_fancy_name(name):
    return name.title().replace('_', ' ')


if __name__ == '__main__':

    # initialize random seed
    random.seed(SEED)

    # create output and log file
    create_clear_dir(OUTPUT_DIR)
    change_log_handler(os.path.join(OUTPUT_DIR, 'inference.log'), 2 if DEBUG else 1)

    replayer = Replayer([DATA_FILE])
    map_info = replayer.maps[MAP]
    neighbors = map_info.adjacency
    locations = list(map_info.rooms)
    victims_locs = map_info.victims
    coords = map_info.coordinates

    logging.info('Parsing data file {}...'.format(DATA_FILE))
    parser = TrajectoryParser(DATA_FILE)
    player_name = parser.player_name()
    logging.info('Got {} events for player "{}"'.format(parser.data.shape[0], player_name))

    # create world, agent and observer
    world, agent, observer, victims, world_map = \
        make_single_player_world(player_name, map_info['start'], neighbors, victims_locs, False, FULL_OBS)

    plot_environment(world, locations, neighbors, os.path.join(OUTPUT_DIR, 'map.pdf'), coords)

    model_list = [{'name': PREFER_NONE_MODEL, 'reward': {GREEN_VICTIM: MEAN_VAL, YELLOW_VICTIM: MEAN_VAL},
                   'rationality': MODEL_RATIONALITY, 'selection': MODEL_SELECTION},
                  {'name': PREFER_GREEN_MODEL, 'reward': {GREEN_VICTIM: HIGH_VAL, YELLOW_VICTIM: LOW_VAL},
                   'rationality': MODEL_RATIONALITY, 'selection': MODEL_SELECTION},
                  {'name': PREFER_YELLOW_MODEL, 'reward': {GREEN_VICTIM: LOW_VAL, YELLOW_VICTIM: HIGH_VAL},
                   'rationality': MODEL_RATIONALITY, 'selection': MODEL_SELECTION}]

    if INCLUDE_RANDOM_MODEL:
        model_list.append({'name': RANDOM_MODEL, 'reward': {GREEN_VICTIM: 0, YELLOW_VICTIM: 0,
                                                            'rationality': MODEL_RATIONALITY,
                                                            'selection': MODEL_SELECTION}})

    set_player_models(world, observer.name, agent.name, victims, model_list)

    # generates trajectory
    aes, _ = parser.getActionsAndEvents(agent.name, victims, world_map, True, MAX_TRAJ_LENGTH)
    logging.info('Getting trajectory out of {} actions/events...'.format(len(aes)))

    parser.runTimeless(world, agent.name, aes, 0, len(aes), prune_threshold=PRUNE_THRESHOLD)
    logging.info('Recorded {} state-action pairs'.format(len(parser.trajectory)))

    # gets evolution of inference over reward models of the agent
    model_names = [m['name'] for m in model_list]
    probs = track_reward_model_inference(parser.trajectory, model_names, agent, observer, [stateKey(agent.name, 'loc')])

    # create and save inference evolution plot
    plot_evolution(probs.T, [_get_fancy_name(name) for name in model_names],
                   'Evolution of Model Inference', None,
                   os.path.join(OUTPUT_DIR, 'inference.png'), 'Time', 'Model Probability', True)
