import copy
import logging
import queue
import numpy as np
import itertools as it
from collections import OrderedDict
from typing import Dict
from sklearn.cluster import AgglomerativeClustering
from sklearn.neighbors import NearestNeighbors

__author__ = 'Pedro Sequeira'
__email__ = 'pedro.sequeira@sri.com'


def hopkins_statistic(datapoints: np.ndarray, seed: float = 0) -> float:
    """
    Compute Hopkins statistic [1] for the given datapoints for measuring clustering tendency of data.
    Source: https://github.com/prathmachowksey/Hopkins-Statistic-Clustering-Tendency/blob/master/Hopkins-Statistic-Clustering-Tendency.ipynb
    References:
        - [1] Lawson, R. G., & Jurs, P. C. (1990). New index for clustering tendency and its application to chemical
    problems. Journal of chemical information and computer sciences, 30(1), 36-41.
    https://pubs.acs.org/doi/abs/10.1021/ci00065a010
    :param np.ndarray datapoints: the data for which to compute the Hopkins statistic shaped (n_points, n_features).
    :param float seed: the seed for the RNG used to sample points and generate uniformly distributed points.
    :rtype: float
    :return: the Hopkins's statistic for the given dataset, a value in [0,1] where a value close to 1 tends to indicate
    the data is highly clustered, random data will tend to result in values around 0.5, and uniformly distributed data
    will tend to result in values close to 0.
    """
    rng = np.random.RandomState(seed)
    sample_size = int(datapoints.shape[0] * 0.05)  # 0.05 (5%) based on paper by Lawson and Jurs
    if sample_size == 0:
        return -1

    # a uniform random sample in the original data space
    simulated_points = rng.uniform(np.min(datapoints, axis=0), np.max(datapoints, axis=0),
                                   (sample_size, datapoints.shape[1]))

    # a random sample of size sample_size from the original data X
    random_indices = rng.choice(np.arange(datapoints.shape[0]), sample_size)
    sample_points = datapoints[random_indices]

    # initialise unsupervised learner for implementing neighbor searches
    neigh = NearestNeighbors(n_neighbors=2)
    nbrs = neigh.fit(datapoints)

    # u_distances = nearest neighbour distances from uniform random sample
    u_distances, u_indices = nbrs.kneighbors(simulated_points, n_neighbors=2)
    u_distances = u_distances[:, 0]  # distance to the first (nearest) neighbour

    # w_distances = nearest neighbour distances from a sample of points from original data X
    w_distances, w_indices = nbrs.kneighbors(sample_points, n_neighbors=2)
    # distance to the second nearest neighbour (as the first neighbour will be the point itself, with distance = 0)
    w_distances = w_distances[:, 1]

    u_sum = np.sum(u_distances)
    w_sum = np.sum(w_distances)

    # compute and return hopkins' statistic
    return u_sum / (u_sum + w_sum)


def update_clusters(clustering: AgglomerativeClustering, new_distance_threshold: float):
    """
    Updates the cluster labels for each datapoint to be consistent with the algorithm's hierarchy and given distance
    threshold. Useful when we already ran the HAC algorithm to determine the points' hierarchy but want to change the
    threshold at which the number of clusters is found.
    :param AgglomerativeClustering clustering: the clustering algorithm with the distances
    :param float new_distance_threshold: the new distance threshold at which the number of clusters is to be determined.
    :return:
    """
    clustering.distance_threshold = new_distance_threshold
    clustering.labels_ = np.full_like(clustering.labels_, -1, dtype=int)
    _update_clusters(clustering)
    clustering.labels_ = np.max(clustering.labels_) - clustering.labels_  # invert to follow natural order
    clustering.n_clusters_ = int(np.max(clustering.labels_) + 1)


def _update_clusters(clustering: AgglomerativeClustering):
    node_q = queue.Queue()
    node_q.put(len(clustering.children_) - 1)  # work backwards from last node/cluster
    cluster_q = queue.Queue()
    cluster_q.put(0)
    num_clusters = 1
    while not node_q.empty():
        # check to see if we need to split node (if above distance threshold)
        cur_node = node_q.get()
        cur_cluster = cluster_q.get()
        dist = clustering.distances_[cur_node]
        for i, child in enumerate(clustering.children_[cur_node]):
            if i > 0 and dist > clustering.distance_threshold:
                num_clusters += 1
                cur_cluster = num_clusters - 1
            if child < clustering.n_leaves_:
                clustering.labels_[child] = cur_cluster  # child is leaf, assign label
            else:
                node_q.put(child - clustering.n_leaves_)  # child is parent, put in queue
                cluster_q.put(cur_cluster)


def get_sorted_indexes(clustering: AgglomerativeClustering) -> np.ndarray:
    """
    Gets the indexes of the datapoints sorted according to the hierarchy imposed by the given HAC algorithm, i.e.,
    same cluster points will have contiguous indexes and closer points will have a closer index.
    :param AgglomerativeClustering clustering: the clustering result containing the points hierarchy.
    :rtype: np.ndarray
    :return: an array containing the indexes of the datapoints sorted according to the given HAC structure.
    """
    q = queue.Queue()
    q.put(len(clustering.children_) - 1)  # work backwards from last node/cluster
    clusters_idxs = []
    while not q.empty():
        cur_node = q.get()
        for child in clustering.children_[cur_node]:
            if child < clustering.n_leaves_:
                cluster = clustering.labels_[child]
                clusters_idxs.append((cluster, child))  # child is leaf, add to list
            else:
                q.put(child - clustering.n_leaves_)  # child is parent, put in queue

    # groups by cluster, then use clustering order with each cluster
    idxs = []
    for cluster, group in it.groupby(sorted(clusters_idxs), lambda x: x[0]):
        idxs.extend(reversed([idx for cluster, idx in group]))  # closest first
    return np.array(idxs)


def get_distance_num_clusters(clustering: AgglomerativeClustering, n_clusters: int) -> float:
    return clustering.distances_[-1] + 1. if n_clusters <= 1 else \
        clustering.distances_[len(clustering.distances_) - n_clusters]


def get_n_clusters(clustering: AgglomerativeClustering, n_min: int = 1, n_max: int = 7) -> Dict[int, np.ndarray]:
    """
    Gets clusters (datapoints labels) for a range of different number of clusters given the HAC result.
    :param AgglomerativeClustering clustering: the clustering result containing the hierarchical structure.
    :param int n_min: the minimum number of clusters for which to get the datapoints labels.
    :param int n_max: the maximum number of clusters for which to get the datapoints labels.
    :rtype: Dict[int, np.ndarray]
    :return: an ordered dictionary containing the datapoints' cluster labels for the different number of clusters.
    """
    n_cluster_labels = OrderedDict()
    for n in np.arange(n_min, n_max + 1):
        clustering = copy.copy(clustering)
        clustering.distances_ = np.arange(len(clustering.distances_))  # fake distances , keep structure (children)
        dist = get_distance_num_clusters(clustering, n)
        update_clusters(clustering, dist)
        if clustering.n_clusters_ != n:
            logging.warning(f'Num. resulting clusters {clustering.n_clusters_} != intended: {n}')
        n_cluster_labels[n] = clustering.labels_
    return n_cluster_labels
