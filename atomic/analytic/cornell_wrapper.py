#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 15 13:32:51 2022

@author: mostafh
"""

from atomic.analytic.acwrapper import ACWrapper
import json
import pandas as pd
import numpy as np


class ComplianceWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
        self.score_names = ['avg_response_time', 'N_requests_open', 'compliance_ratio']
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac/player_compliance': self.handle_msg}
        self.data = pd.DataFrame()

    def handle_msg(self, message, data):
        new_data = []
        for player1, table in data.items():
            if player1 != 'elapsed_ms':
                records = {}
                for field, subtable in table.items():
                    for player2, value in subtable.items():
                        player2 = player2.split('_')[0]
                        if player2 not in records:
                            records[player2] = {'Requestor': f'{player1.upper()}_ASIST2', 'Requestee': f'{player2.upper()}_ASIST2'}
                        records[player2][field] = value
                new_data += list(records.values())
        self.last = pd.DataFrame(new_data)
        self.last['Timestamp'] = message['timestamp']
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        # elapsed = [self.elapsed_millis(message)]
        ######### This needs an overhaul to work with pairwise compliance
        # 
        # for si, score in enumerate(self.score_names):
        #    row = elapsed + [data.get(score+'_'+callsign, 0) for callsign in self.callsigns]
        #    self.data[si].loc[len(self.data[si])] = row
        return new_data
            