from argparse import ArgumentParser
import json
import os.path
import pandas

from sklearn.preprocessing import *
from sklearn.linear_model import *

from replayer import *

class MinimalReplayer(Replayer):
    def process_files(self, num_steps=0, fname=None):
        self.extractions = pandas.DataFrame()
        self.totals = pandas.DataFrame()
        self.labels = set()
        super().process_files(num_steps, fname)

    def process_file(self, fname, num_steps):
        with open(fname, 'r') as json_file:
            conditions = filename_to_condition(fname)
            print(conditions['Trial'])
            total = {'Trial': conditions['Trial'], 'Team': conditions['Team']}
            text = [None]
            for line in json_file:
                msg = json.loads(line)
                msg_type = msg['msg']['sub_type']
                if msg_type == 'Event:dialogue_event':
                    participant = msg['data']['participant_id']
                    if participant != 'Server' and msg['data']['text']:
                        if text[-1] != msg["data"]["text"].strip():
                            text.append(f'{participant}: {msg["data"]["text"].strip()}')
                            record = {'Trial': conditions['Trial'], 'Team': conditions['Team'], 'Participant': participant, 'Timestamp': msg['header']['timestamp'], 
                                'Text': msg['data']['text'].strip() if msg['data']['text'] else ''}
                            for label in set(sum([ex['labels'] for ex in msg['data']['extractions']], [])):
                                record[label] = True
                                self.labels.add(label)
                                total[label] = total.get(label, 0) + 1
                            self.extractions = self.extractions.append(record, ignore_index=True)
                elif msg_type == 'Event:Scoreboard':
                    for field in ['TeamScore']:
                        total[field] = msg['data']['scoreboard'][field]
            self.totals = self.totals.append(total, ignore_index=True)
        with open(f'{os.path.splitext(fname)[0]}.txt', 'w') as txt_file:
            txt_file.write('\n'.join(text[1:]))

    def finish(self):
        self.extractions.to_csv('labels.tsv', sep='\t', na_rep=0, columns=['Trial', 'Team', 'Participant', 'Timestamp', 'Text']+sorted(self.labels))
        data = self.totals.dropna(subset=['TeamScore', 'Commitment'])
        data.to_csv('totals.tsv', sep='\t', na_rep=0, columns=['Trial', 'Team', 'TeamScore']+sorted(self.labels))
        regression = self.regression()
        weights = [(label, regression.coef_[i]) for i, label in enumerate(fields)]
        weights.sort(key=lambda tup: abs(tup[1]), reverse=True)
        data = pandas.DataFrame([{'Label': label, 'Coefficient': coef} for label, coef in weights])
        data.to_csv('regression.csv')

    def regression(self):
        y = self.totals.dropna(subset=['TeamScore', 'Commitment']).filter(items=['TeamScore']).astype(int)
        y = normalize(y).values.ravel()
        X = self.totals.dropna(subset=['TeamScore', 'Commitment']).drop(columns=['Trial', 'Team', 'TeamScore']).fillna(0).astype(int)
        X = normalize(X).fillna(0)
        fields = X.columns
#        scaler = MinMaxScaler()
#        X = scaler.fit_transform(X)
        regression = LinearRegression().fit(X, y)
        print(regression.score(X, y))
        return regression

def normalize(data):
    return (data-data.min())/(data.max()-data.min())

if __name__ == '__main__':
    # Process command-line arguments
    parser = ArgumentParser()
    parser.add_argument('fname', nargs='+',
                        help='Log file(s) (or directory of log files) to process')
    args = vars(parser.parse_args())
    replayer = MinimalReplayer(args['fname'])
    replayer.parameterized_replay(args)
