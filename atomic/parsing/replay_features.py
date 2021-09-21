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
from atomic.parsing.count_features import *
from atomic.parsing.replayer import Replayer, replay_parser, parse_replay_args, filename_to_condition
from atomic.bin.cluster_features import _get_feature_values, _get_derived_features

class Metric:
    def __init__(self, name, times=None):
        self.name = name
        if times is None:
            self.times = []
        else:
            self.times = times
        self.data = {t: pandas.DataFrame() for t in self.times}

    def add_data(self, data):
        for t in self.times:
            data = data[data['time'] > (15-int(t), 0)]
            if len(data) > 0:
                data = data[data['time'] == min(data['time'])]
                self.data[t] = self.data[t].append(data, ignore_index=True)

class RecordScore(Feature):
    def __init__(self, logger=logging):
        super().__init__('record score', logger)
        self.score = {}

    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if msg['sub_type'] == 'Event:Scoreboard':
            self.score.update({field if 'Score' in field else f'Score for {field}': value for field, value in msg['scoreboard'].items()})
            add_flag = True

        if add_flag:
            for field, value in self.score.items():
                if field[:10] == 'Score for ':
                    row = {'Participant': field[10:], 'Individual Score': value, 'Team Score': self.score['TeamScore']}
                else:
                    row = {'Participant': 'Team', 'Team Score': value}
                self.addRow(row)
            
    def printValue(self):
        print(f'{self.name} {self.score}')

class MarkerPlacement(Feature):
    def __init__(self, logger=logging):
        super().__init__('count marker placement per player per room', logger)
        self.marker_count = {}
        self.marker_legend = {}

    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_type == 'Event:MarkerPlaced':
            player = msg['participant_id']
            if player not in self.marker_count:
                self.marker_count[player] = {f'Marker Block {i+1}': {'regular': 0, 'critical': 0, 'none': 0} for i in range(3)}
            if msg['mark_critical'] > 0:
                self.marker_count[player][msg['marker_type']]['critical'] += 1
            elif msg['mark_regular'] > 0:
                self.marker_count[player][msg['marker_type']]['regular'] += 1
            else:
                self.marker_count[player][msg['marker_type']]['none'] += 1
            if 'marker_legend' in msg:
                self.marker_legend[player] = msg['marker_legend']
            add_flag = True

        if add_flag:
            for player, markers in self.marker_count.items():
                row = {'Participant': player}
                if player in self.marker_legend:
                    row[f'Marker Legend'] =  self.marker_legend[player]
                for marker, table in markers.items():
                    norm = sum(table.values())
                    if norm > 0:
                        norm_count = {f'{marker}_{victim}': count/norm for victim, count in table.items()}
                        row.update(norm_count)
                        row[marker] = norm
    #                    print(f'{player} {self.marker_legend[player]}: {norm_count}')
                self.addRow(row)

    def printValue(self):
        print(f'{self.name} {self.marker_count}')


class DialogueLabels(Feature):
    def __init__(self, logger=logging):
        super().__init__('count utterances per player per label', logger)
        self.utterances = {}

    def processMsg(self, msg):
        super().processMsg(msg)
        add_flag = not self.COMPACT_DATA
        if self.msg_type == 'asr:transcription':
            player = msg['participant_id']
            if player not in self.utterances:
                self.utterances[player] = {}
            for label in msg['extractions']:
                field = f'Utterance {label["label"]}'
                self.utterances[player][field] = self.utterances[player].get(field, 0) + 1
                add_flag = True
        if add_flag:
            for player, utterances in self.utterances.items():
                row = {'Participant': player, 'Utterance Total': sum(self.utterances[player].values())}
                row.update(utterances)
                if len(self.dataframe) > 0:
                    self.dataframe = self.dataframe[self.dataframe['Participant'] != player]
                self.addRow(row)

    def printValue(self):
        print(f'{self.name} {self.utterances}')

class FeatureReplayer(Replayer):
    def __init__(self, files=[], config=None, maps=None, rddl_file=None, action_file=None, aux_file=None, logger=logging, output=None):
        super().__init__(files=files, config=config, maps=maps, rddl_file=rddl_file, action_file=action_file, aux_file=aux_file, logger=logger)
        self.completed = []
        # Feature count bookkeeping
        self.feature_output = output
        self.feature_data = pandas.DataFrame()
        self.fields = None
        self.prediction_models = {}

        self.training_trials = set()
        self.testing_trials = set()
        if self.config:
            # Look for evaluation files
            self.train = self.config.get('evaluation', 'train', fallback=None)
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
            self.metrics = {Metric(metric, [t for t in self.config.get('evaluation', f'{metric}_train', fallback='15').split(',')])
                for metric in self.config.get('evaluation', 'metrics', fallback=[]).split(',')}
        else:
            self.metrics = {}

    def pre_replay(self, config=None, logger=logging):
        self.derived_features = [RecordScore(logger)]
        self.derived_features += _get_derived_features(self.parser)
        self.derived_features.append(PlayerRoomPercentage(mission_length=15, logger=logger))
        self.derived_features.append(MarkerPlacement(logger))
        self.derived_features.append(DialogueLabels(logger))
        result = super().pre_replay(config, logger)
        trial_fields = filename_to_condition(os.path.basename(os.path.splitext(self.file_name)[0]))
        if self.fields is None:
            self.fields = list(trial_fields.keys())
            self.fields.append('Participant')
            self.fields.append('time')
            self.fields.append('Team Score')
            self.fields.append('Individual Score')
        # processes data to extract features depending on type of count
        for feature in self.derived_features:
            for field, value in trial_fields.items():
                feature.dataframe[field] = value
            for metric in self.metrics:
                metric.add_data(feature.dataframe)
        if self.feature_output is not None:
            data = None
            suffix = '_y'
            for feature in self.derived_features:
#                new_data = feature.dataframe[feature.dataframe['time'] == feature.dataframe['time'].min()]
                new_data = feature.dataframe.replace(self.parser.jsonParser.subjects)
                if 'Participant' not in new_data.columns:
                    new_data['Participant'] = 'Team'
                new_data = new_data.drop_duplicates(subset='Participant', keep='last')
                if data is None:
                    data = new_data
                else:
                    data = data.merge(new_data, how='outer', on='Participant', suffixes=(None, suffix))
                    data = data.drop(columns=[col for col in data.columns if col[-2:] == suffix])
            self.feature_data = self.feature_data.append(data.drop_duplicates(), ignore_index=True)
        return result

    def post_replay(self, logger=logging):
        super().post_replay(logger)
        trial = filename_to_condition(self.file_name)['Trial']
        map_name = filename_to_condition(self.file_name)['CondWin']
        self.completed.append(trial)
        if trial in self.training_trials and len(self.completed) == len(self.training_trials):
            # We have finished processing the training trials
            for metric, models in self.models.items():
                for t, table in models.items():
                    data = table['data'].fillna(0)
                    if metric == 'm3':
                        y_fields = [field for field in data.columns if field[:6] == 'Saturn' and len(field) > 7]
                        X_fields = [field for field in data.columns if field not in y_fields and field != 'time' and field not in self.condition_fields]
                    elif metric == 'm6':
                        y_fields = [field for field in data.columns if 'Legend' in field]
                        X_fields = [field for field in data.columns if field not in y_fields and field not in {'time', 'seconds', 'Participant'} and field not in self.condition_fields]
                    else:
                        y_fields = self.config.get('evaluation', f'{metric}_y').split(',')
                        X_fields = [field for field in self.feature_fields if field not in y_fields]
                    X = data.filter(items=X_fields)
                    y = data.filter(items=y_fields)
                    table['X_fields'] = X_fields
                    # TODO: logit
                    table['regression'] = LinearRegression().fit(X, y)
        elif trial in self.testing_trials:
            # We have finished processing the testing data
            fname = f'{self.config.get("evaluation", "prediction_prefix", fallback="")}Trial-{self.completed[-1]}_'+\
                f'Vers-{self.config.get("evaluation", "version", fallback=1)}.metadata'
            messages = {}
            for metric, models in self.models.items():
                for t, table in sorted(models.items()):
                    # Set up eventual JSON message
                    if t not in messages:
                        messages[t] = {}
                    msg_type = self.config.get('evaluation', f'{metric}_type', fallback='State')
                    data = table['data'][table['data']['Trial'] == trial]
                    if metric == 'm6':
                        data = data[data['seconds'] >= (15-int(t))*60]
                        data = data[data['seconds'] == data['seconds'].min()]
                    data = data.fillna(0)
                    if msg_type not in messages[t]:
                        messages[t][msg_type] = self.make_prediction_header(msg_type, data['time'])
                    msg = messages[t][msg_type]
                    # Generate input data
                    if metric == 'm3':
                        y_fields = [field for field in data.columns if field[:6] == 'Saturn' and len(field) > 7]
                    elif metric =='m6':
                        y_fields = [field for field in data.columns if 'Legend' in field]                        
                    else:
                        y_fields = self.config.get('evaluation', f'{metric}_y').split(',')
                    X = data.filter(items=table['X_fields']).fillna(0)
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
                                predictions.append({'subject': self.parser.agentToPlayer[players[idx]] if metric == 'm3' else players[idx],
                                    'value': value, 'probability': prob/norm})
                    self.add_prediction_message(msg, data, predictions, metric)
            with open(fname, 'w') as prediction_file:
                for t, table in messages.items():
                    for msg in table.values():
                        print(json.dumps(msg), file=prediction_file)

    def finish(self):
        super().finish()
        if self.feature_output:
            columns = self.fields + sorted(set(self.feature_data.columns)-set(self.fields))
            columns.remove('Member')
            data = self.feature_data[columns]
            if os.path.splitext(self.feature_output)[1] == '.csv':
                with open(self.feature_output, 'w') as csvfile:
                    data.to_csv(csvfile, index=False, header=True)
            else:
                raise ValueError(f'Unable to output feature stats in {os.path.splitext(self.feature_output)[1][1:]} format.')

    def make_prediction_header(self, msg_type, mission_time):
        base_msg = self.parser.jsonParser.jsonMsgs[0]
        message = {'header': {
                    'timestamp': f'{datetime.datetime.utcnow().isoformat()}Z',
                    'message_type': 'agent',
                    'version': '0.3'
                    },
                }
        message['msg'] = {
                        'trial_id': base_msg['msg']['trial_id'],
                        'timestamp': message['header']['timestamp'],
                        'sub_type': f'Prediction:{msg_type}',
                        'version': message['header']['version'],
                        'source': f'atomic:{message["header"]["version"]}',
                        }
        message['data'] = {
            'created': message['header']['timestamp'],
            'predictions': []

        }
        return message

    def add_prediction_message(self, msg, row, predictions, metric):
        minutes, seconds = next(iter(row['time'].to_dict().values()))
        elapsed = (15-minutes)*60 - seconds
        elapsed *= 1000
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

if __name__ == '__main__':
    # Process command-line arguments
    parser = replay_parser()
    parser.add_argument('-o','--output', help='Name of file for storing feature stats')
    args = parse_replay_args(parser)
    replayer = FeatureReplayer(args['fname'], args['config'], rddl_file=args['rddl'], action_file=args['actions'], aux_file=args['aux'], logger=logging, output=args['output'])
    replayer.parameterized_replay(args)
