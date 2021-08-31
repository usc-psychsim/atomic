import csv
import json
import logging
import os
import datetime

import pandas
from sklearn.linear_model import LinearRegression

"""
Subclass for adding feature counts to replay
"""
from atomic.parsing.count_features import Feature
from atomic.parsing.replayer import Replayer, replay_parser, parse_replay_args, filename_to_condition
from atomic.bin.cluster_features import _get_feature_values, _get_derived_features

class RecordScore(Feature):
    def __init__(self, logger=logging):
        super().__init__('record score', logger)
        self.team_score = 0

    def processMsg(self, msg):
        super().processMsg(msg)
        if msg['sub_type'] == 'Event:Scoreboard':
            self.team_score = msg['scoreboard']['TeamScore']
        self.addRow({'Team Score': self.team_score})
            
    def printValue(self):
        print(f'{self.name} {self.team_score}')

class FeatureReplayer(Replayer):
    def __init__(self, files=[], config=None, maps=None, rddl_file=None, action_file=None, aux_file=None, logger=logging, output=None):
        super().__init__(files=files, config=config, maps=maps, rddl_file=rddl_file, action_file=action_file, aux_file=aux_file, logger=logger)
        self.completed = []
        # Feature count bookkeeping
        self.feature_output = output
        self.feature_data = []
        self.fields = None
        self.condition_fields = None
        self.feature_fields = None
        self.prediction_models = {}

        # Look for evaluation files
        self.train = self.config.get('evaluation', 'train', fallback=None)
        self.training_trials = set()
        if self.train:
            with open(self.train, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    self.training_trials.add(row['Trial'].split('_')[-1])
            training_files = {filename_to_condition(f)['Trial']: f for f in self.files 
                if filename_to_condition(f)['Trial'] in self.training_trials}
            missing = sorted([trial for trial in self.training_trials if trial not in training_files])
            if missing:
                logger.warning(f'Unable to find files for training trials: {", ".join(missing)}')
                self.training_trials -= set(missing)
        self.test = self.config.get('evaluation', 'test', fallback=None)
        self.testing_trials = set()
        if self.test:
            with open(self.test, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    self.testing_trials.add(row['Trial'])
            testing_files = {filename_to_condition(f)['Trial']: f for f in self.files 
                if filename_to_condition(f)['Trial'] in self.testing_trials}
            missing = sorted([t for t in self.testing_trials if t not in testing_files])
            if missing:
                logger.warning(f'Unable to find files for testing trials: {", ".join(missing)}')
                self.testing_trials -= set(missing)
        if self.train or self.test:
            missing = sorted([f for f in self.files if f not in training_files.values() and f not in testing_files.values()])
            if missing:
                logger.warning(f'Skipping non-training, non-testing trials: {", ".join(missing)}')
            self.files = sorted(training_files.values()) + sorted(testing_files.values())
        self.models = {metric: {t: {'data': pandas.DataFrame()} for t in self.config.get('evaluation', f'{metric}_times', fallback='').split(',')} 
            for metric in self.config.get('evaluation', 'metrics', fallback=[]).split(',')}

    def pre_replay(self, config=None, logger=logging):
        self.derived_features = [RecordScore()]
        self.derived_features += _get_derived_features(self.parser)
        result = super().pre_replay(config, logger)
        # processes data to extract features depending on type of count
        for feature in self.derived_features:
            df = feature.dataframe
            df['seconds'] = df.apply(lambda row: row['time'][0]*60+row['time'][1], axis=1)
            for player, agent in self.parser.playerToAgent.items():
                df = df.rename(columns={col: col.replace(player, agent) for col in df.columns})
        for metric, models in self.models.items():
            for t in models:
                record = filename_to_condition(os.path.basename(os.path.splitext(self.file_name)[0]))
                if self.fields is None:
                    self.condition_fields = ['Trial'] + [field for field in record if field != 'Trial']
                    self.feature_fields = []
                for feature in self.derived_features:
                    if metric == 'm1' and isinstance(feature, RecordScore):
                        # Use final score for M1
                        values = {'Team Score': feature.team_score}
                    else:
                        frame = feature.dataframe
                        subset = frame[frame['time'] > (15-int(t), 0)]
                        row = subset[subset['seconds'] == subset['seconds'].min()]
                        values = row.to_dict('records')[-1]
                        record['time'] = min(values['time'], record.get('time', (15, 0)))
                        del values['time']
                        del values['seconds']
                    record.update(values)
                    if self.fields is None:
                        self.feature_fields += sorted(values.keys())
                if self.fields is None:
                    self.fields = self.condition_fields + ['time'] + self.feature_fields
                models[t]['data'] = models[t]['data'].append(record, ignore_index=True)
        if self.feature_output is not None:
            if os.path.splitext(self.feature_output)[1] == '.csv':
                with open(self.feature_output, 'w' if len(self.completed) == 0 else 'a') as csvfile:
                    first = len(self.completed) == 0
                    for metric, models in self.models.items():
                        for t, table in models.items():
                            table['data'].to_csv(csvfile, header=first)
                            first = False
            else:
                raise ValueError(f'Unable to output feature stats in {os.path.splitext(self.feature_output)[1][1:]} format.')
        return result

    def post_replay(self, logger=logging):
        super().post_replay(logger)
        trial = filename_to_condition(self.file_name)['Trial']
        self.completed.append(trial)
        if self.train and len(self.completed) == len(self.training_trials):
            # We have finished processing the training trials
            for metric, models in self.models.items():
                for t, table in models.items():
                    data = table['data'].fillna(0)
                    y_field = self.config.get('evaluation', f'{metric}_y')
                    X = data.filter(items=[field for field in self.feature_fields if field != y_field])
                    y = data.filter(items=[y_field])
                    table['regression'] = LinearRegression().fit(X, y)
        elif self.test and len(self.completed) > len(self.training_trials):
            # We have finished processing the testing data
            fname = f'{self.config.get("evaluation", "prediction_prefix", fallback="")}Trial-{self.completed[-1]}_'+\
                f'Vers-{self.config.get("evaluation", "version", fallback=1)}.metadata'
            messages = {}
            for metric, models in self.models.items():
                for t, table in models.items():
                    y_field = self.config.get('evaluation', f'{metric}_y')
                    row = table['data'][table['data']['Trial'] == trial]
                    X = row.filter(items=[field for field in self.feature_fields if field != y_field]).fillna(0)
                    prediction = table['regression'].predict(X)[0][0]
                    if metric == 'm1':
                        prediction = int(round(prediction))
                    msg_type = self.config.get('evaluation', f'{metric}_type', fallback='State')
                    if t not in messages:
                        messages[t] = {}
                    if msg_type not in messages[t]:
                        messages[t][msg_type] = self.make_prediction_header(msg_type, row['time'])
                    msg = messages[t][msg_type]
                    self.add_prediction_message(msg, row, prediction, metric)
            with open(fname, 'w') as prediction_file:
                for t, table in messages.items():
                    for msg in table.values():
                        print(msg)
                        print(json.dumps(msg), file=prediction_file)

    def make_prediction_header(self, msg_type, mission_time):
        base_msg = self.parser.jsonParser.jsonMsgs[0]
        message = {'header': {
                    'timestamp': datetime.datetime.now().isoformat(),
                    'message_type': 'agent',
                    'version': '0.1'
                    },
                    'predictions': []
                }
        message['msg'] = {
                        'trial_id': base_msg['msg']['trial_id'],
                        'timestamp': message['header']['timestamp'],
                        'sub_type': f'Prediction:{msg_type}',
                        'version': message['header']['version']
                        }
        message['data'] = {
            'created': message['header']['timestamp'],

        }
        return message

    def add_prediction_message(self, msg, row, value, metric):
        minutes, seconds = next(iter(row['time'].to_dict().values()))
        elapsed = (15-minutes)*60 - seconds
        elapsed *= 1000
        subject_type = self.config.get('evaluation', f'{metric}_subject')
        if subject_type == 'team':
            subject = next(iter(row['Team'].to_dict().values()))
        property = self.config.get('evaluation', f'{metric}_property')
        prediction = {
            'start_elapsed_time': elapsed,
            'subject_type': subject_type,
            'subject': subject,
            'predicted_property': f'{metric.upper()}:{property}',
            'prediction': value,
            }
        msg['predictions'].append(prediction)

if __name__ == '__main__':
    # Process command-line arguments
    parser = replay_parser()
    parser.add_argument('-o','--output', help='Name of file for storing feature stats')
    args = parse_replay_args(parser)
    replayer = FeatureReplayer(args['fname'], args['config'], rddl_file=args['rddl'], action_file=args['actions'], aux_file=args['aux'], logger=logging, output=args['output'])
    replayer.parameterized_replay(args)
