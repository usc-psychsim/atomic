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
        
        ######### This needs an overhaul to work with pairwise compliance
        
        for si, score in enumerate(self.score_names):
            row = elapsed + [data.get(score+'_'+callsign, 0) for callsign in self.callsigns]
            self.data[si].loc[len(self.data[si])] = row
            