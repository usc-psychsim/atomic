import argparse
import logging
import os.path
import sys

from rddl2psychsim.conversion.converter import Converter
from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry

from psychsim.pwl import stateKey 
from psychsim.probability import Distribution 

THRESHOLD = 0
RDDL_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'rddl_psim', 'mark_v1_template.rddl')


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
args.log_rewards = True

conv = Converter()
conv.convert_file(RDDL_FILE, verbose=True)

p1 = conv.world.agents['p1']
p1.create_belief_state()
p1.set_observations(unobservable={stateKey('p2', 'correct_sem')})
p1.setBelief(stateKey('p2', 'correct_sem'), Distribution({True: 0.5, False: 0.5}))

p2 = conv.world.agents['p2']
p2.create_belief_state()
p2.set_fully_observable()

p1_zero = p1.zero_level()
p1.setAttribute('selection', 'distribution', p1_zero)
p2_zero = p2.zero_level()
p2.setAttribute('selection', 'distribution', p2_zero)

conv.world.setModel(p2.name, p2_zero, p1.name, p1.get_true_model())
conv.world.setModel(p1.name, p1_zero, p2.name, p2.get_true_model())

beliefs = p1.getBelief(model=p1.get_true_model())
print('===p1 initial belief')
conv.world.printState(beliefs, beliefs=False)

json_msg_action_lookup_fname = os.path.join(os.path.dirname(__file__), '..', 'data', 'rddl_psim', 'rddl2actions_fol.csv')
lookup_aux_data_fname = os.path.join(os.path.dirname(__file__), '..', 'maps', 'Saturn', 'rddl_clpsd_neighbors.csv')
Msg2ActionEntry.read_psysim_msg_conversion(json_msg_action_lookup_fname, lookup_aux_data_fname)
usable_msg_types = Msg2ActionEntry.get_msg_types()
#
##################  F A K E    M S G S
all_msgs = []
all_msgs.append({'p1': {'room_name':'ew_A', 'playername':'p1', 'old_room_name':'el_A', 'sub_type':'Event:location'}, 
                 'p2':{'room_name':'sga_B', 'playername':'p2', 'old_room_name':'sga_A', 'sub_type':'Event:location'}})

all_msgs.append({'p1': {'room_name':'el_A', 'playername':'p1', 'old_room_name':'ew_A', 'sub_type':'Event:location'}, 
                 'p2':{'room_name':'sga_A', 'playername':'p2', 'old_room_name':'sga_B', 'sub_type':'Event:location'}})
    
#    all_msgs.append({'p1': {'type':'Marker Block 1', 'playername':'p1', 'sub_type':'Event:MarkerPlaced'}, 
#                 'p2':{'room_name':'loc12', 'playername':'p2', 'sub_type':'Event:location'}})

###################  S T E P    T H R O U G H
REPLAY = True
    
for i, msgs in enumerate(all_msgs):
    logging.info(f'\n__________________________________________________{i}')
    debug = {ag_name: {} for ag_name in conv.actions.keys()} if args.log_rewards else dict()
    
    ## Print legal actions
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
    
    beliefs = p1.getBelief(model=p1.get_true_model())
    print('===p1 belief')
    conv.world.printState(beliefs, beliefs=False)
    
#    print('rewards')
#    for player_name, msg in msgs.items():
#        print(conv.world.agents[player_name].reward())

    conv.verify_constraints()



