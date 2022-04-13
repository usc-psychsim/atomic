"""
Base class for ASIST metrics, predictors, inferrers, and other bits that might analyze data online and spit out results onto the bus
"""
import datetime
import logging
import re

import pandas

#from sklearn.linear_model import *
#
#REGEX_TEAM = 'TM\\d{6}'
#REGEX_INDIVIDUAL = 'E\\d{6}'
#
#class AnalyticComponent:
#
#    VERSION = '0.3'
#    TRAIN_TIMES = []
#    TEST_TIMES = []
#
#    def __init__(self, name, y_fields, team=True, ignore={}, y_type='State', logger=logging):
#        self.name = name
#        self.y_fields = y_fields
#        self.data = {t: pandas.DataFrame() for t in set(self.TRAIN_TIMES)|set(self.TEST_TIMES)}
#        self.team = team
#        self.ignore = ignore
#        self.regression = {}
#        self.y_type = y_type
#        self.X_fields = None
#        self.logger = logger
#
#    def add_data(self, data_list, subjects={}):
#        for t in self.data:
#            data_t = [data[data['time'] > (15-int(t), 0)] for data in data_list]
#            self.data[t] = self.data[t].append(collapse_rows(data_t, subjects), ignore_index=True)
#
#    def get_X(self, t, trial=None):
#        data = self.data[t]
#        if trial is not None:
#            data = data[data['Trial'] == trial]
#        data = filter_team(data, self.team)
#        if trial is None:
#            data = data.dropna(axis='columns', how='all')
#        participants = data['Participant']
#        # Drop columns that are all empty, drop non-numeric columns, drop y columns, fill any empty values with 0
#        return data.select_dtypes(include='float64').drop(columns=self.y_fields, errors='ignore').fillna(0), participants
#
#    def train(self, total_data, times=None):
#        data = filter_team(total_data, self.team)
#        y = data.filter(items=self.y_fields)
#        y = y.values.ravel()
#        if times is None:
#            X_t = {t: self.get_X(t)[0] for t in self.TRAIN_TIMES}
#        else:
#            X_t = {t: self.get_X(t)[0] for t in times}
#        self.X_fields = {t: X.columns for t, X in X_t.items()}
#        self.regression = {t: self.build_model(X, y) for t, X in X_t.items()}
#
#    def build_model(self, X, y):
#        return LogisticRegression(solver='liblinear').fit(X, y)
#
#    def output(self, model, X, participants):
#        result = model.predict_proba(X)
#        return {participants.iloc[row]: {model.classes_[col]: prob for col, prob in enumerate(dist)} 
#            for row, dist in enumerate(result)}
#
#    def test(self, trial, times=None):
#        result = {}
#        for t in self.TEST_TIMES if times is None else times:
#            try:
#                model = self.regression[t]
#                model_t = t
#            except KeyError:
#                if len(self.regression) == 1:
#                    model_t, model = next(iter(self.regression.items()))
#                else:
#                    self.logger.warning(f'Unable to find unambiguous {self.name} model for time {t}')
#                    continue
#            X, participants = self.get_X(t, trial)
#            result[t] = self.output(model, X[self.X_fields[model_t]], participants)
#        return result
#
#    def __hash__(self):
#        return hash(self.name)
#
#def collapse_rows(data_list, subjects={}):
#    """
#    Flattens the mutually exclusive feature columns into a single row per participant (most recent values for each)
#    """
#    data = None
#    suffix = '_y'
#    for new_data in data_list:
#        new_data = new_data.replace(subjects)
#        if 'Participant' not in new_data.columns:
#            new_data['Participant'] = subjects['Team']
#        new_data = new_data.drop_duplicates(subset='Participant', keep='last')
#        if data is None:
#            data = new_data
#        else:
#            # Let's assume that values are the same for overlapping columns
#            data = data.merge(new_data, how='outer', on='Participant', suffixes=(None, suffix))
#            data = data.drop(columns=[col for col in data.columns if col[-len(suffix):] == suffix])
#    return data.drop_duplicates()
#
#def filter_team(data, team=True):
#    """
#    :param team: if True, return all team rows; otherwise, return all individual rows (default is True)
#    :type team: bool
#    """
#    if team:
#        return data[data['Participant'].str.match(REGEX_TEAM)]
#    else:
#        return data[data['Participant'].str.match(REGEX_INDIVIDUAL)]
#
#
#def analysis_to_json(analyses, y_type, trial_id):
#    message = {'header': {
#                'timestamp': f'{datetime.datetime.utcnow().isoformat()}Z',
#                'message_type': 'agent',
#                'version': AnalyticComponent.VERSION
#                },
#            }
#    message['msg'] = {
#                    'trial_id': trial_id,
#                    'timestamp': message['header']['timestamp'],
#                    'sub_type': f'Prediction:{y_type}',
#                    'version': message['header']['version'],
#                    'source': f'atomic:{message["header"]["version"]}',
#                    }
#    message['data'] = {
#        'created': message['header']['timestamp'],
#        'predictions': []
#    }
#    for metric, analysis in analyses.items():
#        for t, output in analysis.items():
#            elapsed = 60*(15-t)
#            elapsed *= 1000
#            print(metric.name, t, elapsed)
#            for participant, dist in sorted(output.items()):
#                if isinstance(dist, dict):
#                    for value, prob in sorted(dist.items()):
#                        message['data']['predictions'].append(json_prediction(elapsed, participant, metric, value, prob))
#                else:
#                    message['data']['predictions'].append(json_prediction(elapsed, participant, metric, dist))
#    return message
#
#def json_prediction(elapsed, participant, metric, value, prob=None):
#    msg = {
#        'start_elapsed_time': elapsed,
#        'subject_type': 'individual' if re.match(REGEX_TEAM, participant) is None else 'team',
#        'subject': participant,
#        'predicted_property': f'{metric.name.upper()}:{metric.PROPERTY}',
#        'prediction': value,
#        }
#    if prob is not None:
#        msg['probability_type'] = 'float'
#        msg['probability'] = prob
#    return msg
