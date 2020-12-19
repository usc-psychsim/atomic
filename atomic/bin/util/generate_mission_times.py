import argparse
import json
import logging
import os
import pandas as pd
from model_learning.util.io import create_clear_dir, get_files_with_extension, get_file_name_without_extension

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Loads several CSV log files + corresponding metadata files and generates new CSVs containing the ' \
           'mission times.'

OUTPUT_DIR = 'output/csv_mission_times'
MISSION_TIME_PARAM = 'mission_timer'
TIME_STAMP_PARAM = '@timestamp'
CSV_PREFIX = 'processed_'


def get_files(files_dir, extension):
    if os.path.isfile(files_dir):
        files = [files_dir]
    elif os.path.isdir(files_dir):
        files = list(get_files_with_extension(files_dir, extension))
    else:
        raise ValueError('Input path is not a valid file or directory: {}.'.format(args.replays))
    return files


def get_stamp_mission_time(mission_times, timestamp):
    timestamp = timestamp.tz_localize(None)
    for i in range(len(mission_times)):
        ts, mission_time = mission_times[i]
        if ts > timestamp:
            return mission_time if i == 0 else mission_times[i - 1][1]
    return mission_times[-1][1]


if __name__ == '__main__':
    # parse command-line arguments
    parser = argparse.ArgumentParser(description=__desc__)

    parser.add_argument('-r', '--replays', required=True, type=str,
                        help='Directory containing the replay logs or single replay file to process.')
    parser.add_argument('-m', '--metadata', required=True, type=str,
                        help='Directory containing the metadata files or single metadata file to process.')
    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR, help='Directory in which to save results.')
    parser.add_argument('-c', '--clear', help='Whether to clear output directories before generating results.',
                        action='store_true')
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Verbosity level.')
    args = parser.parse_args()

    # sets up log to file
    log_level = logging.WARN if args.verbosity == 0 else logging.INFO if args.verbosity == 1 else logging.DEBUG
    logging.basicConfig(format='%(message)s', level=log_level)

    # create output
    output_dir = os.path.join(args.output, os.path.basename(args.replays))
    create_clear_dir(output_dir, args.clear)

    # checks input files
    csv_files = get_files(args.replays, 'csv')
    meta_files = get_files(args.metadata, 'metadata')
    csv_to_meta = {}
    for csv_file in csv_files:
        csv_meta_file = get_file_name_without_extension(csv_file.replace(CSV_PREFIX, '')) + '.metadata'
        for meta_file in meta_files:
            if os.path.basename(meta_file) == csv_meta_file:
                csv_to_meta[csv_file] = meta_file
                break

    not_found_csv = set(csv_files) - set(csv_to_meta.keys())
    logging.info('Could not find matching metadata file for:\n\t{}'.format('\n\t'.join(not_found_csv)))

    logging.info('Processing {} log files from\n\t"{}"\n\t"{}"...'.format(
        len(csv_to_meta), args.replays, args.metadata))

    for csv_file, meta_file in csv_to_meta.items():

        logging.info('Processing "{}" and "{}"...'.format(csv_file, meta_file))

        # reads metadata file, registers mission times
        mission_times = []
        with open(meta_file, 'r') as f:
            for line in f:
                entry = json.loads(line)
                if 'data' not in entry and 'message' in entry:
                    entry = json.loads(entry['message'])
                if 'data' not in entry:
                    continue
                if MISSION_TIME_PARAM in entry['data'] and \
                        entry['data'][MISSION_TIME_PARAM] != 'Mission Timer not initialized.':
                    minutes, seconds = [int(value) for value in entry['data'][MISSION_TIME_PARAM].split(':')]
                    mission_time = minutes * 60 + seconds
                    if len(mission_times) > 0 and mission_times[-1][1] == mission_time:
                        continue
                    timestamp = entry[TIME_STAMP_PARAM] if TIME_STAMP_PARAM in entry else entry['header']['timestamp']
                    timestamp = pd.to_datetime(timestamp, infer_datetime_format=True, exact=False)
                    timestamp = timestamp.tz_localize(None)
                    mission_times.append((timestamp, mission_time))

        if len(mission_times) == 0:
            logging.info('Could not process file "{}", incorrect timestamps'.format(meta_file))
            continue

        df = pd.read_csv(csv_file, index_col=0)
        df[TIME_STAMP_PARAM] = pd.to_datetime(df[TIME_STAMP_PARAM], infer_datetime_format=True, exact=False)
        df[MISSION_TIME_PARAM] = df.apply(lambda r: get_stamp_mission_time(mission_times, r[TIME_STAMP_PARAM]), axis=1)

        file_path = os.path.join(output_dir, os.path.basename(csv_file))
        df.to_csv(file_path)
        logging.info('Processed "{}", saved to "{}"'.format(csv_file, file_path))
