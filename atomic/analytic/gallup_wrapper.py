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
        comp_results = {r['callsign']:r['gelp_components'] for r in data['gelp_results']}
        for gcomponent in range(len(self.score_names)-1):
            row = [comp_results.get(callsign, np.zeros(self.n_scores()))[gcomponent] for callsign in self.callsigns]
            self.data[gcomponent].loc[len(self.data[gcomponent])] = [self.elapsed_millis(message)] + row
            
        
        overall_results = {r['callsign']:r['gelp_overall'] for r in data['gelp_results']}
        self.data[-1].loc[len(self.data[-1])] = [self.elapsed_millis(message)] + \
                                        [overall_results.get(callsign, 0) for callsign in self.callsigns]
                                        
        
        if (len(self.messages) % 10) == 1:
            print(self.compare(10))
    
    def compare(self, history_sec):
        start_ms = self.elapsed_millis(self.messages[-1][0]) - history_sec*1000
        extremes = {score:['', ''] for score in self.score_names}
        for si, score in enumerate(self.score_names):
            df = self.data[si]
            relevant_df = df.loc[df['millis'] >= start_ms, :]
            means = relevant_df.mean()
            stds = relevant_df.std()
            for callsign in self.callsigns:
                thiscall_ub = means[callsign] + stds[callsign]
                thiscall_lb = means[callsign] - stds[callsign]
                if np.all([thiscall_ub <= means[other]-stds[other] for other in self.callsigns]):
                    extremes[score][0] = callsign
                if np.all([thiscall_lb >= means[other]+stds[other] for other in self.callsigns]):
                    extremes[score][1] = callsign
                    
        return extremes
                    