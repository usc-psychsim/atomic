#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 23 15:29:17 2021

@author: mostafh
"""
import pickle
from atomic.parsing.json_parser import JSONReader
import os

''' Note that if USE_COLLAPSED = True, the room names in this pickle will reflect the new collapsed names
'''

USE_COLLAPSED = True

log_name = 'study-2_pilot-2_2021.02_HSRData_TrialMessages_Trial-T000423_Team-TM000112_Member-na_CondBtwn-2_CondWin-SaturnB_Vers-1.metadata'
fname = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ASU_DATA', log_name)


jsonParser = JSONReader(fname, use_collapsed_map=USE_COLLAPSED)
vList = jsonParser.get_victims()


victim_pickle = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'rddl_psim', 'victims.pickle')
with open(victim_pickle, 'wb') as f:
    pickle.dump(vList, f)