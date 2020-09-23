import os
import numpy as np
import pandas as pd

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'


def load_cluster_reward_weights(filename):
    """
    Loads the linear reward weights for a set of clusters from a CSV file.
    :param str filename: the path to the file from which to load the reward weights.
    :rtype: dict[str, np.ndarray]
    :return: a dictionary containing entries in the form `cluster_id` -> `reward_weights`.
    """
    assert os.path.isfile(filename), 'Could not found CSV file at {}'.format(filename)
    data = pd.read_csv(filename, index_col=0)
    return {idx: np.array(row) for idx, row in data.iterrows()}
