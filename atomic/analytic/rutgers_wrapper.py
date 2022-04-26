from atomic.analytic.acwrapper import ACWrapper
import json
import pandas as pd
import numpy as np


class BeliefDiffWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac/belief_diff': self.handle_msg}
        self.data = pd.DataFrame()

    def handle_msg(self, message, data):
        overall_pos = data['room_id'].index('overall')
        new_data = {'Timestamp': data['time_in_seconds']}
        for field, value in data.items():
            if isinstance(value, list) and field != 'room_id':
                new_data[field] = value[overall_pos]
        self.last = pd.DataFrame([new_data])
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data