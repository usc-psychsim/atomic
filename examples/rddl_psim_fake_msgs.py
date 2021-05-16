import argparse
import logging
import sys

from rddl2psychsim.conversion.converter import Converter
from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry

THRESHOLD = 0
#RDDL_FILE = '../data/rddl_psim/sar_v3_inst1.rddl'
RDDL_FILE = '../data/rddl_psim/sar_v3_inst1_small.rddl'


#################  R D D L  2  P S Y C H S I M    W O R L D
logging.root.setLevel(logging.INFO)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.INFO)

def _log_agent_reward(ag_name):
    true_model = conv.world.agents[ag_name].get_true_model()
    action = debug[ag_name]['__decision__'][true_model]['action']
    rwd = debug[ag_name]['__decision__'][true_model]['V'][action]['__ER__']
    rwd = None if len(rwd) == 0 else rwd[0]
    logging.info(f'{ag_name}\'s reward: {rwd}')


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

conv = Converter()
conv.convert_file(RDDL_FILE, verbose=True)

#################  J S O N   M S G   T O  P S Y C H S I M   A C T I O N   N A M E

fname = '../data/rddl_psim/rddl2actions.csv'
Msg2ActionEntry.read_psysim_msg_conversion(fname)

#################  F A K E    M S G S
all_msgs = []
all_msgs.append({'p1': {'room_name':'tkt_2', 'playername':'p1', 'sub_type':'Event:Location'}, 'p2':{'room_name':'tkt_5', 'playername':'p2', 'sub_type':'Event:Location'}})
all_msgs.append({'p1': {'room_name':'tkt_3', 'playername':'p1', 'sub_type':'Event:Location'}, 'p2':{'room_name':'tkt_4', 'playername':'p2', 'sub_type':'Event:Location'}})

#################  S T E P    T H R O U G H
for msgs in all_msgs:
    logging.info('\n__________________________________________________')
    debug = {ag_name: {} for ag_name in conv.actions.keys()} if args.log_rewards else dict()
    
    actions = {}
    for player_name, msg in msgs.items():
        action_name = Msg2ActionEntry.get_action(msg)
        action = conv.actions[player_name][action_name]
        actions[player_name] = action
    
    conv.world.step(actions, debug=debug, threshold=args.threshold, select=args.select)
    conv.log_state(log_actions=args.log_actions)
    if args.log_rewards:
        for ag_name in conv.actions.keys():
            _log_agent_reward(ag_name)
    conv.verify_constraints()



