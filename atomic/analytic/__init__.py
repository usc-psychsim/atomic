"""
Base class for ASIST metrics, predictors, inferrers, and other bits that might analyze data online and spit out results onto the bus
"""
import logging

import pandas

from sklearn.linear_model import *
from sklearn.model_selection import *

class AnalyticComponent:

    VERSION = '0.3'
    TRAIN_TIMES = []
    TEST_TIMES = []

    def __init__(self, name, y_fields, team=True, ignore={}, y_type='State', logger=logging):
        self.name = name
        self.y_fields = y_fields
        self.data = {t: pandas.DataFrame() for t in set(self.TRAIN_TIMES)|set(self.TEST_TIMES)}
        self.team = team
        self.ignore = ignore
        self.regression = {}
        self.y_type = y_type
        self.X_fields = None
        self.logger = logger

    def add_data(self, data_list, subjects={}):
        for t in self.data:
            data_t = [data[data['time'] > (15-int(t), 0)] for data in data_list]
            self.data[t] = self.data[t].append(collapse_rows(data_t, subjects), ignore_index=True)

    def get_X(self, t, trial=None):
        data = self.data[t]
        if trial is not None:
            data = data[data['Trial'] == trial]
        if self.team:
            data = data[data['Participant'] == 'Team']
        else:
            data = data[data['Participant'] != 'Team']
        if trial is None:
            data = data.dropna(axis='columns', how='all')
        participants = data['Participant']
        # Drop columns that are all empty, drop non-numeric columns, drop y columns, fill any empty values with 0
        return data.select_dtypes(include='float64').drop(columns=self.y_fields, errors='ignore').fillna(0), participants

    def train(self, total_data, times=None):
        if self.team:
            data = total_data[total_data['Participant'] == 'Team']
        else:
            data = total_data[total_data['Participant'] != 'Team']
        y = data.filter(items=self.y_fields)
        y = y.values.ravel()
        if times is None:
            X_t = {t: self.get_X(t)[0] for t in self.TRAIN_TIMES}
        else:
            X_t = {t: self.get_X(t)[0] for t in times}
        self.X_fields = {t: X.columns for t, X in X_t.items()}
        self.regression = {t: self.build_model(X, y) for t, X in X_t.items()}

    def build_model(self, X, y):
        return LogisticRegression(solver='liblinear').fit(X, y)

    def output(self, model, X, participants):
        result = model.predict_proba(X)
        return {participants.iloc[row]: {model.classes_[col]: prob for col, prob in enumerate(dist)} 
            for row, dist in enumerate(result)}

    def test(self, trial, times=None):
        result = {}
        for t in self.TEST_TIMES if times is None else times:
            try:
                model = self.regression[t]
            except KeyError:
                if len(self.regression) == 1:
                    t, model = next(iter(self.regression.items()))
                else:
                    self.logger.warning(f'Unable to find unambiguous {self.name} model for time {t}')
                    continue
            X, participants = self.get_X(t, trial)
            result[t] = self.output(model, X[self.X_fields[t]], participants)
        return result

    def json_header(self, trial_id, analyses):
        message = {'header': {
                    'timestamp': f'{datetime.datetime.utcnow().isoformat()}Z',
                    'message_type': 'agent',
                    'version': self.VERSION
                    },
                }
        message['msg'] = {
                        'trial_id': trial_id,
                        'timestamp': message['header']['timestamp'],
                        'sub_type': f'Prediction:{self.y_type}',
                        'version': message['header']['version'],
                        'source': f'atomic:{message["header"]["version"]}',
                        }
        message['data'] = {
            'created': message['header']['timestamp'],
            'predictions': self.json_analyses(message, analyses)
        }
        return message

    def json_analyses(self, msg, analyses):
        for metric, analysis in analyses.items():
            for t, output in analysis.items():
                elapsed = 60*(15-t)
                elapsed *= 1000
                for participant, dist in output.items():
                    print(participant)
        return
        for prediction in predictions:
            if prediction['subject'] == 'team':
                subject_type = prediction['subject']
                subject = next(iter(row['Team'].to_dict().values()))
            else:
                subject_type = 'individual'
                subject = prediction['subject']
            property = self.config.get('evaluation', f'{metric}_property')
            prediction_msg = {
                'start_elapsed_time': elapsed,
                'subject_type': subject_type,
                'subject': subject,
                'predicted_property': f'{metric.upper()}:{property}',
                'prediction': prediction['value'],
                }
            if 'probability' in prediction:
                prediction_msg['probability_type'] = 'float'
                prediction_msg['probability'] = prediction['probability']
            msg['data']['predictions'].append(prediction_msg)
        return msg


        if y_type not in messages[t]:
            base_msg = parser.jsonParser.jsonMsgs[0]
            messages[t][y_type] = self.make_prediction_header(base_msg, y_type, data['time'])
        msg = messages[t][y_type]
        # Generate prediction
        prediction = table['regression'].predict(X)
        if metric == 'm1':
            predictions = [{'subject': self.config.get('evaluation', f'{metric}_subject'),
                'value': int(round(prediction[0][0]))}]
        elif metric == 'm3' or metric == 'm6':
            players = list(data['Participant'])
            predictions = []
            for idx, values in enumerate(prediction):
                if metric == 'm3':
                    dist = {y_fields[i]: values[i] for i in range(len(y_fields)) if values[i] > 0 and y_fields[i][:7] == map_name}
                elif metric == 'm6':
                    dist = {y_fields[i]: values[i] for i in range(len(y_fields)) if values[i] > 0}
                norm = sum(dist.values())
                for value, prob in dist.items():
                    if metric == 'm6':
                        value = value[len('Marker Legend '):]
                    predictions.append({'subject': parser.agentToPlayer[players[idx]] if metric == 'm3' else players[idx],
                        'value': value, 'probability': prob/norm})
        self.add_prediction_message(msg, data, predictions, metric)

    def __hash__(self):
        return hash(self.name)

def collapse_rows(data_list, subjects={}):
    """
    Flattens the mutually exclusive feature columns into a single row per participant (most recent values for each)
    """
    data = None
    suffix = '_y'
    for new_data in data_list:
        new_data = new_data.replace(subjects)
        if 'Participant' not in new_data.columns:
            new_data['Participant'] = 'Team'
        new_data = new_data.drop_duplicates(subset='Participant', keep='last')
        if data is None:
            data = new_data
        else:
            # Let's assume that values are the same for overlapping columns
            data = data.merge(new_data, how='outer', on='Participant', suffixes=(None, suffix))
            data = data.drop(columns=[col for col in data.columns if col[-len(suffix):] == suffix])
    return data.drop_duplicates()

