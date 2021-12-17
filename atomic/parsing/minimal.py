from argparse import ArgumentParser
import json
import os.path
import pandas
from replayer import *

class MinimalReplayer(Replayer):
    def process_files(self, num_steps=0, fname=None):
        self.extractions = pandas.DataFrame()
        self.labels = set()
        super().process_files(num_steps, fname)

    def process_file(self, fname, num_steps):
        with open(fname, 'r') as json_file:
            conditions = filename_to_condition(fname)
            print(conditions['Trial'])
            text = []
            for line in json_file:
                msg = json.loads(line)
                msg_type = msg['msg']['sub_type']
                if msg_type == 'Event:dialogue_event':
                    participant = msg['data']['participant_id']
                    if participant != 'Server':
                        if msg['data']['text']:
                            if len(text) == 0 or text[-1] != msg["data"]["text"].strip():
                                text.append(f'{participant}: {msg["data"]["text"].strip()}')
                        record = {'Trial': conditions['Trial'], 'Team': conditions['Team'], 'Participant': participant, 'Timestamp': msg['header']['timestamp'], 
                            'Text': msg['data']['text'].strip() if msg['data']['text'] else ''}
                        for label in sum([ex['labels'] for ex in msg['data']['extractions']], []):
                            record[label] = True
                            self.labels.add(label)
                    self.extractions = self.extractions.append(record, ignore_index=True)
        with open(f'{os.path.splitext(fname)[0]}.txt', 'w') as txt_file:
            txt_file.write('\n'.join(text))

    def finish(self):
        self.extractions.to_csv('labels.csv', sep='\t', na_rep=0, columns=['Trial', 'Team', 'Participant', 'Timestamp', 'Text']+sorted(self.labels))

if __name__ == '__main__':
    # Process command-line arguments
    parser = ArgumentParser()
    parser.add_argument('fname', nargs='+',
                        help='Log file(s) (or directory of log files) to process')
    args = vars(parser.parse_args())
    replayer = MinimalReplayer(args['fname'])
    replayer.parameterized_replay(args)
