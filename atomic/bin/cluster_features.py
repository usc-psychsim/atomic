import argparse
import logging
import os
import tqdm
import re
import pandas as pd
from typing import Dict
from sklearn import preprocessing
from sklearn.cluster import AgglomerativeClustering
from atomic.parsing.parse_into_msg_qs import MsgQCreator
from atomic.parsing.count_features import CountAction, CountRoleChanges, CountTriageInHallways, CountEnterExit, Feature, \
    CountVisitsPerRole
from atomic.util.io import str2bool, create_clear_dir, save_args, change_log_handler, get_files_with_extension, \
    get_file_name_without_extension
from atomic.util.mp import get_pool_and_map
from atomic.util.clustering import hopkins_statistic
from atomic.util.plot import plot_clustering_distances, plot_clustering_dendrogram

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Loads a series of game logs (metadata files), performs feature counting, and then clusters files based on' \
           'feature count distance.'

LOG_FILE_EXTENSION = 'metadata'

FILE_NAME_COL = 'File'
CLUSTER_ID_COL = 'Cluster'
CLUSTER_COUNT_COL = 'Count'
FILE_NAMES_COL = 'Files'

COUNT_ACTIONS_ARGS = [
    ('Event:dialogue_event', {}),
    ('Event:VictimPickedUp', {}),
    ('Event:VictimPlaced', {}),
    ('Event:ToolUsed', {}),
    ('Event:Triage', {'triage_state': 'SUCCESSFUL'}),
    ('Event:RoleSelected', {})
]


def main():
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', type=str, required=True,
                        help='The path to a directory containing the game logs (.metadata files) or a'
                             'comma-separated string with the paths to individual log files.')
    parser.add_argument('--output', '-o', type=str, required=True, help='Directory in which to save results')
    parser.add_argument('--processes', '-p', type=int, default=1,
                        help='Number of processes for parallel processing. Value < 1 uses all available cpus.')
    parser.add_argument('--format', '-f', type=str, default='png', help='Format of result images')

    parser.add_argument('--affinity', '-a', type=str, default='euclidean',
                        help='Metric used to compute the linkage. Can be “euclidean”, “l1”, “l2”, '
                             '“manhattan” or “cosine”. If linkage is “ward”, only “euclidean” is accepted.')
    parser.add_argument('--linkage', '-l', type=str, default='average',
                        help='Which linkage criterion to use. The linkage criterion '
                             'determines which distance to use between sets of observation. '
                             'The algorithm will merge the pairs of cluster that minimize '
                             'this criterion. One of: "complete", "average", "single" or "ward".')
    parser.add_argument('--n_clusters', '-n', type=int, default=-1,
                        help='The number of clusters to find. Value of -1 will use distance_threshold.')
    parser.add_argument('--distance_threshold', '-dt', type=float, default=0.025,
                        help='The linkage distance threshold above which, clusters will not be merged.')
    parser.add_argument('--eval_clusters', '-ec', type=int, default=7,
                        help='Maximum number of clusters for which to perform evaluation')

    parser.add_argument('--clear', '-c', type=str2bool, default="False",
                        help='Clear output directories before generating results.')
    parser.add_argument('--verbosity', '-v', type=int, default=0, help='Verbosity level.')
    args = parser.parse_args()

    # prepares output dir and log
    create_clear_dir(args.output, args.clear)
    save_args(args, os.path.join(args.output, 'args.json'))
    change_log_handler(os.path.join(args.output, 'cluster-features.log'), args.verbosity)

    # parses game log files
    logging.info('========================================')
    if ',' in args.input or args.input.endswith(LOG_FILE_EXTENSION):
        # files mode, split them
        files = [file.strip() for file in args.input.split(',')]
    else:
        # directory mode, load all metadata files
        files = get_files_with_extension(args.input, LOG_FILE_EXTENSION)

    # checks files
    files = [file for file in files if file.endswith(LOG_FILE_EXTENSION) and os.path.isfile(file)]
    if len(files) == 0:
        raise ValueError(f'Could not find any {LOG_FILE_EXTENSION} files in provided argument: {args.input}!')

    # loads data from logs
    logging.info(f'Loading {len(files)} game log files...')
    pool, map_func = get_pool_and_map(args.processes, star=False, iterator=True)
    results = list(tqdm.tqdm(map_func(_parse_log_file, files), total=len(files)))

    # converts to dataframe and saves to file
    df = pd.DataFrame(results).fillna(0)
    logging.info('========================================')
    logging.info(f'Finished processing log files, got {len(df.columns)} features for {len(df)} files.')
    file_path = os.path.join(args.output, 'features.csv')
    logging.info(f'Saving CSV file with all features to {file_path}...')
    df.to_csv(file_path, index=False)

    # normalize data
    logging.info('========================================')
    logging.info('Normalizing data...')
    df.iloc[:, 1:] = preprocessing.MinMaxScaler().fit_transform(df.iloc[:, 1:].values)  # ignore ID column
    file_path = os.path.join(args.output, 'features-norm.csv')
    logging.info(f'Saving CSV file with all normalized features to {file_path}...')
    df.to_csv(file_path, index=False)

    # split
    file_names = df[FILE_NAME_COL].values
    data = df.iloc[:, 1:].values

    logging.info('========================================')
    logging.info('Computing Hopkins statistic for the data...')
    h = hopkins_statistic(data)
    logging.info(f'\tH={h:.2f}')
    if h <= 0.3:
        logging.info('\tTrace data is regularly spaced')
    elif 0.45 <= h <= 0.55:
        logging.info('\tTrace data is random')
    elif h > 0.75:
        logging.info('\tTrace data has a high tendency to cluster')

    # cluster data
    logging.info('========================================')
    logging.info(f'Clustering {data.shape[0]} datapoints...')
    clustering = AgglomerativeClustering(n_clusters=None if args.n_clusters == -1 else args.n_clusters,
                                         affinity=args.affinity,
                                         linkage=args.linkage,
                                         compute_distances=True,
                                         distance_threshold=args.distance_threshold if args.n_clusters == -1 else None)
    clustering.fit(data)
    logging.info(f'Found {clustering.n_clusters_} clusters at max. distance: {clustering.distance_threshold}')

    # saves clustering results
    logging.info('========================================')
    logging.info('Saving clustering results...')
    plot_clustering_distances(clustering, os.path.join(args.output, f'clustering-distances.{args.format}'))
    plot_clustering_dendrogram(clustering, os.path.join(args.output, f'clustering-dendrogram.{args.format}'))

    # gets traces idxs in each cluster
    clusters = {}
    for idx, cluster in enumerate(clustering.labels_):
        if cluster not in clusters:
            clusters[cluster] = []
        clusters[cluster].append(idx)

    df = pd.DataFrame([{CLUSTER_ID_COL: cluster,
                        CLUSTER_COUNT_COL: len(idxs),
                        FILE_NAMES_COL: [file_names[idx] for idx in idxs]}
                       for cluster, idxs in clusters.items()], index=CLUSTER_ID_COL)
    df.sort_index(inplace=True)
    file_path = os.path.join(args.output, 'cluster-traces.csv')
    df.to_csv(file_path)

    # TODO evaluate (at least internally)

    logging.info('Done!')


def _parse_log_file(log_file: str) -> Dict[str, float]:
    msg_qs = MsgQCreator(log_file, logger=logging)

    # processes room names
    all_loc_name = list(msg_qs.jsonParser.rooms.keys())
    main_names = [nm[:nm.find('_')] for nm in all_loc_name if nm.find('_') >= 0]
    main_names = set(main_names + [nm for nm in all_loc_name if nm.find('_') < 0])
    hallways = ['ccw', 'cce', 'mcw', 'mce', 'scw', 'sce', 'sccc']
    room_names = main_names.difference(hallways)

    # adds feature counters
    derived_features = []
    for args in COUNT_ACTIONS_ARGS:
        derived_features.append(CountAction(*args))
    derived_features.append(CountEnterExit(room_names))
    derived_features.append(CountTriageInHallways(hallways))
    # derived_features.append(CountVisitsPerRole(room_names))
    derived_features.append(CountRoleChanges())

    # process messages
    msg_qs.startProcessing(derived_features, msg_types=None)  # use all msg types available

    # processes data to extract features depending on type of count
    features = {FILE_NAME_COL: get_file_name_without_extension(log_file)}
    for derived_feature in derived_features:
        features.update(_get_feature_values(derived_feature))

    return features


def _get_feature_values(derived_feature: Feature) -> Dict[str, float]:
    if isinstance(derived_feature, CountAction) or \
            isinstance(derived_feature, CountEnterExit) or \
            isinstance(derived_feature, CountRoleChanges):
        # get feature name
        feature_name = derived_feature.type_to_count if isinstance(derived_feature, CountAction) \
            else f'Enter_Exit_{derived_feature.msg_type}' if isinstance(derived_feature, CountEnterExit) \
            else f'Role_Changes_{derived_feature.msg_type}' if isinstance(derived_feature, CountRoleChanges) \
            else ''
        feature_name = _change_feature_name(feature_name)

        # if it's a count per player feature, get stats for all players' counts
        data = pd.DataFrame(derived_feature.playerToCount.values())
        if len(data) == 0:
            return {}
        data = data[0].describe().fillna(0)
        return {f'{feature_name}_{k.title()}': v for k, v in data.to_dict().items()}

    if isinstance(derived_feature, CountTriageInHallways):
        return {'Triages_Hallway': derived_feature.triagesInHallways,
                'Triages_Rooms': derived_feature.triagesInRooms}

    if isinstance(derived_feature, CountVisitsPerRole):
        # gets counts for role counts per rooms
        features = {}
        for room in derived_feature.roomToRoleToCount.keys():
            for role, count in derived_feature.roomToRoleToCount[room].items():
                features[_change_feature_name(f'Count_{room}_{role}')] = count
        return features

    logging.warning(f'Could not process feature of type: {type(derived_feature)}!')


def _change_feature_name(feature_name: str) -> str:
    feature_name = re.sub(r'Event:', '', feature_name)
    feature_name = re.sub('_*([A-Z][a-z]+)', r' \1', feature_name).strip()
    feature_name = re.sub(' ', '_', feature_name)
    return feature_name.title()


if __name__ == '__main__':
    main()
