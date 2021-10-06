import argparse
import logging
import os
import tqdm
import itertools as it
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import OrderedDict
from typing import Dict, List
from sklearn import metrics
from sklearn import preprocessing
from sklearn.cluster import AgglomerativeClustering
from atomic.util.io import str2bool, create_clear_dir, save_args, change_log_handler, get_file_changed_extension
from atomic.util.clustering import hopkins_statistic, get_n_clusters
from atomic.util.plot import plot_clustering_distances, plot_clustering_dendrogram, format_and_save_plot

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Loads a series of game logs (metadata files), performs feature counting, gets set of derived features ' \
           '(stats over the original features) and then clusters files based on this feature embedding distance.'

IGNORE_FEATURES = ['Marker Legend']

TRIAL_COL = 'Trial'
TEAM_COL = 'Team'
MAP_COL = 'CondWin'
PARTICIPANT_COL = 'Participant'
TIME_COL = 'time'
LAST_META_COL = TIME_COL

CLUSTER_ID_COL = 'Cluster'
CLUSTER_COUNT_COL = 'Cluster Count'
FILE_NAMES_COL = 'Files'

SILHOUETTE_COEFFICIENT = 'Silhouette Coefficient'
CALINSKI_HARABASZ_INDEX = 'Calinski-Harabasz Index'
DAVIES_BOULDIN_INDEX = 'Davies-Bouldin Index'


def main():
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', type=str, required=True,
                        help='The path to the CSV file containing the individual- and team-level count features.')
    parser.add_argument('--output', '-o', type=str, required=True, help='Directory in which to save results.')
    parser.add_argument('--map', type=str,
                        help='World map trials to be analyzed.')
    parser.add_argument('--trial', type=int, default=-1,
                        help='Trial number to analyze for each team. -1 ignores the trial filter.')
    parser.add_argument('--format', '-f', type=str, default='png', help='Format of resulting images.')

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
                        help='Maximum number of clusters for which to perform evaluation.')

    parser.add_argument('--clear', '-c', type=str2bool, default="False",
                        help='Clear output directories before generating results.')
    parser.add_argument('--verbosity', '-v', type=int, default=0, help='Verbosity level.')
    args = parser.parse_args()

    # prepares output dir and log
    create_clear_dir(args.output, args.clear)
    save_args(args, os.path.join(args.output, 'args.json'))
    change_log_handler(os.path.join(args.output, 'cluster-features.log'), args.verbosity)

    # checks CSV file
    logging.info('========================================')
    if args.input is None or not os.path.isfile(args.input):
        raise ValueError(f'Could not find input CSV in: {args.input}!')

    # read dataframe
    df = pd.read_csv(args.input)
    if len(df) == 0:
        raise ValueError(f'No data loaded from input CSV file: {args.input}!')
    logging.info(f'Loaded {len(df)} records from input CSV file: {args.input}')

    # filter data and transforms / gets stats from players' data
    df = _filter_data(df, args)
    start_idx = list(df.columns).index(LAST_META_COL) + 1
    df = _transform_data(df, start_idx)

    # merge dataframes and saves to file
    logging.info('========================================')
    logging.info(f'Finished processing data, got {len(df.columns) - start_idx + 1} features for {len(df)} files.')
    file_path = os.path.join(args.output, 'features.csv')
    logging.info(f'Saving CSV file with all features to {file_path}...')
    df.to_csv(file_path, index=False)

    # normalize data
    logging.info('========================================')
    logging.info('Normalizing data...')
    df_norm = df.copy()
    df_norm.iloc[:, start_idx:] = preprocessing.MinMaxScaler().fit_transform(df.iloc[:, start_idx:].values)
    file_path = os.path.join(args.output, 'features-norm.csv')
    logging.info(f'Saving CSV file with all normalized features to {file_path}...')
    df_norm.to_csv(file_path, index=False)

    # split data
    features = df.columns[start_idx:].tolist()
    metadata = df.iloc[:, :start_idx]
    data = df.iloc[:, start_idx:].values
    norm_data = df_norm.iloc[:, start_idx:].values

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
    else:
        logging.info('\tData does not have high tendency to cluster')

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

    clustering_dir = os.path.join(args.output, 'clustering')
    clusters = _save_clustering_results(data, clustering, clustering_dir, features, metadata, args)

    # performs internal evaluation
    _internal_evaluation(norm_data, clustering, clustering_dir, args)

    # analyzes feature importance
    _analyze_cluster_features(norm_data, clusters, clustering_dir, features)

    logging.info('Done!')


def _filter_data(df, args):
    # first remove all unwanted features/columns
    df = df.drop(IGNORE_FEATURES, axis=1)
    
    # filter by trial for each team
    if args.trial >= 0:
        logging.info(f'Filtering data by selecting trial="{args.trial}"...')
        teams_dfs = []
        for _, team_df in df.groupby(TEAM_COL):
            trials = sorted(team_df[TRIAL_COL].unique())
            if len(trials) > args.trial:
                team_df = team_df[team_df[TRIAL_COL] == trials[args.trial]]
                teams_dfs.append(team_df)
        df = pd.concat(teams_dfs)

    # filter by map
    if args.map is not None and args.map != '':
        logging.info(f'Filtering data by selecting map="{args.map}"...')
        df = df[df[MAP_COL] == args.map]

    return df


def _transform_data(df, start_idx):
    # transform data
    # first gets all team-level data, filter columns with all NaNs and fills other Nan with zero
    logging.info('========================================')
    logging.info('Selecting and processing team data...')
    teams_df = df[df[PARTICIPANT_COL] == 'Team']
    teams_df = teams_df.dropna(axis=1, how='all')
    teams_df = _one_hot_encode_cols(teams_df, start_idx)
    teams_df = teams_df.fillna(0)
    logging.info(f'Got data for {len(teams_df)} teams and {len(teams_df.columns) - start_idx + 1} features')

    # do the same for the player data
    logging.info('Selecting and processing players\' data...')
    players_df = df[df[PARTICIPANT_COL] != 'Team']
    players_df = players_df.dropna(axis=1, how='all')
    players_df = _one_hot_encode_cols(players_df, start_idx)
    players_df = players_df.fillna(0)

    # get statistics for all players in each team and create new features
    logging.info('Getting stats features from players\' data...')
    teams_dfs = []
    for trial, team_df in tqdm.tqdm(players_df.groupby(TRIAL_COL)):
        team_data = {TRIAL_COL: trial}
        for feat in team_df.columns.difference(teams_df.columns):
            feat_data = team_df[feat].describe().fillna(0)
            team_data.update({f'{feat}_{k.title()}': v for k, v in feat_data.to_dict().items()})
        teams_dfs.append(pd.DataFrame([team_data]))
    teams_stats_df = pd.concat(teams_dfs)
    logging.info(f'Got data for {len(teams_stats_df)} teams and {len(teams_stats_df.columns) - 1} features')

    # merge team data with team stats data
    return pd.merge(teams_df, teams_stats_df, on=TRIAL_COL, how='inner')


def _one_hot_encode_cols(df, start_idx):
    # transforms categorical data into one-hot encodings
    new_cols = {}
    for col, d_type in df.dtypes[start_idx:].iteritems():
        if d_type == object:
            one_hot_df = pd.get_dummies(df[col], prefix=col)
            new_cols[col] = one_hot_df
    df = df.drop(new_cols.keys(), axis=1)
    df = pd.concat([df] + list(new_cols.values()), axis=1)
    return df


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


def _save_clustering_results(data: np.ndarray, clustering: AgglomerativeClustering, clustering_dir: str,
                             features: List[str], metadata: pd.DataFrame, args: argparse.Namespace):
    # saves clustering results
    os.makedirs(clustering_dir, exist_ok=True)
    logging.info('========================================')
    logging.info('Saving clustering results...')
    plot_clustering_distances(clustering, os.path.join(clustering_dir, f'clustering-distances.{args.format}'))
    plot_clustering_dendrogram(clustering, os.path.join(clustering_dir, f'clustering-dendrogram.{args.format}'))

    # gets log files idxs for each cluster
    clusters = {}
    for idx, cluster in enumerate(clustering.labels_):
        if cluster not in clusters:
            clusters[cluster] = []
        clusters[cluster].append(idx)

    df = metadata.copy()
    df[CLUSTER_ID_COL] = -1
    df[CLUSTER_COUNT_COL] = -1
    for cluster, idxs in clusters.items():
        df.loc[idxs, CLUSTER_ID_COL] = cluster
        df.loc[idxs, CLUSTER_COUNT_COL] = len(idxs)
    file_path = os.path.join(clustering_dir, 'clusters.csv')
    df.to_csv(file_path, index=False)

    logging.info('========================================')
    logging.info('Clusters\' distribution:')
    for cluster, idxs in clusters.items():
        logging.info(f'Cluster {cluster}: {len(idxs)}')

    # saves mean feature vectors
    logging.info('========================================')
    logging.info('Computing mean feature vectors for each cluster...')
    mean_vecs = [[cluster] + np.mean(data[idxs], axis=0).tolist() for cluster, idxs in clusters.items()]
    df = pd.DataFrame(mean_vecs, columns=[CLUSTER_ID_COL] + features)
    df.set_index([CLUSTER_ID_COL], inplace=True)
    df.sort_index(inplace=True)
    file_path = os.path.join(clustering_dir, 'cluster-mean-feats.csv')
    df.to_csv(file_path)

    return clusters


def _internal_evaluation(data: np.ndarray, clustering: AgglomerativeClustering, clustering_dir: str,
                         args: argparse.Namespace):
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


def _analyze_cluster_features(norm_data: np.ndarray, clusters: Dict[int, List[int]], clustering_dir: str,
                              features: List[str]):
    # gets pairwise component distances
    logging.info('========================================')
    logging.info('Calculating inter-cluster pairwise distances...')
    cluster_embeds = {c: [norm_data[idx] for idx in idxs] for c, idxs in clusters.items()}
    clusters = list(cluster_embeds.keys())
    num_clusters = len(clusters)
    mean_embed_diffs = 0.
    embed_count = 0
    for i in range(num_clusters):
        logging.info(f'Processing cluster {i}...')
        c_i = clusters[i]
        len_c_i = len(cluster_embeds[c_i])
        for j in range(i + 1, num_clusters):
            c_j = clusters[j]
            len_c_j = len(cluster_embeds[c_j])
            for k, l in tqdm.tqdm(it.product(range(len_c_i), range(len_c_j)), total=len_c_i * len_c_j):
                if k == l:
                    continue
                dist = (cluster_embeds[c_i][k] - cluster_embeds[c_j][l]) ** 2
                mean_embed_diffs = (mean_embed_diffs * embed_count + dist) / (embed_count + 1)
                embed_count += 1

    # gets mean component distances across all pairs of all clusters
    logging.info('========================================')
    df = pd.DataFrame(zip(features, mean_embed_diffs), columns=['Feature', 'Mean Difference'])
    df.sort_values('Mean Difference', ascending=False, inplace=True)
    logging.info('Top-10 features:')
    logging.info(df.iloc[:10])

    logging.info('========================================')
    file_path = os.path.join(clustering_dir, 'feat-diffs.csv')
    logging.info(f'Saving mean features differences to: {file_path}...')
    df.to_csv(file_path, index=False)


if __name__ == '__main__':
    main()
