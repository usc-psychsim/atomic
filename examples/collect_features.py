import logging, sys

from atomic.parsing.get_psychsim_action_name import Msg2ActionEntry
from atomic.parsing.parse_into_msg_qs import MsgQCreator
from atomic.parsing.count_features import CountAction, CountRoleChanges, CountTriageInHallways, CountEnterExit

logging.root.setLevel(logging.INFO)

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(message)s', level=logging.INFO)

fname = '../data/rddl_psim/rddl2actions_small.csv'
Msg2ActionEntry.read_psysim_msg_conversion(fname)
usable_msg_types = Msg2ActionEntry.get_msg_types()

##################  M S G S
ddir = '../data/ASU_DATA/'
fname = ddir + 'study-2_pilot-2_2021.02_NotHSRData_TrialMessages_Trial-T000315_Team-TM000021_Member-na_CondBtwn-1_CondWin-SaturnA_Vers-1.metadata'
msg_qs = MsgQCreator(fname, logger=logging)


all_loc_name = list(msg_qs.jsonParser.rooms.keys())
main_names = [nm[:nm.find('_')] for nm in all_loc_name if nm.find('_') >=0] 
main_names = set(main_names + [nm for nm in all_loc_name if nm.find('_') < 0] )
hallways = ['ccw', 'cce', 'mcw', 'mce', 'scw', 'sce', 'sccc']
room_names = main_names.difference(hallways)

derived_features = []
derived_features.append(CountAction('Event:dialogue_event', {}))  # same as CountPlayerDialogueEvents
derived_features.append(CountAction('Event:VictimPickedUp', {}))
derived_features.append(CountAction('Event:VictimPlaced', {}))
derived_features.append(CountAction('Event:ToolUsed', {}))
derived_features.append(CountAction('Event:Triage', {'triage_state':'SUCCESSFUL'}))
derived_features.append(CountAction('Event:RoleSelected', {})) # same as CountRoleChanges
derived_features.append(CountEnterExit(room_names))
derived_features.append(CountTriageInHallways(hallways))

msg_qs.startProcessing(derived_features, usable_msg_types)

