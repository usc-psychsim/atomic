import logging
import os
from SandRMap import getSandRMap, getSandRVictims, getSandRCoords
from locations_no_pre import Directions
from psychsim.helper_functions import get_true_model_name
from psychsim.pwl import stateKey, makeTree, setToConstantMatrix, rewardKey
from model_learning.inference import track_reward_model_inference
from model_learning.util.io import create_clear_dir, save_object
from model_learning.util.plot import plot_evolution
from simple import plotting
from simple.player_agent import PlayerAgent
from simple.sar_world import SearchAndRescueWorld, INIT_LOC, GREEN_STR, GOLD_STR

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__description__ = 'Perform reward model inference in the ASIST world based on synthetic/generated data.'

NUM_STEPS = 20
ACHIEVE_LOC = 'RJ'

OBSERVER_NAME = 'ATOMIC'
AGENT_NAME = 'Player'

# models
TRIAGER_MODEL = 'triager'
TRIAGER_GOLD_MODEL = 'triager_gold'
TRIAGER_GREEN_MODEL = 'triager_green'
EXPLORER_MODEL = 'explorer'
REACH_LOC_MODEL = 'reach_' + ACHIEVE_LOC
NE_NAVIGATOR_MODEL = 'move_NE'
RANDOM_MODEL = 'zero_rwd'

# agents properties
TRUE_RWD_MODEL = NE_NAVIGATOR_MODEL
HORIZON = 2
AGENT_SELECTION = 'random'
MODEL_SELECTION = 'distribution'  # TODO 'consistent' or 'random' gives an error
MODEL_RATIONALITY = .5

OUTPUT_DIR = 'output/reward-model-inference-simple'
DEBUG = False
SHOW = True
INCLUDE_RANDOM_MODEL = False
FULL_OBS = True  # False


def _get_fancy_name(name):
    return name.title().replace('_', ' ')


if __name__ == '__main__':
    # create output
    create_clear_dir(OUTPUT_DIR)

    # sets up log to screen
    logging.basicConfig(
        handlers=[logging.StreamHandler(), logging.FileHandler(os.path.join(OUTPUT_DIR, 'inference.log'), 'w')],
        format='%(message)s', level=logging.DEBUG if DEBUG else logging.INFO)

    # create S&R world
    world = SearchAndRescueWorld(getSandRMap(), getSandRVictims(), getSandRCoords())
    plotting.plot(world, os.path.join(OUTPUT_DIR, 'env.pdf'), title='S&R World (Initial State)')

    # create agent
    agent = PlayerAgent(AGENT_NAME, world, INIT_LOC, AGENT_SELECTION, HORIZON)

    # create agent models and corresponding reward functions
    true_model = get_true_model_name(agent)
    agent.addModel(REACH_LOC_MODEL, parent=true_model, rationality=MODEL_RATIONALITY, selection=MODEL_SELECTION)
    agent.set_reach_location_reward(ACHIEVE_LOC, model=REACH_LOC_MODEL)
    agent.addModel(TRIAGER_GREEN_MODEL, parent=true_model, rationality=MODEL_RATIONALITY, selection=MODEL_SELECTION)
    agent.set_victim_triage_reward({GREEN_STR: 1.}, model=TRIAGER_GREEN_MODEL)
    agent.addModel(TRIAGER_GOLD_MODEL, parent=true_model, rationality=MODEL_RATIONALITY, selection=MODEL_SELECTION)
    agent.set_victim_triage_reward({GOLD_STR: 1.}, model=TRIAGER_GOLD_MODEL)
    agent.addModel(NE_NAVIGATOR_MODEL, parent=true_model, rationality=MODEL_RATIONALITY, selection=MODEL_SELECTION)
    agent.set_move_reward({Directions.N: .4, Directions.E: .6}, model=NE_NAVIGATOR_MODEL)
    agent.addModel(EXPLORER_MODEL, parent=true_model, rationality=MODEL_RATIONALITY, selection=MODEL_SELECTION)
    agent.set_location_frequency_reward(.1, model=EXPLORER_MODEL)
    if INCLUDE_RANDOM_MODEL:
        agent.setReward(makeTree(setToConstantMatrix(rewardKey(agent.name), 0)))
    model_names = [name for name in agent.models.keys() if name != true_model]

    # sets true reward
    agent.setReward(agent.getReward(TRUE_RWD_MODEL), 1.)

    # creates observer agent and resets beliefs
    observer = world.add_observer_agent(agent)
    world.prepare()

    # generates trajectory
    logging.info('Generating trajectory of length {}...'.format(NUM_STEPS))
    trajectories = agent.generate_trajectories(1, NUM_STEPS, [INIT_LOC], verbose=True)
    save_object(trajectories[0], os.path.join(OUTPUT_DIR, 'trajectory.pkl.gz'), True)

    # gets evolution of inference over reward models of the agent
    probs = track_reward_model_inference(trajectories[0], model_names, agent, observer, [stateKey(agent.name, 'loc')])

    # create and save inference evolution plot
    plot_evolution(probs.T, [_get_fancy_name(name) for name in model_names],
                   'Evolution of Model Inference', None,
                   os.path.join(OUTPUT_DIR, 'inference.pdf'), 'Time', 'Model Probability', True)

    plotting.plot_trajectories(world, trajectories, os.path.join(OUTPUT_DIR, 'trajectories.pdf'))
    plotting.plot_location_frequencies(agent, os.path.join(OUTPUT_DIR, 'location_frequencies.pdf'), trajectories)
    plotting.plot_action_frequencies(agent, os.path.join(OUTPUT_DIR, 'action_frequencies.pdf'), trajectories)
    plotting.plot(world, os.path.join(OUTPUT_DIR, 'final-env.pdf'), trajectories[0][-1][0].state,
                  'S&R World (Final State)')
