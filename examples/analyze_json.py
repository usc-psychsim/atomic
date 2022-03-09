import os.path
from atomic.parsing.parse_into_msg_qs import MsgQCreator

ddir = os.path.join(os.path.dirname(__file__), '..', 'data', 'ASU_DATA')
jsonFile = 'GELP_study-3_spiral-3_pilot_NotHSRData_TrialMessages_Trial-T000451_Team-TM000075_Member-na_CondBtwn-ASI-CMU-CRA_CondWin-na_Vers-4.metadata'
metadata_file = os.path.join(ddir, jsonFile)
    
msg_qs = MsgQCreator(metadata_file)
msg_qs.startProcessing_simple()
msg_qs.jsonParser.stats()