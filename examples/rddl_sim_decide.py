import argparse
import logging
import sys

from rddl2psychsim.conversion.converter import Converter
from psychsim.pwl import modelKey

THRESHOLD = 0
#RDDL_FILE = '../data/rddl_psim/sar_v3_inst1.rddl'
#RDDL_FILE = '../data/rddl_psim/sar_mv_tr_big.rddl'
#RDDL_FILE = '../data/rddl_psim/mv_tr_tool_template_small.rddl'
#RDDL_FILE = '../data/rddl_psim/mv_tr_tool_big.rddl'
#RDDL_FILE = '../data/rddl_psim/vic_move_big.rddl'
# RDDL_FILE = '../data/rddl_psim/role_big.rddl'
RDDL_FILE = '../../atomic/data/rddl_psim/role_big_2_rooms_3_agents.rddl'

#################  R D D L  2  P S Y C H S I M    W O R L D
logging.root.setLevel(logging.INFO)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.INFO)

def _log_agent_reward(ag_name):
    if '__decision__' not in debug[ag_name]:
        return
    true_model = conv.world.agents[ag_name].get_true_model()
    decision = debug[ag_name]['__decision__'][true_model]
    action = decision['action']
    rwd = decision['V'][action]['__ER__'] if 'V' in decision else []
    rwd = None if len(rwd) == 0 else rwd[0]
    logging.info(f'{ag_name}\'s action: {action} reward: {rwd}')

parser = argparse.ArgumentParser()
parser.add_argument('--input', '-i', type=str, default=RDDL_FILE, help='RDDL file to be converted to PsychSim.')
parser.add_argument('--threshold', '-t', type=float, default=THRESHOLD,
                    help='Stochastic outcomes with a likelihood below this threshold are pruned.')
parser.add_argument('--select', action='store_true',
                    help='Whether to select an outcome if dynamics are stochastic.')
parser.add_argument('--log-actions', action='store_true',
                    help='Whether to log agents\' actions in addition to current state.')
parser.add_argument('--log-rewards', action='store_true',
                    help='Whether to log agents\' rewards wrt chosen actions in addition to current state.')
args = parser.parse_args()
#args.log_rewards = True

conv = Converter()
conv.convert_file(RDDL_FILE, verbose=True)

agents = set(conv.world.agents.keys())
for agent in conv.world.agents.values():
    agent.create_belief_state()
zeros = {name: agent.zero_level() for name, agent in conv.world.agents.items()}
for name, agent in conv.world.agents.items():
    beliefs = agent.getBelief()
    model = agent.get_true_model()
    belief = agent.getBelief(model=model)
    for other in agents-{name}:
        conv.world.setFeature(modelKey(other), zeros[other], belief)
#################  S T E P    T H R O U G H
steps  = 10
for i in range(steps):
    logging.info(f'\n__________________________________________________{i}')
    debug = {ag_name: {} for ag_name in conv.actions.keys()} if args.log_rewards else dict()
    
    conv.world.step(debug=debug, threshold=args.threshold, select=args.select)
    conv.log_state(log_actions=args.log_actions)
    if args.log_rewards:
        for ag_name in conv.actions.keys():
            _log_agent_reward(ag_name)
    conv.verify_constraints()