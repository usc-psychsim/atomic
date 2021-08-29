import csv
import logging
import os

from atomic.parsing.replayer import Replayer, replay_parser, parse_replay_args, filename_to_condition
from atomic.bin.cluster_features import _get_feature_values, _get_derived_features

class FeatureReplayer(Replayer):
    def __init__(self, files=[], config=None, maps=None, rddl_file=None, action_file=None, aux_file=None, logger=logging, output=None):
        super().__init__(files=files, config=config, maps=maps, rddl_file=rddl_file, action_file=action_file, aux_file=aux_file, logger=logger)
        # Feature count bookkeeping
        self.feature_output = output
        self.feature_data = []
        self.fields = None

    def pre_replay(self, config=None, logger=logging):
        self.derived_features = _get_derived_features(self.parser)
        result = super().pre_replay(config, logger)
        # processes data to extract features depending on type of count
        record = filename_to_condition(os.path.basename(self.file_name))
        if self.fields is None:
            fields = ['Trial'] + [field for field in record if field != 'Trial']
        for feature in self.derived_features:
            values = _get_feature_values(feature)
            record.update(values)
            if self.fields is None:
                fields += list(values.keys())
        if self.fields is None:
            self.fields = fields
        self.feature_data.append(record)
        return result

    def post_replay(self, logger=logging):
        super().post_replay(logger)
        if self.feature_output is not None:
            if os.path.splitext(self.feature_output)[1] == '.csv':
                with open(self.feature_output, 'w') as csvfile:
                    writer = csv.DictWriter(csvfile, self.fields, extrasaction='ignore')
                    writer.writeheader()
                    for row in self.feature_data:
                        writer.writerow(row)
            else:
                raise ValueError(f'Unable to output feature stats in {os.path.splitext(self.feature_output)[1][1:]} format.')

if __name__ == '__main__':
    # Process command-line arguments
    parser = replay_parser()
    parser.add_argument('-o','--output', help='Name of file for storing feature stats')
    args = parse_replay_args(parser)
    replayer = FeatureReplayer(args['fname'], args['config'], rddl_file=args['rddl'], action_file=args['actions'], aux_file=args['aux'], logger=logging, output=args['output'])
    replayer.parameterized_replay(args)
