import colorsys
import copy
import matplotlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.legend_handler import HandlerTuple
from matplotlib.lines import Line2D
from scipy.cluster.hierarchy import dendrogram
from sklearn.cluster import AgglomerativeClustering
from atomic.util.io import get_file_changed_extension

__author__ = 'Pedro Sequeira'
__email__ = 'pedro.sequeira@sri.com'

TITLE_FONT_SIZE = 10


def plot_bar(data, title, output_img=None, colors=None, plot_mean=True, plot_error=True, x_label='', y_label='',
             show_legend=False, horiz_grid=True, show=False):
    """
    Plots the given data as a bar-chart, assumed to be a collection of key-value pairs.
    :param dict[str, float or (float,float)] data: the data to be plotted.
    :param str title: the title of the plot.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param np.ndarray or None colors: an array of shape (num_variables, 3) containing colors for each variable in the
    [R, G, B] normalized format ([0-1]). If `None`, colors will be automatically generated.
    :param bool plot_mean: whether to plot a horizontal line across the bar chart denoting the mean of the values.
    :param bool plot_error: whether to plot error bars (requires input `data` to be 2-dimensional for each entry).
    :param str x_label: the label of the X axis.
    :param str y_label: the label of the Y axis.
    :param bool show_legend: whether to show a legend. If `False`, data labels will be placed on tick marks.
    :param bool horiz_grid: whether to show an horizontal grid.
    :param bool show: whether to show the plot on the screen.
    :return:
    """
    data_size = len(data)
    labels = list(data.keys())
    values = np.array([data[key] if isinstance(data[key], tuple) or isinstance(data[key], list) else [data[key]]
                       for key in labels]).T

    # save to csv
    np.savetxt(get_file_changed_extension(output_img, 'csv'), values, '%s', ',', header=','.join(labels), comments='')

    # automatically get colors
    if colors is None:
        colors = distinct_colors(data_size)

    # create bar chart with mean and error-bars
    plt.figure(figsize=(max(8., 0.4 * data_size), 6))
    ax = plt.gca()
    if plot_error and values.shape[0] > 1:
        ax.bar(np.arange(data_size), values[0], yerr=values[1], capsize=2, error_kw={'elinewidth': .75},
               color=colors, edgecolor='black', linewidth=0.7, zorder=100)
    else:
        ax.bar(np.arange(data_size), values[0], color=colors, edgecolor='black', linewidth=0.7, zorder=100)

    if plot_mean:
        ax.axhline(y=np.mean(values[0]), label='Mean', c='black', ls='--')

    if show_legend:
        # add custom legend on the side
        plt.xticks([])
        patches = []
        for i, color in enumerate(colors):
            patches.append(mpatches.Patch(color=color, label=labels[i]))
        leg = plt.legend(handles=patches, loc='right', fancybox=False)
        leg.get_frame().set_edgecolor('black')
        leg.get_frame().set_linewidth(0.8)
    else:
        # show data labels in tick marks
        short_labels = max(len(label) for label in labels) <= 8
        rotation = 0 if short_labels else 45
        align = 'center' if short_labels else 'right'
        plt.xticks(np.arange(data_size), labels, rotation=rotation, horizontalalignment=align)

    format_and_save_plot(ax, title, output_img, x_label, y_label, False, horiz_grid, show)
    plt.close()


def plot_clustering_distances(clustering, file_path):
    """
    Saves a plot with the clustering distances resulting from the given clustering algorithm.
    :param AgglomerativeClustering clustering: the clustering algorithm with the resulting distances.
    :param str file_path: the path to the file in which to save the plot.
    :return:
    """
    # saves csv with distances
    num_clusters = np.flip(np.arange(len(clustering.distances_) + 1) + 1)
    distances = np.hstack(([0], clustering.distances_))
    np.savetxt(get_file_changed_extension(file_path, 'csv'), np.column_stack((num_clusters, distances)), '%s', ',',
               header='Num. Clusters,Distance', comments='')

    # plots distances
    plt.figure()
    plt.plot(num_clusters, distances)
    plt.xlim(num_clusters[0], num_clusters[-1])  # invert for more natural view of hierarchical clustering
    plt.ylim(ymin=0)
    plt.axvline(x=clustering.n_clusters_, c='red', ls='--', lw=1)
    format_and_save_plot(plt.gca(), 'Traces Clustering Distance', file_path,
                         x_label='Num. Clusters', show_legend=False)


def plot_clustering_dendrogram(clustering, file_path, labels=None):
    """
    Saves a dendrogram plot with the clustering resulting from the given model.
    :param AgglomerativeClustering clustering: the clustering algorithm with the resulting labels and distances.
    :param str file_path: the path to the file in which to save the plot.
    :param list[str] labels: a list containing a label for each clustering datapoint. If `None`, the cluster of each
    datapoint is used as label.
    :return:
    """
    # saves linkage info to csv
    linkage_matrix = get_linkage_matrix(clustering)
    np.savetxt(get_file_changed_extension(file_path, 'csv'), linkage_matrix, '%s', ',',
               header='Child 0, Child 1, Distance, Leaf Count', comments='')

    # saves dendrogram plot
    labels = [str(c) for c in clustering.labels_] if labels is None else labels
    dendrogram(linkage_matrix, clustering.n_clusters_, 'level', clustering.distance_threshold,
               labels=labels, leaf_rotation=45 if max(len(l) for l in labels) > 8 else 0, leaf_font_size=8)
    dist_thresh = clustering.distances_[len(clustering.distances_) - clustering.n_clusters_ + 1] \
        if clustering.distance_threshold is None else clustering.distance_threshold
    plt.axhline(y=dist_thresh, c='red', ls='--', lw=1)
    format_and_save_plot(plt.gca(), 'Traces Clustering Dendrogram', file_path, show_legend=False)


def plot_confusion_matrix(matrix, output_img, save_csv=True,
                          x_labels=None, y_labels=None, color_map=None, title='',
                          x_label='', y_label='', vmin=None, vmax=None, colorbar=True, rasterized=False):
    """
    Plots the given confusion matrix.
    :param np.ndarray matrix: the confusion matrix to be plotted.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param bool save_csv: whether to save a CSV file with the confusion matrix.
    :param list[str] x_labels: the labels for the elements in the X-axis.
    :param list[str] y_labels: the labels for the elements in the Y-axis.
    :param str or None color_map: the colormap to be used.
    :param str title: the plot's title.
    :param str x_label: the label of the X axis.
    :param str y_label: the label of the Y axis.
    :param float vmin: the colorbar minimal value. The true minimum will be used if set to `None`.
    :param float vmax: the colorbar maximal value. The true maximum will be used if set to `None`.
    :param bool colorbar: whether to plot colobar.
    :param bool rasterized: whether to rasterize the pcolormesh when drawing vector graphics.
    :return:
    """
    # saves matrix to csv
    if save_csv and output_img is not None:
        pd.DataFrame(matrix, y_labels, x_labels).to_csv(get_file_changed_extension(output_img, 'csv'))

    # save grid/heatmap plot
    if x_labels or y_labels is None:
        fig, ax = plt.subplots()
    else:
        fig, ax = plt.subplots(figsize=(max(8., len(x_labels) * .5), max(6., len(y_labels) * 6 / 16)))
    color_map = copy.copy(matplotlib.cm.get_cmap(color_map))
    color_map.set_under('w')
    color_map.set_over('w')
    plt.pcolormesh(matrix, cmap=color_map, edgecolors=None, linewidth=0.1, vmax=vmax, vmin=vmin, rasterized=rasterized)
    if x_labels is not None:
        tilt = max(map(len, x_labels)) > 10
        plt.xticks(np.arange(len(x_labels)) + 0.5, x_labels,
                   rotation=45 if tilt else 0,
                   horizontalalignment='right' if tilt else 'center')
    if y_labels is not None:
        plt.yticks(np.arange(len(y_labels)) + 0.5, y_labels)
    ax.invert_yaxis()
    ax.xaxis.tick_top()
    ax.set_aspect('equal')
    if colorbar:
        plt.colorbar()
    format_and_save_plot(ax, title, output_img, x_label, y_label, False, False)


def get_linkage_matrix(clustering):
    """
    Gets a linkage matrix from the `sklearn` clustering model.
    See: https://scikit-learn.org/stable/auto_examples/cluster/plot_agglomerative_dendrogram.html
    :param AgglomerativeClustering clustering: the clustering model.
    :return:
    """
    # create the counts of samples under each node
    counts = np.zeros(clustering.children_.shape[0])
    n_samples = len(clustering.labels_)
    for i, merge in enumerate(clustering.children_):
        current_count = 0
        for child_idx in merge:
            if child_idx < n_samples:
                current_count += 1  # leaf node
            else:
                current_count += counts[child_idx - n_samples]
        counts[i] = current_count

    return np.column_stack([clustering.children_, clustering.distances_, counts]).astype(float)


def format_and_save_plot(ax, title, output_img=None, x_label='', y_label='',
                         show_legend=True, horiz_grid=True, show=False):
    """
    Utility function that formats a plot and saves it to a file. Also closes the current plot.
    This gives the generated plots a uniform look-and-feel across the library.
    :param ax: the plot axes to be formatted.
    :param str title: the plot's title.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param str x_label: the label of the X axis.
    :param str y_label: the label of the Y axis.
    :param bool show_legend: whether to show the legend.
    :param bool horiz_grid: whether to show an horizontal grid.
    :param bool show: whether to show the plot on the screen.
    :return:
    """

    plt.title(title)  # , fontweight='bold', fontsize=TITLE_FONT_SIZE)
    ax.set_xlabel(x_label)  # , fontweight='bold')
    ax.set_ylabel(y_label)  # , fontweight='bold')
    if horiz_grid:
        ax.yaxis.grid(True, which='both', linestyle='--', color='lightgrey')
    if show_legend:
        leg = plt.legend(fancybox=False)
        leg.get_frame().set_edgecolor('black')
        leg.get_frame().set_linewidth(0.8)

    if output_img is not None:
        plt.savefig(output_img, pad_inches=0, bbox_inches='tight', dpi=600)
    if show:
        plt.show()
    plt.close()


def gradient_line_legend(color_maps, labels, num_points=10, handle_length=3):
    """
    Creates a legend where each entry is a gradient color line.
    :param list color_maps: the color maps used in the legend.
    :param list[str] labels: the labels of the legend entries.
    :param int num_points: the number of points used to create the gradient.
    :param int handle_length: the length of the legend line entries.
    """
    assert len(color_maps) == len(labels), 'Number of color maps has to be the same as that of labels!'
    color_space = np.linspace(0, 1, num_points)
    lines = []
    for c_map in color_maps:
        lines.append(tuple(Line2D([], [], marker='s', markersize=handle_length, c=c_map(c)) for c in color_space))

    plt.legend(lines, labels, numpoints=1,
               handler_map={tuple: HandlerTuple(ndivide=None)},
               handlelength=handle_length)


def distinct_colors(n):
    """
    Generates N visually-distinct colors.
    :param int n: the number of colors to generate.
    :rtype: np.ndarray
    :return: an array of shape (n, 3) with colors in the [R, G, B] normalized format ([0-1]).
    """
    return np.array([[x for x in colorsys.hls_to_rgb(i / n, .65, .9)] for i in range(n)])
