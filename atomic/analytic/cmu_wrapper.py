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


class TEDWrapper(ACWrapper):
    def __init__(self, agent_name, world=None, **kwargs):
        super().__init__(agent_name, world, **kwargs)
        self.score_names = [
            "process_coverage",
            "process_coverage_agg",
            "inaction_stand_s",
            "action_triage_s",
            "triage_count",
            "action_dig_rubble_s",
            "dig_rubble_count",
            "action_move_victim_s",
            "move_victim_count",
            "action_explore_s",
            "explore_count",
            "process_triaging_agg",
            "team_score",
            "team_score_agg",
            "comms_total_words",
            "comms_equity",
            "process_skill_use_s",
            "process_effort_s",
            "process_skill_use_rel",
            "process_workload_burnt",
            "process_skill_use_agg",
            "process_effort_agg",
            "process_workload_burnt_agg"]
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac/ac_cmu_ta2_ted/ted': self.handle_msg}
        
        self.data = pd.DataFrame()
        # self.data = pd.DataFrame(columns=['millis'] + self.score_names)

    def handle_msg(self, message, data, mission_time):
        new_data = [self.world.make_record(data)]
        self.last = pd.DataFrame(new_data)
        self.last['Timestamp'] = mission_time
        self.last['Trial'] = self.trial
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        # elapsed = [self.elapsed_millis(message)]
        # row = [data.get(score, 0) for score in self.score_names]
        # self.data.loc[len(self.data)] = elapsed + row
        # return row
        return new_data


class BEARDWrapper(ACWrapper):
    def __init__(self, agent_name, world=None, **kwargs):
        super().__init__(agent_name, world, **kwargs)
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac/ac_cmu_ta2_beard/beard': self.handle_msg}
        
        self.data = pd.DataFrame()

    def handle_msg(self, message, data, mission_time):
        new_data = []
        for player, table in data.items():
            if player != 'team':
                new_data.append(self.world.make_record(table))
                new_data[-1]['Player'] = player.split('_')[0].capitalize()
                if new_data[-1]['Player'] not in self.world.agents:
                    print(f'Invalid player {new_data[-1]["Player"]} in BEARD message in Trial {self.trial}')
                    new_data[-1]['Player'] = self.world.participant2player[new_data[-1]['Player']]['callsign']
        self.last = pd.DataFrame(new_data)
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data        
