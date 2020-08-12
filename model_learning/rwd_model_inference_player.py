import copy
import logging
import os
import sys
sys.path.append('../')
from psychsim.action import ActionSet
from psychsim.helper_functions import get_true_model_name
from psychsim.probability import Distribution
from psychsim.pwl import modelKey, rewardKey, stateKey, makeTree, setToConstantMatrix, state2agent
from model_learning.inference import track_reward_model_inference
from model_learning.util.io import create_clear_dir
from model_learning.util.plot import plot_evolution
from SandRMap import getSandRMap, getSandRVictims
from maker import makeWorld
from parser_no_pre import DataParser
from victims_no_pre_instance import Victims

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
    DATA_FILENAME = sys.argv[1]
except IndexError:
    DATA_FILENAME = 'data/Florian_processed_1.csv'

OBSERVER_NAME = 'ATOMIC'
PLAYER_NAME = 'Player173'
YELLOW_VICTIM = 'Gold'
GREEN_VICTIM = 'Green'

# models
TRUE_MODEL = 'task_scores'
PREFER_NONE_MODEL = 'prefer_none'
PREFER_YELLOW_MODEL = 'prefer_yellow'
PREFER_GREEN_MODEL = 'prefer_green'
RANDOM_MODEL = 'zero_rwd'

# agents properties
HORIZON = 1
MODEL_SELECTION = 'distribution'  # TODO 'consistent' or 'random' gives an error
MODEL_RATIONALITY = .5
AGENT_SELECTION = 'random'

# victim reward values
HIGH_VAL = 200
LOW_VAL = 10
MEAN_VAL = (HIGH_VAL + LOW_VAL) / 2

OUTPUT_DIR = 'output/reward-model-inference'
DEBUG = False
SHOW = True
INCLUDE_RANDOM_MODEL = False
FULL_OBS = False


def _get_trajectory_from_parsing(world, agent, aes):
    trajectory = []
    act_or_event, act_event, *_ = aes[0]
    if act_or_event == DataParser.SET_FLG:
        var_name = act_event[0]
        var_value = act_event[1]
        world.setState(agent.name, var_name, var_value)
        agent.setBelief(stateKey(agent.name,var_name),var_value)

    elif act_or_event == DataParser.SEARCH:
        [sact, color] = act_event[1]
        key = stateKey(agent.name, 'vicInFOV')
        world.step(sact, select={key:world.value2float(key,color)})
    else:
        # This first action can be an actual action or an initial location
        if isinstance(act_event, ActionSet):
            world.step(act_event)
        else:
            world.setState(agent.name, 'loc', act_event)
            agent.setBelief(stateKey(agent.name,'loc'),act_event)
            world.setState(agent.name, 'seenloc_' + act_event, True)
            agent.setBelief(stateKey(agent.name,'seenloc_'+act_event),True)

    for act_event in aes[1:]:
        if act_event[0] == DataParser.ACTION:
            trajectory.append((copy.deepcopy(world), act_event[1]))
            world.step(act_event[1])
        elif act_event[0] == DataParser.SET_FLG:
            var, val = act_event[1]
            world.setState(agent.name, var, val)
        elif act_event[0] == DataParser.SEARCH:
            [sact, color] = act_event[1]
            key = stateKey(agent.name, 'vicInFOV')
            world.step(sact, select={key:world.value2float(key,color),'__default__': False})
    return trajectory


def _get_fancy_name(name):
    return name.title().replace('_', ' ')


if __name__ == '__main__':
    # sets up log to screen
    logging.basicConfig(format='%(message)s', level=logging.DEBUG if DEBUG else logging.INFO)

    logging.info('Parsing data file {}...'.format(DATA_FILENAME))
    parser = DataParser(DATA_FILENAME)
    PLAYER_NAME = parser.data['player_ID'].iloc[0]

    # create output
#    create_clear_dir(OUTPUT_DIR)

    # MDP or POMDP
    Victims.FULL_OBS = FULL_OBS

    # create world, agent and observer
    world, agent, observer, victimsObj = makeWorld(PLAYER_NAME, 'BH2', getSandRMap(), getSandRVictims(), use_unobserved=False)
    parser.victimsObj = victimsObj

    agent.setAttribute('horizon', HORIZON)
    agent.setAttribute('selection', AGENT_SELECTION)
    agent.resetBelief(ignore={modelKey(observer.name)})

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
    aes = parser.getActionsAndEvents(agent.name)
    logging.info('Getting trajectory out of {} actions/events...'.format(len(aes)))
    trajectory = runTimeless(world, agent, aes,0,len(aes),0)
    logging.info('Recorded {} state-action pairs'.format(len(trajectory)))

    # gets evolution of inference over reward models of the agent
    probs = track_reward_model_inference(trajectory, model_names, agent, observer, [stateKey(agent.name, 'loc')])

    # create and save inference evolution plot
    plot_evolution(probs.T, [_get_fancy_name(name) for name in model_names],
                   'Evolution of Model Inference', None,
                   os.path.join(OUTPUT_DIR, 'inference.png'), 'Time', 'Model Probability', True)
