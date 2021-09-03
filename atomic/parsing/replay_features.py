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

class MarkerPlacement(Feature):
    def __init__(self, logger=logging):
        super().__init__('count marker placement per player per room', logger)
        self.marker_count = {}
        self.marker_legend = {}

    def processMsg(self, msg):
        super().processMsg(msg)
        if self.msg_type == 'Event:MarkerPlaced':
            if self.msg_player not in self.marker_count:
                self.marker_count[self.msg_player] = {}
            if msg['marker_type'] not in self.marker_count[self.msg_player]:
                self.marker_count[self.msg_player][msg['marker_type']] = {}
            self.marker_count[self.msg_player][msg['marker_type']][msg['victim_type']] = self.marker_count[self.msg_player][msg['marker_type']].get(msg['victim_type'], 0) + 1
            if 'marker_legend' in msg:
                self.marker_legend[self.msg_player] = msg['marker_legend']
        for player, markers in self.marker_count.items():
            row = {'Player': player}
            if player in self.marker_legend:
                row[f'Marker Legend {self.marker_legend[player]}'] = 1
            for marker, table in markers.items():
                norm = sum(table.values())
                row.update({f'{marker}_{victim}': count/norm for victim, count in table.items()})
                row[marker] = norm
            self.addRow(row)

    def printValue(self):
        print(f'{self.name} {self.marker_count}')

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
        self.derived_features = [RecordScore(logger)]
        self.derived_features += _get_derived_features(self.parser)
        self.derived_features.append(PlayerRoomPercentage(mission_length=15, logger=logger))
        self.derived_features.append(MarkerPlacement(logger))
        result = super().pre_replay(config, logger)
        # processes data to extract features depending on type of count
        for feature in self.derived_features:
            df = feature.dataframe
            df['seconds'] = df.apply(lambda row: row['time'][0]*60+row['time'][1], axis=1)
            for player, agent in self.parser.playerToAgent.items():
                df = df.rename(columns={col: col.replace(player, agent) for col in df.columns})
            feature.dataframe = df
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
                    elif isinstance(feature, MarkerPlacement):
                        if metric == 'm6':
                            feature.msg_time = '15:0'
                            for player in self.parser.players:
                                feature.addRow({'Player': player, 'seconds': 15*60})
                            feature.dataframe['Trial'] = record['Trial']
                            models[t]['data'] = models[t]['data'].append(feature.dataframe, ignore_index=True)
                            break
                        else:
                            # Ignore this feature for other metrics
                            continue
                    elif metric != 'm6':
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
                if metric == 'm3':
                    # Break data down by player
                    models[t]['players'] = {}
                    for player in self.parser.agentToPlayer:
                        player_record = {field[len(player)+1:]: record.get(field, 0) 
                            for field in self.feature_fields if player in field}
                        if player in self.parser.player_maps:
                            # Training trial
                            player_record[self.parser.player_maps[player]] = 1
                        else:
                            # Testing trial
                            player_record['Player'] = player
                        player_record['Trial'] = record['Trial']
                        player_record['time'] = record['time']
                        player_record[record['CondWin']] = 1
                        models[t]['data'] = models[t]['data'].append(player_record, ignore_index=True)
                elif metric != 'm6':
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
                        X_fields = [field for field in data.columns if field not in y_fields and field not in {'time', 'seconds', 'Player'} and field not in self.condition_fields]
                    else:
                        y_fields = self.config.get('evaluation', f'{metric}_y').split(',')
                        X_fields = [field for field in self.feature_fields if field not in y_fields]
                    X = data.filter(items=X_fields)
                    y = data.filter(items=y_fields)
                    table['X_fields'] = X_fields
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
                        players = list(data['Player'])
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

    def make_prediction_header(self, msg_type, mission_time):
        base_msg = self.parser.jsonParser.jsonMsgs[0]
        message = {'header': {
                    'timestamp': f'{datetime.datetime.utcnow().isoformat()}Z',
                    'message_type': 'agent',
                    'version': '0.2'
                    },
                }
        message['msg'] = {
                        'trial_id': base_msg['msg']['trial_id'],
                        'timestamp': message['header']['timestamp'],
                        'sub_type': f'Prediction:{msg_type}',
                        'version': message['header']['version']
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
