#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 15 13:32:51 2022

@author: mostafh
"""

from .acwrapper import ACWrapper
import pandas as pd
import numpy as np


class GelpWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
        self.score_names = ['Ideas', 'Focus', 'Coordinate', 'Monitor', 'Share', 'Plan', 'Agree', 'Help', 'Leadership'] 
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/gelp': self.handle_msg}

        self.make_dfs()
        
    def handle_msg(self, message, data):
        if message['timestamp'] is None:
            return
        elapsed = [self.elapsed_millis(message)]
        comp_results = {r['callsign']:r['gelp_components'] for r in data['gelp_results']}
        for gcomponent in range(len(self.score_names)-1):
            row = [comp_results.get(callsign, np.zeros(self.n_scores()))[gcomponent] for callsign in self.callsigns]
            self.data[gcomponent].loc[len(self.data[gcomponent])] = elapsed + row
            
        
        overall_results = {r['callsign']:r['gelp_overall'] for r in data['gelp_results']}
        self.data[-1].loc[len(self.data[-1])] = [self.elapsed_millis(message)] + \
                                        [overall_results.get(callsign, 0) for callsign in self.callsigns]
                                        
        
        print(len(self.messages))
        if (len(self.messages) % 10) == 1:
            print(self.name, self.compare(10))
    
    '''
“Overall” leadership score: mean = 6.1, SD = 1.6. 
Attribute leadership scores: 
IDEAS: mean = 4.0, SD = 1.6. 
FOCUS: mean = 4.2, SD = 1.3. 
COORDINATE: mean = 4.6, SD = 1.1. 
MONITOR: mean = 3.9, SD = 1.4. 
SHARE: mean = 4.3, SD = 1.3. 
PLAN: mean = 4.1, SD = 1.3. 
AGREE: mean = 4.6, SD = 1.2. 
HELP: mean = 4.8, SD = 1.2.
'''
                    