from atomic.analytic.acwrapper import ACWrapper
import json
import pandas as pd
import numpy as np


class BeliefDiffWrapper(ACWrapper):
    def __init__(self, agent_name, **kwargs):
        super().__init__(agent_name, **kwargs)
        self.topic_handlers = {
            'trial': self.handle_trial,
            'agent/ac/belief_diff': self.handle_msg,
            'agent/ac/threat_room_communication': self.ignore_msg,
            'agent/ac/victim_type_communication': self.ignore_msg,
            'agent/ac/threat_room_coordination': self.handle_threat}
        self.data = pd.DataFrame()

    def handle_msg(self, message, data, mission_time):
        overall_pos = data['room_id'].index('overall')
        new_data = {'Timestamp': mission_time}
        for field, value in data.items():
            if isinstance(value, list) and field != 'room_id':
                new_data[field] = value[overall_pos]
        self.last = pd.DataFrame([new_data])
        self.last['Trial'] = self.trial
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return [new_data]

    def handle_threat(self, message, data, mission_time):
        new_data = [{'Player': player, 'Timestamp': mission_time,
                     'wait_time': data['wait_time'][i]}
                    for i, player in enumerate(data['threat_activation_player'])]
        self.last = pd.DataFrame(new_data)
        self.last['Trial'] = self.trial
        self.data = pd.concat([self.data, self.last], ignore_index=True)
        return new_data
