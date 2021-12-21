import os.path
from atomic.parsing.parse_into_msg_qs import MsgQCreator

ddir = os.path.join(os.path.dirname(__file__), '..', 'data', 'ASU_DATA')
jsonFile = 'study-3_spiral-2_pilot_NotHSRData_TrialMessages_Trial-T000411_Team-TM000061_Member-na_CondBtwn-ASI-none_CondWin-na_Vers-2.metadata'
metadata_file = os.path.join(ddir, jsonFile)
    
msg_qs = MsgQCreator(metadata_file)
msg_qs.startProcessing_simple()
