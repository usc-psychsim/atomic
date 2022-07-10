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
                            records[player2] = self.world.make_record({'Requestor': player1, 'Requestee': player2})
                        records[player2][field] = value
                new_data += list(records.values())
        new_frame = pd.DataFrame(new_data)
        # Identify any changes
        if len(self.data) > 0:
            changes = {}
            for i, record in new_frame.iterrows():
                previous = self.data[(self.data['Requestor'] == record['Requestor']) & (self.data['Requestee'] == record['Requestee'])]
                for key, new_value in record.items():
                    if record['Requestor'] != record['Requestee']:
                        old_value = previous.get(key)
                        if old_value is not None:
                            old_value = old_value.dropna()
                        else:
                            continue
                        if 'time' not in key and len(old_value) > 0:
                            old_value = old_value.iloc[-1]
                            if old_value != new_value:
                                pair = (record['Requestor'], record['Requestee'])
                                changes[pair] = changes.get(pair, []) + [(key, old_value < new_value)]
            if changes and self.world.config.getboolean('output', 'ac', fallback=False):
                for pair, delta in changes.items():
                    for field, direction in delta:
                        elements = field.split('_')
                        if elements[:3] == ['N', 'open', 'requests']:
                            if direction:
                                record = self.world.make_record({'actor': pair[0], 'message': f'Requests {elements[-1]} of {pair[1]}'})
                                self.world.log_data = pd.concat([self.world.log_data, pd.DataFrame.from_records([record])], ignore_index=True)
                            else:
                                record = self.world.make_record({'actor': pair[1], 'message': f'Satisfies {elements[-1]} request of {pair[0]}'})
                                self.world.log_data = pd.concat([self.world.log_data, pd.DataFrame.from_records([record])], ignore_index=True)
        self.last = new_frame
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data

    def compute_state_delta(self, data):
        state_delta = super().compute_state_delta(data)
        if data:
            for record in data:
                if record['Requestor'] != record.get('Requestee', None):
                    if 'goal_alignment_overall' in record:
                        pass
                    elif 'N_open_requests_triage' in record:
                        for var in self.variables:
                            total = 0
                            for key, value in record.items():
                                if var in key:
                                    total += value
                            key = self.get_pair_variable(record['Requestor'], record['Requestee'], var)
                            state_delta[key] = total
        return state_delta

    def handle_alignment_msg(self, message, data, mission_time):
        new_data = []
        for player1, table in data.items():
            if player1 == 'Team':
                new_data.append(table)
                new_data[-1]['Requestor'] = player1
                new_data[-1]['goal_alignment_current'] = 1 if table['goal_alignment_current'] else 0
            elif player1 != 'elapsed_ms':
                for player2 in table['goal_alignment_current']:
                    record = self.world.make_record({'Requestor': player1, 'Requestee': player2,
                                                     'current_goal': table['current_goal']})
                    record.update({field: value[player2] for field, value in table.items() if field != 'current_goal'})
                    record['goal_alignment_current'] = 1 if record['goal_alignment_current'] else 0
                    new_data.append(record)
        self.last = pd.DataFrame(new_data)
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data            