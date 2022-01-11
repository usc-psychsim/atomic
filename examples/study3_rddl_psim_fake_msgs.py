import argparse
import logging
import os.path
import sys

from rddl2psychsim.conversion.converter import Converter
from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry
from atomic.parsing.parse_into_msg_qs import MsgQCreator
from rddl2psychsim.conversion.task_tree import AllTrees, PROP

THRESHOLD = 0
def exec_step(msgs, conv):
    actions = {}
    teleported = []
    
    ## For any player with an Event:location msg with empty old room, teleport to new room
    for player_name, msg in msgs.items():
        if (msg['sub_type'] == 'Event:location') and (msg['old_room_name'] == ''):
            room = msg['room_name']
            print('Teleporting %s to %s' %(player_name, room))
            teleported.append(player_name)
#            conv.world.setState(player_name, 'ploc', room, recurse=True)
            conv.world.setState(player_name, '(ploc, ' + room + ')', True, recurse=True)
    
    ## For players that were teleported, replace their msgs with noop actions
    for tele_player in teleported:
        msgs[tele_player] = {'playername':tele_player, 'sub_type':'noop'}
        
    for player_name, msg in msgs.items():
        mtime = msg.get('mission_timer', '')
        action_name = Msg2ActionEntry.get_action(msg)
        ## If no psychsim action, inject a noop
        if action_name not in conv.actions[player_name]:
            action_name = Msg2ActionEntry.get_action({'playername':player_name, 'sub_type':'noop'})
            print(f'Msg {msg} has no associated action at {mtime}')
        else:
            print(f'Player {player_name} does {action_name} at {mtime}')
            
        action = conv.actions[player_name][action_name]
        actions[player_name] = action        
        if not action in conv.world.agents[player_name].getLegalActions():
            print(f'Illegal action: {action}')
    conv.world.step(actions, threshold=0, select=True)
    conv.log_state(log_actions=True)
    return actions

####################  J S O N   M S G   T O  P S Y C H S I M   A C T I O N   N A M E
json_msg_action_lookup_fname = os.path.join(os.path.dirname(__file__), '..', 'data', 'rddl_psim', 'study3', 'rddl2actions_1.csv')
ddir = os.path.join(os.path.dirname(__file__), '..', 'data', 'ASU_DATA')
    
Msg2ActionEntry.read_psysim_msg_conversion(json_msg_action_lookup_fname)
usable_msg_types = Msg2ActionEntry.get_msg_types()

#################  R D D L  2  P S Y C H S I M    W O R L D
logging.root.setLevel(logging.INFO)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.INFO)


##################  M S G S
derived_features = []
RDDL_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'rddl_psim', 'study3', 'other.rddl')

all_msgs = []
all_msgs.append({'med': {'room_name':'tkt_1', 'playername':'med', 'old_room_name':'', 'sub_type':'Event:location'}, 
                 'eng': {'room_name':'tkt_1', 'playername':'eng', 'old_room_name':'', 'sub_type':'Event:location'}, 
                 'tran': {'room_name':'sga_7', 'playername':'tran', 'old_room_name':'', 'sub_type':'Event:location'}})
    
all_msgs.append({'med': {'mission_timer': '14 : 23', 'triage_state': 'SUCCESSFUL', 'type': 'REGULAR', 'sub_type': 'Event:Triage',
                        'playername': 'med', 'room_name': 'tkt_1', 'victim_id': 'v1'},
                 'tran': {'sub_type': 'noop', 'playername': 'tran'},
                 'eng': {'sub_type': 'noop', 'playername': 'eng'}} )
                 

conv = Converter()
conv.convert_file(RDDL_FILE, verbose=False)

allTrees = AllTrees(True)
## Create fluent nodes
for feat_name, psim_name in conv.features.items():
    val = conv.world.getFeature(psim_name)    
    allTrees.create_node(psim_name, PROP, psim_name, val)
allTrees.build(conv.world.dynamics, {player.name:player.legal for player in conv.world.agents.values()})

##################  S T E P    T H R O U G H
num = len(all_msgs)
seen_victims = dict()
seen_locations = set()

def extract_vics_and_locs(msgs):
    victims = dict()
    locations = set()
    for msg in msgs:
        if 'victim_id' in msg.keys():
            victims[msg['victim_id']] = msg['room_name']
        if 'room_name' in msg.keys():
            locations.add(msg['room_name'])
    return victims, locations

allTrees.copy_world_values(conv.world, {})
allTrees.print()
for i, msgs in enumerate(all_msgs):
    print(f'\n__________________________________________________{i} out of {num}')
    vics, locs = extract_vics_and_locs(msgs.values())
    new_locs = locs.difference(seen_locations)
    new_vics = [v for v in vics.keys() if v not in seen_victims.keys()]
    seen_victims.update(vics)
    seen_locations = seen_locations.union(locs)
    actions = exec_step(msgs, conv)
    allTrees.copy_world_values(conv.world, actions.values())
    allTrees.print()
#    break

#
##print(seen_victims, seen_locations)
#
#   
