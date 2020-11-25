import copy
import igraph
import cairo
import numpy as np
from collections import OrderedDict
from igraph import Layout
from igraph.drawing.colors import color_to_html_format
from igraph.drawing.text import TextDrawer
from psychsim.agent import Agent
from psychsim.probability import Distribution
from psychsim.pwl import VectorDistributionSet
from psychsim.world import World
from model_learning.util.plot import distinct_colors, plot_bar
from atomic.definitions.features import get_num_victims_location_key, get_location_key
from atomic.definitions.victims import GOLD_STR, GREEN_STR, RED_STR, WHITE_STR
from atomic.model_learning.stats import get_location_frequencies, get_action_frequencies

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


def plot_environment(world, locations, neighbors, output_img, coordinates=None,
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


def plot_trajectories(agents, trajectories, locations, neighbors, output_img, coordinates=None, state=None,
                      title='Trajectories', draw_victims=True, show=False):
    """
    Plots the given set of trajectories over a graph representation of the environment.
    :param Agent or list[Agent] agents: the agent or agents (one per trajectory) whose trajectories we want to plot.
    :param list[list[tuple[World, Distribution]]] trajectories: the set of trajectories to save, containing
    several sequences of state-action pairs.
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
    multiagent = True
    if isinstance(agents, Agent):
        multiagent = False
        agents = [agents] * len(trajectories)

    # get base world plot
    g, g_plot = _plot(agents[0].world, locations, neighbors, output_img, coordinates, state, title, draw_victims)

    if len(trajectories) == 0 or len(trajectories[0]) == 0:
        return

    # draw each trajectory
    t_colors = distinct_colors(len(trajectories))
    for i, trajectory in enumerate(trajectories):
        loc_feat = get_location_key(agents[i])
        state = copy.deepcopy(trajectory[0][0].state)
        state.select(True)  # select most likely state
        source = trajectory[0][0].getFeature(loc_feat, state, True)
        for t in range(1, len(trajectory)):
            state = copy.deepcopy(trajectory[t][0].state)
            state.select(True)
            target = trajectory[t][0].getFeature(loc_feat, state, True)
            label = (agents[i].name if multiagent else 'T{:02d}'.format(i)) if t == len(trajectory) - 1 else None
            g.add_edge(source, target, color=color_to_html_format(t_colors[i]),
                       arrow_size=EDGE_ARROW_SIZE, arrow_width=EDGE_ARROW_WIDTH,
                       label_size=EDGE_LABEL_SIZE, label_color=EDGE_LABEL_COLOR, width=TRAJ_EDGE_WIDTH,
                       label=label)
            source = target

    g_plot.redraw()
    _draw_title(title, g_plot.surface, g_plot.width, g_plot.height)
    _save_plot(g_plot, output_img)
    if show:
        g_plot.show()


def plot_agent_location_frequencies(
        agent, trajectories, locations, output_img, title='Location Visitation Frequencies',
        plot_mean=True, plot_error=True):
    """
    Generates a plot with the agent's visitation frequency for each location in the environment.
    :param Agent agent: the agent whose visitation frequency we want to plot.
    :param list[str] locations: the list of possible world locations.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param list[list[tuple[World, Distribution]]] trajectories: the set of trajectories containing sequences of
    state-action pairs.
    :param str title: the plot's title.
    :param bool plot_mean: whether to plot a horizontal line across the bar chart denoting the mean of the values.
    :param bool plot_error: whether to plot error bars (requires input `data` to be 2-dimensional for each entry).
    """
    # gets agent's visitation frequency for all locations
    data = get_location_frequencies(agent, trajectories, locations)
    plot_location_frequencies(data, output_img, '{}\'s {}'.format(agent.name, title), plot_mean, plot_error)


def plot_location_frequencies(data, output_img, title, plot_mean=True, plot_error=True):
    """
    Generates a plot with the visitation frequency for each location in the environment.
    :param dict[str, float or list[float]] data: a dictionary containing the number of executions for each action.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param str title: the plot's title.
    :param bool plot_mean: whether to plot a horizontal line across the bar chart denoting the mean of the values.
    :param bool plot_error: whether to plot error bars (requires input `data` to be 2-dimensional for each entry).
    :return:
    """
    plot_bar(data, title, output_img, None, plot_mean, plot_error, y_label='Frequency')


def plot_agent_action_frequencies(
        agent, trajectories, output_img, title='Action Execution Frequencies', plot_mean=True):
    """
    Generates a plot with the agent's action execution frequency for each action in the given trajectories.
    :param Agent agent: the agent whose visitation frequency we want to plot.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param list[list[tuple[World, Distribution]]] trajectories: the set of trajectories containing sequences of
    state-action pairs.
    :param str title: the plot's title.
    :param bool plot_mean: whether to plot a horizontal line across the bar chart denoting the mean of the values.
    """
    data = get_action_frequencies(agent, trajectories)
    data = OrderedDict({str(a).replace('{}-'.format(agent.name), '').replace('_', ' '): val for a, val in data.items()})
    plot_action_frequencies(data, output_img, '{}\'s {}'.format(agent.name, title), plot_mean)


def plot_action_frequencies(data, output_img, title, plot_mean=True, plot_error=True):
    """
    Generates a plot with the agent's action execution frequency for each action.
    :param dict[str, float or list[float]] data: a dictionary containing the number of executions for each action.
    :param str output_img: the path to the image on which to save the plot. None results in no image being saved.
    :param str title: the plot's title.
    :param bool plot_mean: whether to plot a horizontal line across the bar chart denoting the mean of the values.
    :param bool plot_error: whether to plot error bars (requires input `data` to be 2-dimensional for each entry).
    :return:
    """
    plot_bar(data, title, output_img, None, plot_mean, plot_error, y_label='Frequency')


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
                g.add_vertex(label=vic_amount, label_size=VIC_LABEL_SIZE, color=(0, 0, 0, 0),
                             frame_color=(0, 0, 0, 0),
                             label_angle=np.pi / 2, label_color=COLORS[color], label_dist=VIC_VERTEX_LABEL_DIST)
                layout.append((x - label_start_x + VIC_LABEL_DIST * i, y))

    g_plot = igraph.plot(g, surface, (0, 0, width, height), margin=PLOT_MARGIN, layout=layout)
    g_plot.redraw()

    _draw_title(title, surface, width, height)

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


def _draw_title(title, surface, width, height):
    ctx = cairo.Context(surface)
    ctx.set_font_size(TITLE_FONT_SIZE)
    drawer = TextDrawer(ctx, title, halign=TextDrawer.CENTER, valign=TextDrawer.TOP)
    drawer.draw_at(0, PLOT_MARGIN[2] / 3, width=width)
