import argparse
import logging
import os
import tqdm
import re
import itertools as it
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import OrderedDict
from typing import Dict, List
from sklearn import metrics
from sklearn import preprocessing
from sklearn.cluster import AgglomerativeClustering
from atomic.parsing.parse_into_msg_qs import MsgQCreator
from atomic.parsing.count_features import CountAction, CountRoleChanges, CountTriageInHallways, CountEnterExit, Feature, \
    CountVisitsPerRole
from atomic.util.io import str2bool, create_clear_dir, save_args, change_log_handler, get_files_with_extension, \
    get_file_name_without_extension, get_file_changed_extension
from atomic.util.mp import get_pool_and_map
from atomic.util.clustering import hopkins_statistic, get_n_clusters
from atomic.util.plot import plot_clustering_distances, plot_clustering_dendrogram, format_and_save_plot

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Loads a series of game logs (metadata files), performs feature counting, gets set of derived features ' \
           '(stats over the original features) and then clusters files based on this feature embedding distance.'

MAX_VERS = 20  # maximum metadata file version to search for

HALLWAYS = ['ccw', 'cce', 'mcw', 'mce', 'scw', 'sce', 'sccc']

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

SILHOUETTE_COEFFICIENT = 'Silhouette Coefficient'
CALINSKI_HARABASZ_INDEX = 'Calinski-Harabasz Index'
DAVIES_BOULDIN_INDEX = 'Davies-Bouldin Index'


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
    parser.add_argument('--linkage', '-l', type=str, default='ward',
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
    files = _filter_files(files)
    if len(files) == 0:
        raise ValueError(f'Could not find any {LOG_FILE_EXTENSION} files in provided argument: {args.input}!')

    # check cache dir
    cache_dir = os.path.join(args.output, 'data')
    os.makedirs(cache_dir, exist_ok=True)

    # loads data from logs
    logging.info(f'Loading {len(files)} game log files...')
    pool, map_func = get_pool_and_map(args.processes, star=True, iterator=True)
    f_args = list(it.product(files, [cache_dir]))
    results = list(tqdm.tqdm(map_func(_parse_log_file, f_args), total=len(files)))
    results = [result for result in results if result is not None]

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
    df_norm = df.copy()
    df_norm.iloc[:, 1:] = preprocessing.MinMaxScaler().fit_transform(df.iloc[:, 1:].values)  # ignore ID column
    file_path = os.path.join(args.output, 'features-norm.csv')
    logging.info(f'Saving CSV file with all normalized features to {file_path}...')
    df_norm.to_csv(file_path, index=False)

    # split
    features = df.columns[1:]
    file_names = df[FILE_NAME_COL].values
    data = df.iloc[:, 1:].values
    norm_data = df_norm.iloc[:, 1:].values

    logging.info('========================================')
    logging.info('Computing Hopkins statistic for the data...')
    h = hopkins_statistic(norm_data)
    logging.info(f'\tH={h:.2f}')
    if h < 0:
        logging.info('\tInsufficient data to compute Hopkins statistic')
    elif h <= 0.3:
        logging.info('\tData is regularly spaced')
    elif 0.45 <= h <= 0.55:
        logging.info('\tData is random')
    elif h > 0.75:
        logging.info('\tData has a high tendency to cluster')

    # cluster data
    logging.info('========================================')
    logging.info(f'Clustering {norm_data.shape[0]} datapoints...')
    clustering = AgglomerativeClustering(n_clusters=None if args.n_clusters == -1 else args.n_clusters,
                                         affinity=args.affinity if args.linkage != 'ward' else 'euclidean',
                                         linkage=args.linkage,
                                         compute_distances=True,
                                         distance_threshold=args.distance_threshold if args.n_clusters == -1 else None)
    clustering.fit(norm_data)
    logging.info(f'Found {clustering.n_clusters_} clusters at max. distance: {clustering.distance_threshold}')

    # saves clustering results
    clustering_dir = os.path.join(args.output, 'clustering')
    os.makedirs(clustering_dir, exist_ok=True)
    logging.info('========================================')
    logging.info('Saving clustering results...')
    plot_clustering_distances(clustering, os.path.join(clustering_dir, f'clustering-distances.{args.format}'))
    plot_clustering_dendrogram(clustering, os.path.join(clustering_dir, f'clustering-dendrogram.{args.format}'))

    # gets lof files idxs for each cluster
    clusters = {}
    for idx, cluster in enumerate(clustering.labels_):
        if cluster not in clusters:
            clusters[cluster] = []
        clusters[cluster].append(idx)

    df = pd.DataFrame([{CLUSTER_ID_COL: cluster,
                        CLUSTER_COUNT_COL: len(idxs),
                        FILE_NAMES_COL: [file_names[idx] for idx in idxs]}
                       for cluster, idxs in clusters.items()])
    df.set_index([CLUSTER_ID_COL], inplace=True)
    df.sort_index(inplace=True)
    file_path = os.path.join(clustering_dir, 'cluster-ids.csv')
    df.to_csv(file_path)

    logging.info('========================================')
    logging.info('Clusters\' distribution:')
    for cluster, idxs in clusters.items():
        logging.info(f'Cluster {cluster}: {len(idxs)}')

    # saves mean feature vectors
    logging.info('========================================')
    logging.info('Computing mean feature vectors for each cluster...')
    mean_vecs = [[cluster] + np.mean(data[idxs], axis=0).tolist() for cluster, idxs in clusters.items()]
    df = pd.DataFrame(mean_vecs, columns=[CLUSTER_ID_COL] + features.tolist())
    df.set_index([CLUSTER_ID_COL], inplace=True)
    df.sort_index(inplace=True)
    file_path = os.path.join(clustering_dir, 'cluster-mean-feats.csv')
    df.to_csv(file_path)

    # performs internal evaluation
    _internal_evaluation(norm_data, clustering, clustering_dir, args)

    logging.info('Done!')


def _filter_files(files: List[str]) -> List[str]:
    files = set(files)
    filtered = set()
    for file in files:
        if file in filtered or not file.endswith(LOG_FILE_EXTENSION) or not os.path.isfile(file):
            continue
        i = re.search(r'Vers-(\d+)', file)
        if i is None:
            filtered.add(file)  # did not find version info
            continue
        i = int(i.group(1)) + 1  # search for higher version
        for i in range(i, MAX_VERS + 1):
            file_ = re.sub(r'Vers-\d+', f'Vers-{i}', file)
            if file_ in files:
                file = file_
        filtered.add(file)
    return sorted(filtered)


def _get_derived_features(msg_qs: MsgQCreator) -> List[Feature]:
    # processes room names
    all_loc_name = list(msg_qs.jsonParser.rooms.keys())
    main_names = [nm[:nm.find('_')] for nm in all_loc_name if nm.find('_') >= 0]
    main_names = set(main_names + [nm for nm in all_loc_name if nm.find('_') < 0])
    room_names = main_names.difference(HALLWAYS)

    # adds feature counters
    derived_features = []
    for args in COUNT_ACTIONS_ARGS:
        derived_features.append(CountAction(*args))
    derived_features.append(CountEnterExit(room_names.copy()))
    derived_features.append(CountTriageInHallways(HALLWAYS))
    derived_features.append(CountVisitsPerRole(room_names))
    # derived_features.append(CountRoleChanges())
    return derived_features


def _parse_log_file(log_file: str, cache_dir: str) -> Dict[str, float] or None:
    try:
        # check file in cache, load and skip if exits
        file_path = os.path.join(cache_dir, f'{get_file_name_without_extension(log_file)}.csv')
        if os.path.isfile(file_path):
            df = pd.read_csv(file_path)
            return df.iloc[0].to_dict()

        msg_qs = MsgQCreator(log_file, logger=logging)
        derived_features = _get_derived_features(msg_qs)

        # process messages
        msg_qs.startProcessing(derived_features, msg_types=None)  # use all msg types available

        # processes data to extract features depending on type of count
        features = {FILE_NAME_COL: get_file_name_without_extension(log_file)}
        for derived_feature in derived_features:
            features.update(_get_feature_values(derived_feature))

        # save to output (cache)
        df = pd.DataFrame([features])
        df.to_csv(file_path, index=False)

        return features
    except (KeyError, AttributeError, ValueError, UnboundLocalError) as e:
        logging.info(f'Could not process log file {log_file}, {e}!')
        return None


def _get_feature_values(derived_feature: Feature) -> Dict[str, float]:
    if isinstance(derived_feature, CountAction) or \
            isinstance(derived_feature, CountEnterExit) or \
            isinstance(derived_feature, CountRoleChanges):
        # get feature name
        feature_name = derived_feature.type_to_count if isinstance(derived_feature, CountAction) \
            else f'Enter_Exit' if isinstance(derived_feature, CountEnterExit) \
            else f'Role_Changes' if isinstance(derived_feature, CountRoleChanges) \
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
        # gets mean counts for visits (time really) per role across rooms
        counts_per_role = {}
        for room in derived_feature.roomToRoleToCount.keys():
            for role, count in derived_feature.roomToRoleToCount[room].items():
                if role not in counts_per_role:
                    counts_per_role[role] = []
                counts_per_role[role].append(count)
        features = {}
        for role, counts in counts_per_role.items():
            feature_name = _change_feature_name(f'Visits_Room_{role}')
            data = pd.DataFrame(counts)
            if len(data) == 0:
                continue
            data = data[0].describe().fillna(0)
            features.update({f'{feature_name}_{k.title()}': v for k, v in data.to_dict().items()})
        return features

    logging.warning(f'Could not process feature of type: {type(derived_feature)}!')


def _change_feature_name(feature_name: str) -> str:
    feature_name = re.sub(r'Event:', '', feature_name)
    feature_name = re.sub('_*([A-Z][a-z]+)', r' \1', feature_name).strip()
    feature_name = re.sub(' ', '_', feature_name)
    return feature_name.title()


def _plot_evaluation(metric: str, scores: Dict[int, Dict[int, float]], output_img: str, save_csv: bool = True):
    """
    Saves a line plot with the scores for different number of clusters for some evaluation metric.
    :param str metric: the name of the evaluation metric.
    :param Dict[int, Dict[int, float]] scores: the metric scores for each number of clusters.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param bool save_csv: whether to save a CSV file with the results.
    :return:
    """
    # saves csv with metric scores
    if save_csv and output_img is not None:
        df = pd.DataFrame({'Num. clusters': scores.keys(), metric: scores.values()})
        df.to_csv(get_file_changed_extension(output_img, 'csv'), index=False)

    # plots distances
    plt.figure()
    plt.plot(scores.keys(), scores.values())
    format_and_save_plot(plt.gca(), metric, output_img, x_label='Num. Clusters', show_legend=False)


def _internal_evaluation(data: np.ndarray, clustering: AgglomerativeClustering, clustering_dir: str, args):
    sub_dir = os.path.join(clustering_dir, 'internal eval')
    os.makedirs(sub_dir, exist_ok=True)

    # performs internal evaluation using different metrics and num. clusters
    logging.info('========================================')
    max_clusters = max(clustering.n_clusters_, args.eval_clusters)
    logging.info(f'Performing internal evaluation for up to {max_clusters} clusters, saving results in "{sub_dir}"...')
    n_clusters = get_n_clusters(clustering, 2, max_clusters)
    evals = {
        SILHOUETTE_COEFFICIENT: OrderedDict(),
        CALINSKI_HARABASZ_INDEX: OrderedDict(),
        DAVIES_BOULDIN_INDEX: OrderedDict()
    }
    for n, labels in tqdm.tqdm(n_clusters.items()):
        evals[SILHOUETTE_COEFFICIENT][n] = metrics.silhouette_score(data, labels, metric='cosine')
        evals[CALINSKI_HARABASZ_INDEX][n] = metrics.calinski_harabasz_score(data, labels)
        evals[DAVIES_BOULDIN_INDEX][n] = metrics.davies_bouldin_score(data, labels)

    # saves plots for each metric with scores for diff. num clusters
    for metric, scores in evals.items():
        file_path = os.path.join(sub_dir, f'{metric.lower().replace(" ", "-")}.{args.format}')
        _plot_evaluation(metric, scores, file_path, True)


if __name__ == '__main__':
    main()
