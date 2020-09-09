__author__ = 'brett israelsen'
__email__ = 'brett.israelsen@rtx.com'

import os


def get_participant_data_props():
    """
    Utility function to associate participant data with start/stop times, stop times are important right now becasue
    parsing past a certain point on different files will break.
    :return:
    """
    fldr = 'data'
    # the 'end_t' below was obtained by trying to parse a file, and the observing at what step an error occurred. -1 indicates that the entire file will be parsed.
    auto_named_data = {'file_prefix': 'processed_ASIST_data_study_id_XXX_condition_id_YYY_trial_id_ZZZ_messages.csv',
                       'studies': [1], 'trials': {1: [1, 5, 8], 2: [2, 3, 10], 3: [6, 13]},
                       'start_t': {1: [0, 0, 0], 2: [0, 0, 0], 3: [0, 0]},
                       #  'end_t':{1:[36,12,-1], 2:[-1,-1,13], 3:[30,62]},
                       'end_t': {1: [-1, -1, -1], 2: [-1, -1, -1], 3: [-1, -1]},
                       }
    data_list = []
    for cond in auto_named_data['trials']:
        for i in range(len(auto_named_data['trials'][cond])):
            trial = auto_named_data['trials'][cond][i]
            fname = auto_named_data['file_prefix']
            study_str = str.zfill('1', 6)
            cond_str = str.zfill(f'{cond}', 6)
            id_str = str.zfill(f'{trial}', 6)
            fname = fname.replace('XXX', study_str)
            fname = fname.replace('YYY', cond_str)
            fname = fname.replace('ZZZ', id_str)
            entry = {'fname': os.path.join(fldr, fname),
                     'start': auto_named_data['start_t'][cond][i],
                     'stop': auto_named_data['end_t'][cond][i]}

            data_list.append(entry)

    return data_list


if __name__ == '__main__':
    lst = get_participant_data_props()
    for itm in lst:
        print(itm)
