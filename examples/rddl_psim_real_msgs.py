import argparse
import logging
import sys
import numpy as np

from rddl2psychsim.conversion.converter import Converter
from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry
from atomic.parsing.parse_into_msg_qs import MsgQCreator
from atomic.parsing.count_features import CountAction, CountPlayerDialogueEvents, CountRoleChanges, CountTriageInHallways, CountEnterExit

THRESHOLD = 0
#RDDL_FILE = '../data/rddl_psim/sar_v3_inst1.rddl'
#RDDL_FILE = '../data/rddl_psim/sar_mv_tr_big.rddl'
#RDDL_FILE = '../data/rddl_psim/mv_tr_tool_template_small.rddl'
#RDDL_FILE = '../data/rddl_psim/mv_tr_tool_big.rddl'
#RDDL_FILE = '../data/rddl_psim/vic_move_big.rddl'
RDDL_FILE = '../data/rddl_psim/role_clpsd_map.rddl'

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

#all_loc_name = list(msg_qs.jsonParser.rooms.keys())
#main_names = [nm[:nm.find('_')] for nm in all_loc_name if nm.find('_') >=0] 
#main_names = set(main_names + [nm for nm in all_loc_name if nm.find('_') < 0] )
#hallways = ['ccw', 'cce', 'mcw', 'mce', 'scw', 'sce', 'sccc']
#room_names = main_names.difference(hallways)


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

####################  J S O N   M S G   T O  P S Y C H S I M   A C T I O N   N A M E

json_msg_action_lookup_fname = '../data/rddl_psim/rddl2actions_fol.csv'
lookup_aux_data_fname = '../maps/Saturn/rddl_clpsd_neighbors.csv'
Msg2ActionEntry.read_psysim_msg_conversion(json_msg_action_lookup_fname, lookup_aux_data_fname)
usable_msg_types = Msg2ActionEntry.get_msg_types()
#
##################  M S G S
ddir = '../data/ASU_DATA/'
fname = ddir + 'study-2_pilot-2_2021.02_HSRData_TrialMessages_Trial-T000423_Team-TM000112_Member-na_CondBtwn-2_CondWin-SaturnB_Vers-1.metadata'

msg_qs = MsgQCreator(fname, logger=logging)
derived_features = []
#derived_features.append(CountAction('Event:dialogue_event', {}))
#derived_features.append(CountAction('Event:VictimPickedUp', {}))
#derived_features.append(CountAction('Event:VictimPlaced', {}))
#derived_features.append(CountAction('Event:ToolUsed', {}))
#derived_features.append(CountAction('Event:Triage', {'triage_state':'SUCCESSFUL'}))
#derived_features.append(CountRoleChanges())
#derived_features.append(CountAction('Event:RoleSelected', {}))
#derived_features.append(CountEnterExit(room_names))
#derived_features.append(CountTriageInHallways(hallways))

msg_qs.startProcessing(derived_features, usable_msg_types)

#################  S T E P    T H R O U G H
num = len(msg_qs.actions)
for i, msgs in enumerate(msg_qs.actions):
    logging.info(f'\n__________________________________________________{i} out of {num}')
    debug = {ag_name: {} for ag_name in conv.actions.keys()} if args.log_rewards else dict()
    
    actions = {}
    for player_name, msg in msgs.items():
        action_name = Msg2ActionEntry.get_action(msg)
        if action_name not in conv.actions[player_name]:
            logging.warning(f'Msg {msg} has no associated action')
            action_name = '(noop, ' + player_name + ')'
            if msg['sub_type'] == 'Event:location' and msg['old_room_name'] == '':
                conv.world.setState(player_name, 'pLoc', msg['room_name'], recurse=True)
        else:
            logging.info(f'Msg {msg} becomes {action_name}')
            
        action = conv.actions[player_name][action_name]
        actions[player_name] = action
    
    conv.world.step(actions, debug=debug, threshold=args.threshold, select=args.select)
    conv.log_state(log_actions=args.log_actions)
    if args.log_rewards:
        for ag_name in conv.actions.keys():
            _log_agent_reward(ag_name)
    conv.verify_constraints()
    if  (i%2) == 0:
        input('cont..')



