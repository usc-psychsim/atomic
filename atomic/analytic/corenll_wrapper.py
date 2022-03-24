#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 15 13:32:51 2022

@author: mostafh
"""

from atomic.analytic.acwrapper import ACWrapper
import pandas as pd
import numpy as np


class ComplianceWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
        self.score_names = ['avg_response_time', 'N_requests_open', 'compliance_ratio']
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac/player_compliance': self.handle_msg}
        self.make_dfs()

        
    def handle_msg(self, message, data):
        elapsed = [self.elapsed_millis(message)]
        for si, score in enumerate(self.score_names):
            row = elapsed + [data.get(score+'_'+callsign, 0) for callsign in self.callsigns]
            self.data[si].loc[len(self.data[si])] = row
            
        if (len(self.messages) % 10) == 1:
            print(self.compare(10))
            
    ''' Compare players over the last history_sec seconds
        For each score, return a list of [min, max] of the players that fall well below/above 
        the others on this score.
    '''
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
                    