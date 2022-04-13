import os.path
import json
from atomic.analytic.ihmc_wrapper import JAGWrapper
from atomic.analytic.gallup_wrapper import GelpWrapper
from atomic.analytic.corenll_wrapper import ComplianceWrapper
from atomic.analytic.cmu_wrapper import TEDWrapper

ddir = os.path.join(os.path.dirname(__file__), '..', 'data', 'ASU_DATA')


## IHMC only
jsonFile = 'NotHSRData_TrialMessages_Trial-T000479_Team-TM000089_Member-na_CondBtwn-CMU-TA1_CondWin-na_Vers-1--jai-augmented-20220405.metadata'

#jsonFile = 'gelp_metadata/GELP_study-3_spiral-3_pilot_NotHSRData_TrialMessages_Trial-T000451_Team-TM000075_Member-na_CondBtwn-ASI-CMU-CRA_CondWin-na_Vers-4.metadata'


## Cornell and IHMC. IHMC messages are outdated and useless.
#jsonFile = 'Cornell_AC_republish_NotHSRData_TrialMessages_Trial-T000486_Team-TM000093_Member-na_CondBtwn-none_CondWin-na_Vers-1.metadata'

metadata_file = os.path.join(ddir, jsonFile)
    
ac_filters = {
        'ihmc':{'observations/events/player/jag', 'observations/events/mission',
        'observations/events/player/role_selected'}, 
        'cornell':{'agent/ac/player_compliance'},
        'cmu_ted':{'agent/ac/cmuta2-ted-ac/ted'},
        'gallup':{'agent/gelp'}
                   }
ac_wrappers = {
        'ihmc':JAGWrapper('ihmc', 'jag'),
        'cornell': ComplianceWrapper('cornell', 'compliance'),
        'cmu_ted': TEDWrapper('cmu', 'ted'), 
        'gallup': GelpWrapper('gallup', 'gelp')
                    }

jsonfile = open(metadata_file, 'rt')

## Read one line at a time to handle mal-formed lines
jsonMsgs = []
ctr = 0
line = jsonfile.readline()
jsonMsgs.append(json.loads(line))
while line:
    try:
        line = jsonfile.readline()
        jsonMsgs.append(json.loads(line))
        ctr = ctr+1
    except Exception:
        print('**************', line, '**************')
        
#jsonMsgs = [json.loads(line) for line in jsonfile.readlines() ] 
jsonfile.close()        

for ji, jmsg in enumerate(jsonMsgs):
    msg_topic = jmsg.get('topic', '')
    for ac_name, topics in ac_filters.items():
        if (msg_topic == 'trial') or (msg_topic in topics):
            ac_wrappers[ac_name].handle_message(msg_topic, jmsg['msg'], jmsg['data'])

#    if 'ihmc' in ac_wrappers and len(ac_wrappers['ihmc'].messages) > 1800:
#        break

msgs_per_ac = {k:len(ac_wrappers[k].messages) for k in ac_wrappers.keys()}
print('messages per AC', msgs_per_ac)