import logging
import os
from psychsim.pwl import modelKey, stateKey
from model_learning.inference import track_reward_model_inference
from model_learning.trajectory import generate_trajectory
from model_learning.util.io import create_clear_dir, save_object, change_log_handler
from model_learning.util.plot import plot_evolution
from atomic.inference import set_player_models
from atomic.scenarios.single_player import make_single_player_world
from atomic.definitions.map_utils import get_default_maps

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__description__ = 'Perform reward model inference in the ASIST world based on synthetic/generated data.' \
                  'There is one acting agent whose reward function is to save victims according to the task score.' \
                  'There is an observer agent that has models of the moving agent (uniform prior):' \
                  '  - a model with a zero reward function, resulting in a random behavior;' \
                  '  - other models with different weights for each victim type.' \
                  'We collect a trajectory based on a data file and the observer updates its belief over the models ' \
                  'of the triaging agent via PsychSim inference. ' \
                  'A plot is show with the inference evolution.'

EXPT = 'FalconEasy'
IS_SMALL = False
NUM_STEPS = 5

AGENT_NAME = 'Player'
YELLOW_VICTIM = 'Gold'
GREEN_VICTIM = 'Green'

# models
PREFER_NONE_MODEL = 'prefer_none'
PREFER_YELLOW_MODEL = 'prefer_gold'
PREFER_GREEN_MODEL = 'prefer_green'
RANDOM_MODEL = 'zero_rwd'

# agents properties
HORIZON = 2
MODEL_SELECTION = 'distribution'  # TODO 'consistent' or 'random' gives an error
MODEL_RATIONALITY = 10
AGENT_SELECTION = 'random'

# victim reward values
HIGH_VAL = 200
LOW_VAL = 10
MEAN_VAL = (HIGH_VAL + LOW_VAL) / 2

OUTPUT_DIR = 'output/reward-model-inference'
DEBUG = False
SHOW = True
INCLUDE_RANDOM_MODEL = False
FULL_OBS = True


def _get_fancy_name(name):
    return name.title().replace('_', ' ')


def create_mental_models(world, agent, observer, victimsObj):
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

    set_player_models(world, observer.name, agent.name, victimsObj, model_list)
    return [m['name'] for m in model_list]


if __name__ == '__main__':
    # create output
    create_clear_dir(OUTPUT_DIR)

    # sets up log to file
    change_log_handler(os.path.join(OUTPUT_DIR, 'inference.log'), 2 if DEBUG else 1)

    maps = get_default_maps()
    if EXPT not in maps:
        raise NameError(f'Experiment "{EXPT}" is not implemented yet')

    # create world, agent and observer
    map_data = maps[EXPT]
    world, agent, observer, victims, world_map = \
        make_single_player_world(AGENT_NAME, map_data.init_loc, map_data.adjacency, map_data.victims, False, FULL_OBS)
    agent.setAttribute('horizon', HORIZON)
    agent.setAttribute('selection', AGENT_SELECTION)
    agent.resetBelief(ignore={modelKey(observer.name)})

    model_names = create_mental_models(world, agent, observer, victims)

    # generates trajectory
    logging.info('Generating trajectory of length {}...'.format(NUM_STEPS))
    trajectory = generate_trajectory(agent, NUM_STEPS)
    save_object(trajectory, os.path.join(OUTPUT_DIR, 'trajectory.pkl.gz'), True)

    # gets evolution of inference over reward models of the agent
    probs = track_reward_model_inference(
        trajectory, model_names, agent, observer, [stateKey(agent.name, 'loc')], verbose=False)

    # create and save inference evolution plot
    plot_evolution(probs.T, [_get_fancy_name(name) for name in model_names],
                   'Evolution of Model Inference', None,
                   os.path.join(OUTPUT_DIR, 'inference.png'), 'Time', 'Model Probability', True)
