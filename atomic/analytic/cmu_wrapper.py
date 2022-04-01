#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 15 13:32:51 2022

@author: mostafh
"""

from atomic.analytic.acwrapper import ACWrapper
import pandas as pd
import numpy as np


class TEDWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
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
            'agent/ac/cmuta2-ted-ac/ted': self.handle_msg}
        
        self.data = pd.DataFrame(columns=['millis'] + self.score_names)

        
    def handle_msg(self, message, data):
        elapsed = [self.elapsed_millis(message)]
        row = [data.get(score, 0) for score in self.score_names]
        self.data.loc[len(self.data)] = elapsed + row
            
            
                    