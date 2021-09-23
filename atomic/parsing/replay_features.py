"""
Subclass for adding feature counts to replay
"""
import csv
import json
import os
import datetime
import pandas
from sklearn.linear_model import LinearRegression
from atomic.parsing.count_features import *
from atomic.parsing.replayer import Replayer, replay_parser, parse_replay_args, filename_to_condition


HALLWAYS = ['ccw', 'cce', 'mcw', 'mce', 'scw', 'sce', 'sccc']

COUNT_ACTIONS_ARGS = [
    ('Event:dialogue_event', {}),
    ('Event:VictimPickedUp', {}),
    ('Event:VictimPlaced', {}),
    ('Event:ToolUsed', {}),
    ('Event:Triage', {'triage_state': 'SUCCESSFUL'}),
    ('Event:RoleSelected', {})
]

def collapse_rows(data_list, subjects={}):
    """
    Flattens the mutually exclusive feature columns into a single row per participant (most recent values for each)
    """
    data = None
    suffix = '_y'
    for new_data in data_list:
#                new_data = feature.dataframe[feature.dataframe['time'] == feature.dataframe['time'].min()]
        new_data = new_data.replace(subjects)
        if 'Participant' not in new_data.columns:
            new_data['Participant'] = 'Team'
        new_data = new_data.drop_duplicates(subset='Participant', keep='last')
        if data is None:
            data = new_data
        else:
            # Let's assume that values are the same for overlapping columns
            data = data.merge(new_data, how='outer', on='Participant', suffixes=(None, suffix))
            data = data.drop(columns=[col for col in data.columns if col[-2:] == suffix])
    return data.drop_duplicates()

class Metric:
    def __init__(self, name, y_fields, times=None, team=True, ignore={}):
        self.name = name
        if times is None:
            self.times = []
        else:
            self.times = times
        self.y_fields = y_fields
        self.data = {t: pandas.DataFrame() for t in self.times}
        self.team = team
        self.ignore = ignore
        self.regression = None

    def add_data(self, data_list, subjects={}):
        for t in self.times:
            data_t = [data[data['time'] > (15-int(t), 0)] for data in data_list]
            self.data[t] = collapse_rows(data_t, subjects)

    def train(self):
        for t, data in self.data.items():
            data = data.fillna(0)
            if self.team:
                data = data[data['Participant'] == 'Team']
            else:
                data = data[data['Participant'] != 'Team']
            for field in self.ignore + self.y_fields:
                assert field in data.columns
            X = data.filter(items=[field for field in data.columns if field not in self.ignore + self.y_fields])
            print(X)
            if self.name == 'm1':
                print(self.data.keys())
            y = data.filter(items=self.y_fields)
#            if metric == 'm3':
#                y_fields = [field for field in data.columns if field[:6] == 'Saturn' and len(field) > 7]
#                X_fields = [field for field in data.columns if field not in y_fields and field != 'time' and field not in self.condition_fields]
#            elif metric == 'm6':
#                y_fields = [field for field in data.columns if 'Legend' in field]
#                X_fields = [field for field in data.columns if field not in y_fields and field not in {'time', 'seconds', 'Participant'} and field not in self.condition_fields]
            # TODO: logit
            self.regression = LinearRegression().fit(X, y)

class FeatureReplayer(Replayer):
    def __init__(self, files=[], config=None, maps=None, rddl_file=None, action_file=None, aux_file=None, logger=logging, output=None):
        super().__init__(files=files, config=config, maps=maps, rddl_file=rddl_file, action_file=action_file, aux_file=aux_file, logger=logger)
        self.completed = []
        # Feature count bookkeeping
        self.feature_output = output
        self.feature_data = pandas.DataFrame()

        trial_fields = list(filename_to_condition(os.path.splitext(os.path.basename(files[0]))[0]))
        self.fields = trial_fields + ['Participant', 'time', 'Team Score', 'Individual Score']

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
            else:
                training_files = {}
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
            else:
                testing_files = {}
            if self.train or self.test:
                missing = sorted([f for f in self.files if f not in training_files.values() and f not in testing_files.values()])
                if missing:
                    logger.warning(f'Skipping non-training, non-testing trials: {", ".join(missing)}')
                self.files = sorted(training_files.values()) + sorted(testing_files.values())
            self.metrics = {Metric(metric, self.config.get('evaluation', f'{metric}_y').split(','),
                [t for t in self.config.get('evaluation', f'{metric}_train', fallback='15').split(',')],
                self.config.getboolean('evaluation', f'{metric}_team', fallback=False), trial_fields+['time', 'Participant'])
                for metric in self.config.get('evaluation', 'metrics', fallback=[]).split(',')}
        else:
            self.metrics = {}

    def _create_derived_features(self, parser, logger=logging):
        # processes room names
        all_loc_name = list(parser.jsonParser.rooms.keys())
        main_names = [nm[:nm.find('_')] for nm in all_loc_name if nm.find('_') >= 0]
        main_names = set(main_names + [nm for nm in all_loc_name if nm.find('_') < 0])
        room_names = main_names.difference(HALLWAYS)

        # adds feature counters
        self.derived_features[parser.jsonFile] = [RecordScore(logger)]
        for args in COUNT_ACTIONS_ARGS:
            self.derived_features[parser.jsonFile].append(CountAction(*args, logger=logger))
        self.derived_features[parser.jsonFile].append(CountEnterExit(room_names.copy(), logger=logger))
        self.derived_features[parser.jsonFile].append(CountTriageInHallways(HALLWAYS, logger=logger))
        self.derived_features[parser.jsonFile].append(CountVisitsPerRole(room_names, logger=logger))
        # self.derived_features[parser.jsonFile].append(CountRoleChanges(logger=logger))
        self.derived_features[parser.jsonFile].append(PlayerRoomPercentage(mission_length=15, logger=logger))
        self.derived_features[parser.jsonFile].append(MarkerPlacement(logger))
        self.derived_features[parser.jsonFile].append(DialogueLabels(logger))

    def pre_replay(self, parser, config=None, logger=logging):
        self._create_derived_features(parser, logger)
        result = super().pre_replay(config, logger)
        trial_fields = {'File': os.path.basename(self.file_name)}
        trial_fields.update(filename_to_condition(os.path.basename(os.path.splitext(parser.jsonFile)[0])))
        if self.fields is None:
            self.fields = list(trial_fields.keys())
            self.fields.append('Participant')
            self.fields.append('time')
            self.fields.append('Team Score')
            self.fields.append('Individual Score')
        # processes data to extract features depending on type of count
        for feature in feature_list:
            for field, value in trial_fields.items():
                feature.dataframe[field] = value
        for metric in self.metrics:
            metric.add_data([feature.dataframe for feature in feature_list], parser.jsonParser.subjects)
        if self.feature_output is not None:
            data = collapse_rows([feature.dataframe for feature in feature_list], parser.jsonParser.subjects)
            self.feature_data = self.feature_data.append(data, ignore_index=True)
        return result

    def post_replay(self, parser, logger=logging):
        super().post_replay(parser, logger)
        trial = filename_to_condition(parser.jsonFile)['Trial']
        map_name = filename_to_condition(parser.jsonFile)['CondWin']
        self.completed.append(trial)
        if trial in self.training_trials and len(self.completed) == len(self.training_trials):
            # We have finished processing the training trials
            for metric in sorted(self.metrics):
                metric.train()
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
                        base_msg = parser.jsonParser.jsonMsgs[0]
                        messages[t][msg_type] = self.make_prediction_header(base_msg, msg_type, data['time'])
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
                                predictions.append({'subject': parser.agentToPlayer[players[idx]] if metric == 'm3' else players[idx],
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

    def make_prediction_header(self, base_msg, msg_type, mission_time):
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
