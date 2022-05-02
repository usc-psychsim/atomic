from atomic.analytic.acwrapper import ACWrapper
import json
import pandas as pd
import numpy as np


class PlayerProfileWrapper(ACWrapper):
    def __init__(self, agent_name, **kwargs):
        super().__init__(agent_name, **kwargs)
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac_ucf_ta2_playerprofiler/playerprofile': self.handle_msg}
        self.data = pd.DataFrame()

    def handle_msg(self, message, data, mission_time):
        new_data = {'Player': data["callsign"]}
        new_data['team-potential-category'] = data['team-potential-category'] == 'HighTeam'
        new_data['task-potential-category'] = data['task-potential-category'] == 'HighTask'
        self.last = pd.DataFrame([new_data])
        self.last['Timestamp'] = mission_time
        self.last['Trial'] = self.trial
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return [new_data]