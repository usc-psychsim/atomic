import logging
import os
import sys
from psychsim.helper_functions import get_true_model_name
from psychsim.probability import Distribution
from psychsim.pwl import modelKey, rewardKey, stateKey, makeTree, setToConstantMatrix
from model_learning.inference import track_reward_model_inference
from model_learning.util.io import create_clear_dir
from model_learning.util.plot import plot_evolution
from SandRMap import getSandRMap, getSandRVictims
from maker import makeWorld
from parser_no_pre import DataParser
from utils import get_participant_data_props as gpdp

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

try:
    # pass the index of the data file that you want. The index is over the list returned by the `get_participant_data_props` function, more files can be added to that list in `utils.py`
    DATA_FILE_IDX = int(sys.argv[1])
except IndexError:
    DATA_FILE_IDX = 0

TRAJ_START = 0
TRAJ_STOP = -1

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
MAX_TRAJ_LENGTH = 100


def _get_fancy_name(name):
    return name.title().replace('_', ' ')


if __name__ == '__main__':
    # create output
    create_clear_dir(OUTPUT_DIR)

    pdp = gpdp()
    pdp_itm = DATA_FILE_IDX

    DATA_FILENAME = pdp[pdp_itm]['fname']
    TRAJ_START = pdp[pdp_itm]['start']
    TRAJ_STOP = pdp[pdp_itm]['stop']

    # sets up log to file
    logging.basicConfig(
        handlers=[logging.StreamHandler(), logging.FileHandler(os.path.join(OUTPUT_DIR, 'inference.log'), 'w')],
        format='%(message)s', level=logging.DEBUG if DEBUG else logging.INFO)

    logging.info('Parsing data file {}...'.format(DATA_FILENAME))
    parser = DataParser(DATA_FILENAME)
    player_name = parser.data['player_ID'].iloc[0]
    logging.info('Got {} events for player "{}"'.format(parser.data.shape[0], player_name))

    # create world, agent and observer
    world, agent, observer, victimsObj = makeWorld(
        player_name, 'BH2', getSandRMap(), getSandRVictims(), False, FULL_OBS)

    # observer does not model itself
    observer.resetBelief(ignore={modelKey(observer.name)})

    # get the canonical name of the "true" agent model
    true_model = get_true_model_name(agent)

    # reward models (as linear combinations of victim color)
    mm_list = {
        PREFER_NONE_MODEL: {GREEN_VICTIM: MEAN_VAL, YELLOW_VICTIM: MEAN_VAL},
        PREFER_GREEN_MODEL: {GREEN_VICTIM: HIGH_VAL, YELLOW_VICTIM: LOW_VAL},
        PREFER_YELLOW_MODEL: {GREEN_VICTIM: LOW_VAL, YELLOW_VICTIM: HIGH_VAL}  # should be the most likely at the end
    }
    for name, rwd_dict in mm_list.items():
        if name != true_model:
            agent.addModel(name, parent=true_model, rationality=MODEL_RATIONALITY, selection=MODEL_SELECTION)
        victimsObj.makeVictimReward(agent, name, rwd_dict)

    if INCLUDE_RANDOM_MODEL:
        agent.addModel(RANDOM_MODEL, parent=true_model, rationality=.5, selection=MODEL_SELECTION)
        agent.setReward(makeTree(setToConstantMatrix(rewardKey(agent.name), 0)), model=RANDOM_MODEL)

    model_names = [name for name in agent.models.keys() if name != true_model]

    for name in model_names:
        agent.resetBelief(model=name, ignore={modelKey(observer.name)})

    # observer has uniform prior distribution over possible agent models
    world.setMentalModel(observer.name, agent.name,
                         Distribution({name: 1. / (len(agent.models) - 1) for name in model_names}))

    # observer sees everything except true models
    observer.omega = [key for key in world.state.keys()
                      if key not in {modelKey(agent.name), modelKey(observer.name)}]  # rewardKey(agent.name),

    # generates trajectory
    parser.victimsObj = victimsObj
    aes, _ = parser.getActionsAndEvents(agent.name, True, MAX_TRAJ_LENGTH)
    logging.info('Getting trajectory out of {} actions/events...'.format(len(aes)))

    if TRAJ_STOP == -1:
        TRAJ_STOP = len(aes)

    trajectory = parser.runTimeless(world, agent.name, aes, TRAJ_START, TRAJ_STOP, len(aes))
    logging.info('Recorded {} state-action pairs'.format(len(trajectory)))

    # gets evolution of inference over reward models of the agent
    probs = track_reward_model_inference(trajectory, model_names, agent, observer, [stateKey(agent.name, 'loc')])

    # create and save inference evolution plot
    plot_evolution(probs.T, [_get_fancy_name(name) for name in model_names],
                   'Evolution of Model Inference', None,
                   os.path.join(OUTPUT_DIR, 'inference.png'), 'Time', 'Model Probability', True)
