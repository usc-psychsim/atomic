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
    def __init__(self, agent_name, world=None, **kwargs):
        super().__init__(agent_name, world, **kwargs)
        self.score_names = ['avg_response_time', 'N_requests_open', 'compliance_ratio']
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac/player_compliance': self.handle_compliance_msg,
            'agent/ac/goal_alignment': self.handle_alignment_msg}
        self.data = pd.DataFrame()

    def handle_compliance_msg(self, message, data, mission_time):
        # Load in the latest compliance numbers
        new_data = []
        for player1, table in data.items():
            if player1 != 'elapsed_ms':
                records = {}
                for field, subtable in table.items():
                    for player2, value in subtable.items():
                        player2 = player2.split('_')[0]
                        if player2 not in records:
                            records[player2] = {'Requestor': player1, 'Requestee': player2}
                        records[player2][field] = value
                new_data += list(records.values())
        new_frame = pd.DataFrame(new_data)
        # Identify any changes
        if len(self.data) > 0:
            for i, record in new_frame.iterrows():
                previous = self.data[(self.data['Requestor'] == record['Requestor']) & (self.data['Requestee'] == record['Requestee'])]
        self.last = new_frame
        self.last['Timestamp'] = mission_time
        self.last['Trial'] = self.trial
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data

    def handle_alignment_msg(self, message, data, mission_time):
        new_data = []
        for player1, table in data.items():
            if player1 == 'Team':
                new_data.append(table)
                new_data[-1]['Requestor'] = player1
                new_data[-1]['goal_alignment_current'] = 1 if table['goal_alignment_current'] else 0
            elif player1 != 'elapsed_ms':
                for player2 in table['goal_alignment_current']:
                    record = {'Requestor': player1, 'Requestee': player2,
                              'current_goal': table['current_goal']}
                    record.update({field: value[player2] for field, value in table.items() if field != 'current_goal'})
                    record['goal_alignment_current'] = 1 if record['goal_alignment_current'] else 0
                    new_data.append(record)
        self.last = pd.DataFrame(new_data)
        self.last['Timestamp'] = mission_time
        self.last['Trial'] = self.trial
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data            