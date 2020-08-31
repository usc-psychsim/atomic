import copy
import igraph
import cairo
import numpy as np
import matplotlib.pyplot as plt
from collections import OrderedDict
from igraph import Layout
from igraph.drawing.colors import color_to_html_format
from igraph.drawing.text import TextDrawer
from model_learning.util.io import get_file_changed_extension

from psychsim.agent import Agent
from psychsim.probability import Distribution
from psychsim.pwl import VectorDistributionSet
from psychsim.world import World
from model_learning.util.plot import format_and_save_plot, distinct_colors
from atomic_domain_definitions.features import get_num_victims_location_key, get_num_visits_location_key, \
    get_location_key
from atomic_domain_definitions.locations_no_pre import Directions
from atomic_domain_definitions.multivic import GOLD_STR, GREEN_STR, RED_STR, WHITE_STR

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'

GRAPH_LAYOUT = 'kk'

EDGE_WIDTH = .3
TRAJ_EDGE_WIDTH = .8
EDGE_LABEL_SIZE = 6
EDGE_LABEL_COLOR = 'Gray40'
EDGE_ARROW_SIZE = 0.5
EDGE_ARROW_WIDTH = 1

VERTEX_LABEL_SIZE = 6
VERTEX_LABEL_DIST = 0.25
VERTEX_LABEL_COLOR = 'DimGray'
VERTEX_COLOR = 'white'
VERTEX_SIZE = 35

VIC_LABEL_SIZE = 10
VIC_LABEL_DIST = 0.09
VIC_VERTEX_LABEL_DIST = 0.1

TITLE_FONT_SIZE = 12

DEF_SIZE = 7
PLOT_MARGIN = (50, 50, 50, 50)
LOC_SIZE_FACTOR = 600 / DEF_SIZE

COLORS = {GOLD_STR: 'Goldenrod',  # (255, 215, 0),
          GREEN_STR: 'ForestGreen',  # (34, 139, 34),
          RED_STR: 'Red',  # (255, 0, 0),
          WHITE_STR: 'Gray40'}  # (176, 196, 222)}


def plot(world, locations, neighbors, output_img, coordinates=None,
         state=None, title='Search & Rescue World', draw_victims=True, show=False):
    """
    Generates and saves a graph plot of the environment, including each location and connection.
    :param World world: the world we want to plot.
    :param list[str] locations: the list of possible world locations.
    :param dict[str,dict[int, str]] neighbors: the locations' neighbors in each direction.
    :param str output_img: the path to the file in which to save the plot.
    :param dict[str, tuple[float,float]] coordinates: the coordinates of each world location.
    :param VectorDistributionSet state: the state used to fetch the graph information to be plotted.
    :param str title: the plot's title.
    :param bool draw_victims: whether to include the number of victims of each color in each location of the graph.
    :param bool show: whether to show the plot to the screen.
    :return:
    """
    # creates and prints plot
    _, g_plot = _plot(world, locations, neighbors, output_img, coordinates, state, title, draw_victims)
    _save_plot(g_plot, output_img)
    if show:
        g_plot.show()


def plot_trajectories(agent, locations, neighbors, trajectories, output_img, coordinates=None,
                      state=None, title='Trajectories', draw_victims=True, show=False):
    """
    Plots the given set of trajectories over a graph representation of the environment.
    :param Agent agent: the agent whose trajectories we want to plot.
    :param list[str] locations: the list of possible world locations.
    :param dict[str,dict[int, str]] neighbors: the locations' neighbors in each direction.
    :param list[list[tuple[World, Distribution]]] trajectories: the set of trajectories to save, containing
    several sequences of state-action pairs.
    :param str output_img: the path to the file in which to save the plot.
    :param dict[str, tuple[float,float]] coordinates: the coordinates of each world location.
    :param VectorDistributionSet state: the state used to fetch the graph information to be plotted.
    :param str title: the plot's title.
    :param bool draw_victims: whether to include the number of victims of each color in each location of the graph.
    :param bool show: whether to show the plot to the screen.
    :return:
    """
    g, g_plot = _plot(agent.world, locations, neighbors, output_img, coordinates, state, title, draw_victims)

    if len(trajectories) == 0 or len(trajectories[0]) == 0:
        return

    loc_feat = get_location_key(agent)
    t_colors = distinct_colors(len(trajectories))
    for i, trajectory in enumerate(trajectories):
        state = copy.deepcopy(trajectory[0][0].state)
        state.select(True)
        source = trajectory[0][0].getFeature(loc_feat, state, True)
        for t in range(1, len(trajectory)):
            state = copy.deepcopy(trajectory[t][0].state)
            state.select(True)
            target = trajectory[t][0].getFeature(loc_feat, state, True)
            g.add_edge(source, target, color=color_to_html_format(t_colors[i]),
                       arrow_size=EDGE_ARROW_SIZE, arrow_width=EDGE_ARROW_WIDTH,
                       label_size=EDGE_LABEL_SIZE, label_color=EDGE_LABEL_COLOR, width=TRAJ_EDGE_WIDTH,
                       label='T{:02d}'.format(i) if t == len(trajectory) - 1 else None)
            source = target

    g_plot.redraw()
    _draw_title(title, g_plot.surface, g_plot.width)
    _save_plot(g_plot, output_img)
    if show:
        g_plot.show()


def plot_location_frequencies(agent, locations, output_img, trajectories, title='Location Visitation Frequencies'):
    """
    Generates a plot with the agent's visitation frequency for each location in the environment.
    :param Agent agent: the agent whose visitation frequency we want to plot.
    :param list[str] locations: the list of possible world locations.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param list[list[tuple[World, Distribution]]] trajectories: the set of trajectories containing sequences of
    state-action pairs.
    :param str title: the plot's title.
    :return:
    """
    # gets agent's visitation frequency for all locations
    world = agent.world
    data = np.zeros(len(locations))
    for trajectory in trajectories:
        traj_data = []
        for loc in locations:
            freq_feat = get_num_visits_location_key(agent, loc)
            state = copy.deepcopy(trajectory[-1][0].state)
            state.select(True)
            freq = world.getFeature(freq_feat, state, True)
            traj_data.append(freq)
        data += traj_data
    num_locs = len(data)

    # save to csv
    np.savetxt(get_file_changed_extension(output_img, 'csv'), data.reshape((1, -1)),
               '%s', ',', header=','.join(locations), comments='')

    plt.figure(figsize=(0.4 * num_locs, 6))
    ax = plt.gca()

    colors = distinct_colors(num_locs)
    ax.bar(np.arange(num_locs), data, color=colors, edgecolor='black', linewidth=0.7, zorder=100)
    plt.xticks(np.arange(num_locs), locations, rotation=45, horizontalalignment='right')

    format_and_save_plot(ax, '{}\'s {}'.format(agent.name, title), output_img, '', 'Frequency', False)
    plt.close()


def plot_action_frequencies(agent, output_img, trajectories, title='Action Execution Frequencies'):
    """
    Generates a plot with the agent's action execution frequency for each action in the given trajectories.
    :param Agent agent: the agent whose visitation frequency we want to plot.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param list[list[tuple[World, Distribution]]] trajectories: the set of trajectories containing sequences of
    state-action pairs.
    :param str title: the plot's title.
    :return:
    """
    # gets action execution frequencies
    actions = sorted(agent.actions, key=lambda a: str(a))
    action_names = [str(a).replace('{}-'.format(agent.name), '').replace('_', ' ') for a in actions]
    data = OrderedDict({a: 0 for a in actions})
    for trajectory in trajectories:
        for _, dist in trajectory:
            for a, p in dist.items():
                data[a] += p
    num_acts = len(data)

    # save to csv
    np.savetxt(get_file_changed_extension(output_img, 'csv'), np.array([list(data.values())]), '%s', ',',
               header=','.join(action_names), comments='')

    plt.figure()
    ax = plt.gca()

    colors = distinct_colors(num_acts)
    ax.bar(np.arange(num_acts), data.values(), color=colors, edgecolor='black', linewidth=0.7, zorder=100)
    plt.xticks(np.arange(num_acts), action_names, rotation=45, horizontalalignment='right')

    format_and_save_plot(ax, '{}\'s {}'.format(agent.name, title), output_img, '', 'Frequency', False)
    plt.close()


def _plot(world, locations, neighbors, output_img, coordinates,
          state=None, title='Environment', draw_victims=True):
    """
    :param World world: the world we want to plot.
    :param list[str] locations: the list of possible world locations.
    :param dict[str,dict[int, str]] neighbors: the locations' neighbors in each direction.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param dict[str, tuple[float,float]] coordinates: the coordinates of each world location.
    :param VectorDistributionSet state: the state used to fetch the graph information to be plotted.
    :param str title: the plot's title.
    :param bool draw_victims: whether to include the number of victims of each color in each location of the graph.
    :rtype: tuple[igraph.Graph,igraph.Plot]
    :return: a tuple with the generated graph and plot.
    """
    # create graph and add vertices
    g = igraph.Graph(directed=True)
    g.add_vertices(locations)
    g.vs['label'] = locations
    g.vs['size'] = VERTEX_SIZE
    g.vs['color'] = VERTEX_COLOR
    g.vs['label_color'] = VERTEX_LABEL_COLOR
    g.vs['label_dist'] = VERTEX_LABEL_DIST
    g.vs['label_size'] = VERTEX_LABEL_SIZE

    # add and format edges
    edges = set()
    for loc in locations:
        for direction, neighbor in neighbors[loc].items():
            if (loc, neighbor) not in edges and (neighbor, loc) not in edges:
                g.add_edge(loc, neighbor)
                edges.add((loc, neighbor))

    g.es['width'] = EDGE_WIDTH
    g.es['label_size'] = EDGE_LABEL_SIZE
    g.es['label_color'] = EDGE_LABEL_COLOR
    g.es['arrow_size'] = 0.01
    g.es['arrow_width'] = 0.01

    # gets surface
    coordinates = None if coordinates is None else np.array([coordinates[loc] for loc in locations])
    width, height = _get_dimensions(coordinates)
    layout = _get_layout(g, coordinates)
    width *= LOC_SIZE_FACTOR
    height *= LOC_SIZE_FACTOR
    surface = _get_surface(output_img, int(width), int(height))

    # draws victims
    if draw_victims:
        state = copy.deepcopy(world.state) if state is None else copy.deepcopy(state)
        state.select(True)
        label_start_x = (len(COLORS) * VIC_LABEL_DIST) / 2 - (VIC_LABEL_DIST / 2)
        for loc in locations:
            for i, color in enumerate(COLORS.keys()):
                vic_amount_feat = get_num_victims_location_key(loc, color)
                vic_amount = world.getFeature(vic_amount_feat, state, True)
                v = g.vs.select(label=loc)[0]
                x, y = layout.coords[v.index]
                g.add_vertex(title, label=vic_amount, label_size=VIC_LABEL_SIZE, color=(0, 0, 0, 0),
                             frame_color=(0, 0, 0, 0),
                             label_angle=np.pi / 2, label_color=COLORS[color], label_dist=VIC_VERTEX_LABEL_DIST)
                layout.append((x - label_start_x + VIC_LABEL_DIST * i, y))

    g_plot = igraph.plot(g, surface, margin=PLOT_MARGIN, layout=layout)
    g_plot.redraw()

    _draw_title(title, surface, width)

    return g, g_plot


def _save_plot(g_plot, output_img):
    g_plot.save(output_img if output_img.endswith('png') else None)


def _get_layout(g, coordinates):
    return g.layout(GRAPH_LAYOUT) if coordinates is None else Layout(coordinates.tolist())


def _get_dimensions(coordinates):
    return (DEF_SIZE, DEF_SIZE) if coordinates is None else (coordinates[:, 0].max() + 1, coordinates[:, 1].max() + 1)


def _get_surface(output_img, width, height):
    if output_img.endswith('pdf'):
        return cairo.PDFSurface(output_img, width, height)
    if output_img.endswith('svg'):
        return cairo.SVGSurface(output_img, width, height)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    surface.write_to_png(output_img)
    return surface


def _draw_title(title, surface, width):
    ctx = cairo.Context(surface)
    ctx.set_font_size(TITLE_FONT_SIZE)
    drawer = TextDrawer(ctx, title, halign=TextDrawer.CENTER, valign=TextDrawer.TOP)
    drawer.draw_at(0, PLOT_MARGIN[2] / 3, width=width)
