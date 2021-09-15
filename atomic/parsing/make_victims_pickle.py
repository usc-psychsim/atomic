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

names = ['study-2_2021.06_HSRData_TrialMessages_Trial-T000421_Team-TM000111_Member-na_CondBtwn-2_CondWin-SaturnA_Vers-6.metadata',
'study-2_2021.06_HSRData_TrialMessages_Trial-T000401_Team-TM000101_Member-na_CondBtwn-2_CondWin-SaturnB_Vers-6.metadata']


for i, tag in enumerate(['A', 'B']):
    fname = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ASU_DATA', names[i])
    jsonParser = JSONReader(fname, use_collapsed_map=USE_COLLAPSED)
    vList = jsonParser.get_victims()
    victim_pickle = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'rddl_psim', 'victims'+tag+'.pickle')
    with open(victim_pickle, 'wb') as f:
        pickle.dump(vList, f)