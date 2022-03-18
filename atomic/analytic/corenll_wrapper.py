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
        self.callsigns = ['green', 'red', 'blue']
        self.scores = ['avg_response_time', 'N_requests_open', 'compliance_ratio']
        self.data = [pd.DataFrame(columns=['millis'] + self.callsigns) for i in range(len(self.scores))]
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac/player_compliance': self.handle_msg}

        
    def handle_msg(self, message, data):
        for si, score in enumerate(self.scores):
            row = [self.elapsed_millis(message)] + [data.get(score+'_'+callsign, 0) for callsign in self.callsigns]
            self.data[si].loc[len(self.data[si])] = row
            