from atomic.analytic.acwrapper import ACWrapper
import json
import pandas as pd
import numpy as np


class PlayerProfileWrapper(ACWrapper):
    def __init__(self, team_name, ac_name):
        super().__init__(team_name, ac_name)
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac_ucf_ta2_playerprofiler/playerprofile': self.handle_msg}
        self.data = pd.DataFrame()

    def handle_msg(self, message, data):
        new_data = {'Player': f'{data["callsign"].upper()}_ASIST2'}
        new_data['team-potential-category'] = 1 if data['team-potential-category'] == 'HighTeam' else 0
        new_data['task-potential-category'] = 1 if data['task-potential-category'] == 'HighTask' else 0
        self.last = pd.DataFrame([new_data])
        self.last['Timestamp'] = message['timestamp']
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data