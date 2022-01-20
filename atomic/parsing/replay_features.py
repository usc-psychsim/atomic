"""
Subclass for adding feature counts to replay
"""
import csv
import json
import os
import datetime
import math
import pandas

from atomic.parsing.count_features import *
from atomic.parsing.replayer import *
from atomic.analytic import *
from atomic.analytic.metrics2 import *

HALLWAYS = ['ccw', 'cce', 'mcw', 'mce', 'scw', 'sce', 'sccc']

COUNT_ACTIONS_ARGS = [
    ('Event:dialogue_event', {}),
    ('Event:VictimPickedUp', {}),
    ('Event:VictimPlaced', {}),
    ('Event:ToolUsed', {}),
    ('Event:Triage', {'triage_state': 'SUCCESSFUL'}),
    ('Event:RoleSelected', {})
]

class FeatureReplayer(Replayer):
    DEFAULT_FEATURES = {'RecordScore', 'MarkerPlacement', 'DialogueLabels', 'RecordMap', 'CountAction', 'CountEnterExit', 
        'CountTriageInHallways', 'CountVisitsPerRole', 'PlayerRoomPercentage'}

    def __init__(self, files=[], trials=None, config=None, maps=None, rddl_file=None, action_file=None, aux_file=None, logger=logging, output=None):
        super().__init__(files=files, trials=trials, config=config, maps=maps, rddl_file=rddl_file, action_file=action_file, aux_file=aux_file, logger=logger)
        self.completed = []
        # Feature count bookkeeping
        self.feature_output = output
        self.feature_data = pandas.DataFrame()

        trial_fields = list(filename_to_condition(os.path.splitext(os.path.basename(files[0]))[0]))
        self.fields = trial_fields + ['Participant', 'time']

        self.prediction_models = {}

        self.training_trials = set()
        self.testing_trials = set()
        if self.config:
            # Look for evaluation files
            self.train = self.config.get('evaluation', 'train', fallback=None)
            if self.train:
                self.train = os.path.join(os.path.dirname(__file__), '..', '..', self.train)
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
                self.test = os.path.join(os.path.dirname(__file__), '..', '..', self.test)
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
                missing = sorted([filename_to_condition(f)['Trial'] for f in self.files 
                    if f not in training_files.values() and f not in testing_files.values()])
                if missing:
                    logger.warning(f'Skipping non-training, non-testing trials: {", ".join(missing)}')
                self.files = sorted(training_files.values()) + sorted(testing_files.values())
            self.metrics = {name.strip(): STUDY2_METRICS[name.strip()](name.strip(), trial_fields+['time', 'Participant', 'File'], logger) 
                for name in self.config.get('evaluation', 'metrics', fallback=STUDY2_METRICS).split(',')}
        else:
            self.metrics = {}

    def _create_derived_features(self, parser, logger=logging):
        # processes room names
        all_loc_name = list(parser.jsonParser.rooms.keys())
        main_names = [nm[:nm.find('_')] for nm in all_loc_name if nm.find('_') >= 0]
        main_names = set(main_names + [nm for nm in all_loc_name if nm.find('_') < 0])
        room_names = main_names.difference(HALLWAYS)

        # adds feature counters
        self.derived_features[parser.jsonFile] = []
        for feature_cls in Feature.__subclasses__():
            if self.config.getboolean('features', feature_cls.__name__, fallback=feature_cls.__name__ in self.DEFAULT_FEATURES):
                if feature_cls is CountAction:
                    for args in COUNT_ACTIONS_ARGS:
                        self.derived_features[parser.jsonFile].append(CountAction(*args, logger=logger))
                elif feature_cls is CountEnterExit:
                    self.derived_features[parser.jsonFile].append(CountEnterExit(room_names.copy(), logger=logger))
                elif feature_cls is CountTriageInHallways:
                    self.derived_features[parser.jsonFile].append(CountTriageInHallways(HALLWAYS, logger=logger))
                elif feature_cls is CountVisitsPerRole:
                    self.derived_features[parser.jsonFile].append(CountVisitsPerRole(room_names, logger=logger))
                elif feature_cls is PlayerRoomPercentage:
                    self.derived_features[parser.jsonFile].append(PlayerRoomPercentage(mission_length=15, logger=logger))
                else:
                    # Fallback is to assume no arguments
                    self.derived_features[parser.jsonFile].append(feature_cls(logger))
        return self.derived_features[parser.jsonFile]

    def pre_replay(self, parser, logger=logging):
        self._create_derived_features(parser, logger)
        result = super().pre_replay(parser, logger)
        trial_fields = {'File': os.path.basename(parser.jsonFile)}
        trial_fields.update(filename_to_condition(os.path.basename(os.path.splitext(parser.jsonFile)[0])))
        if self.fields is None:
            self.fields = list(trial_fields.keys())
            self.fields.append('Participant')
            self.fields.append('time')
        # processes data to extract features depending on type of count
        for feature in self.derived_features[parser.jsonFile]:
            if isinstance(feature, RecordScore):
                self.fields.insert(self.fields.index('time')+1, 'Individual Score')
                self.fields.insert(self.fields.index('time')+1, 'Team Score')
            for field, value in trial_fields.items():
                feature.dataframe[field] = value
        subjects = dict(parser.jsonParser.subjects)
        subjects['Team'] = trial_fields['Team']
        feature_data = [feature.dataframe for feature in self.derived_features[parser.jsonFile]]
        if feature_data:
            for metric in self.metrics.values():
                metric.add_data(feature_data, subjects)
            if self.feature_output is not None:
                data = collapse_rows(feature_data, subjects)
                self.feature_data = self.feature_data.append(data, ignore_index=True)
        return result

    def post_replay(self, world, parser, logger=logging):
        super().post_replay(world, parser, logger)
        if len(self.feature_data) > 0:
            # Train / test
            trial = filename_to_condition(parser.jsonFile)['Trial']
            map_name = filename_to_condition(parser.jsonFile)['CondWin']
            self.completed.append(trial)
            if trial in self.training_trials and len(self.completed) == len(self.training_trials):
                # We have finished processing the training trials
                for metric in sorted(self.metrics.values(), key=lambda m: m.name):
                    metric.train(self.feature_data)
            elif trial in self.testing_trials:
                # We have finished processing the testing data
                fname = f'{self.config.get("evaluation", "prediction_prefix", fallback="")}Trial-{self.completed[-1]}_'+\
                    f'Vers-{self.config.get("evaluation", "version", fallback=1)}.metadata'
                results = {metric: metric.test(trial) for metric in self.metrics.values()}
                trial_id = parser.jsonParser.jsonMsgs[0]['msg']['trial_id']
                messages = {}
                for metric, result in results.items():
                    if metric.y_type not in messages:
                        messages[metric.y_type] = {}
                    messages[metric.y_type][metric] = result
                with open(os.path.join(os.path.dirname(__file__), '..', '..', fname), 'w') as prediction_file:
                    for y_type, result in messages.items():
                        print(json.dumps(analysis_to_json(result, y_type, trial_id), indent=3), file=prediction_file)

    def finish(self):
        super().finish()
        if self.feature_output and len(self.feature_data) > 0:
            columns = self.fields + sorted(set(self.feature_data.columns)-set(self.fields))
            columns.remove('Member')
            data = self.feature_data[columns]
            if os.path.splitext(self.feature_output)[1] == '.csv':
                with open(self.feature_output, 'w') as csvfile:
                    data.to_csv(csvfile, index=False, header=True)
            else:
                raise ValueError(f'Unable to output feature stats in {os.path.splitext(self.feature_output)[1][1:]} format.')

def feature_cmd_parser():
    parser = replay_parser()
    parser.add_argument('-o','--output', help='Name of file for storing feature stats')
    return parser

if __name__ == '__main__':
    # Process command-line arguments
    parser = feature_cmd_parser()
    args = parse_replay_args(parser)
    replayer = FeatureReplayer(args['fname'], args['trials'], args['config'], rddl_file=args['rddl'], action_file=args['actions'], aux_file=args['aux'], logger=logging, output=args['output'])
    replayer.parameterized_replay(args)
