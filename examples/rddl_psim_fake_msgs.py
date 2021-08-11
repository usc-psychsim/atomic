import argparse
import logging
import sys

from rddl2psychsim.conversion.converter import Converter
from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry

THRESHOLD = 0
USE_COLLAPSED = True


#################  J S O N   M S G   T O  P S Y C H S I M   A C T I O N   N A M E
if USE_COLLAPSED:
    json_msg_action_lookup_fname = '/home/mostafh/Documents/psim/new_atomic/atomic/data/rddl_psim/rddl2actions_fol.csv'
    lookup_aux_data_fname = '/home/mostafh/Documents/psim/new_atomic/atomic/maps/Saturn/rddl_clpsd_neighbors.csv'
    RDDL_FILE = '../data/rddl_psim/role_clpsd_map.rddl'
else:
    json_msg_action_lookup_fname = '/home/mostafh/Documents/psim/new_atomic/atomic/data/rddl_psim/rddl2actions_small.csv'
    lookup_aux_data_fname = None
    RDDL_FILE = '../data/rddl_psim/role_big.rddl'
    
Msg2ActionEntry.read_psysim_msg_conversion(json_msg_action_lookup_fname, lookup_aux_data_fname)
usable_msg_types = Msg2ActionEntry.get_msg_types()

##################  R D D L  2  P S Y C H S I M    W O R L D
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
args.log_rewards = True

conv = Converter()
conv.convert_file(RDDL_FILE, verbose=True)

##################  F A K E    M S G S
all_msgs = []
if USE_COLLAPSED:    
    ## correct message
    all_msgs.append({'p1': {'room_name':'sga_A', 'playername':'p1', 'old_room_name':'sga_B', 'sub_type':'Event:location'}, 
                 'p2':{'room_name':'sga_A', 'playername':'p2', 'old_room_name':'sga_B', 'sub_type':'Event:location'}, 
                 'p3':{'room_name':'ew_A', 'playername':'p3', 'old_room_name':'sga_A', 'sub_type':'Event:location'}})

    ## message with an impossible move
    all_msgs.append({'p1': {'room_name':'ew_A', 'playername':'p1', 'old_room_name':'sga_A', 'sub_type':'Event:location'}, 
                 'p2':{'room_name':'ccn', 'playername':'p2', 'old_room_name':'sga_A', 'sub_type':'Event:location'}, 
                 'p3':{'room_name':'el_A', 'playername':'p3', 'old_room_name':'ew_A', 'sub_type':'Event:location'}})

else:
    all_msgs.append({'p1': {'room_name':'sdc', 'playername':'p1', 'old_room_name':'el', 'sub_type':'Event:location'}, 
                 'p2':{'room_name':'ew', 'playername':'p2', 'old_room_name':'el', 'sub_type':'Event:location'}, 
                 'p3':{'room_name':'ca', 'playername':'p3', 'old_room_name':'ds', 'sub_type':'Event:location'}})
####################  S T E P    T H R O U G H
REPLAY = True
    
for msgs in all_msgs:
    logging.info('\n__________________________________________________N E W    S T E P')
    debug = {ag_name: {} for ag_name in conv.actions.keys()} if args.log_rewards else dict()
    
    # Print legal actions
    for player_name, msg in msgs.items():
        leg_acts = [str(a) for a in conv.world.agents[player_name].getLegalActions()]
        print('legal actions of', player_name, '\n',  '\n'.join(leg_acts))
    
    
    if REPLAY:
        actions = {}
        any_none = False
        for player_name, msg in msgs.items():
            action_name = Msg2ActionEntry.get_action(msg)
            if action_name not in conv.actions[player_name]:
                any_none = True
                logging.warning(f'Msg {msg} has no associated action')
            else:
                logging.info(f'Player {player_name} does {action_name}')
                action = conv.actions[player_name][action_name]
                actions[player_name] = action
        
        if any_none:
            input('cont..')
            continue
        
        conv.world.step(actions, debug=debug, threshold=args.threshold, select=args.select)
    else:
        conv.world.step(debug=debug, threshold=args.threshold, select=args.select)
        
    conv.log_state(log_actions=args.log_actions)
#    print('rewards')
#    for player_name, msg in msgs.items():
#        print(conv.world.agents[player_name].reward())
#
#
#    if args.log_rewards:
#        for ag_name in conv.actions.keys():
#            _log_agent_reward(ag_name)
#    conv.verify_constraints()
#
#
#

#import pickle
#from atomic.parsing.remap_connections import transformed_connections
#file = open("/home/mostafh/sem_map.pickle", 'rb')
#map_file = pickle.load(file)
#edge_list, lookup, new_map, orig_map = transformed_connections(map_file)


