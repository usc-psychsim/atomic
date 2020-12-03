import argparse
import json
import logging
import os
from model_learning.util.cmd_line import str2bool, none_or_int
from model_learning.util.io import create_clear_dir, get_files_with_extension, change_log_handler
from atomic.definitions import world_map
from atomic.model_learning.linear.post_process.evaluation import evaluate_reward_models
from atomic.model_learning.linear.post_process.players_data import process_players_data
from atomic.model_learning.linear.post_process.clustering import cluster_reward_weights
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer, OUTPUT_DIR, \
    NUM_TRAJECTORIES, TRAJ_LENGTH, HORIZON, MAX_EPOCHS, LEARNING_RATE, NORM_THETA, PRUNE_THRESHOLD, DIFF_THRESHOLD, \
    PROCESSES, IMG_FORMAT, SEED

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Loads several log files containing the information about different players\' behavior on the ASIST ' \
           'search and rescue task and performs linear reward model learning for each datapoint using the ' \
           'Maximum Entropy Inverse Reinforcement Learning algorithm (MaxEnt IRL). Statistics about the learned ' \
           'rewards models are also gathered and saved in the output directory.'

CMDS_JSON_FILE = 'cmds.json'

# relevant cmd line flags
REPLAYS_FLAG = '--replays'
SAVE_COMMANDS_FLAG = '--save-commands'

# TODO hack to avoid lights
world_map.MODEL_LIGHTS = False


def _save_commands():
    scripts_args = []
    for file in files:
        args_dict = vars(args)
        cmd_args = []
        for a in parser._actions:
            arg_str = a.option_strings[-1]
            if a.dest not in args_dict or arg_str == SAVE_COMMANDS_FLAG:
                continue
            if arg_str == REPLAYS_FLAG:
                args_dict[a.dest] = file  # replace with file
            if isinstance(a, argparse._StoreTrueAction):
                if args_dict[a.dest]:
                    cmd_args.append(arg_str)
            elif isinstance(a, argparse._CountAction):
                cmd_args.extend([arg_str for _ in range(args_dict[a.dest])])
            else:
                cmd_args.extend([arg_str, str(args_dict[a.dest])])
        scripts_args.append('python -m atomic.bin.reward_model_learning {}'.format(' '.join(cmd_args)))

    with open(os.path.join(args.output, CMDS_JSON_FILE), 'w') as fp:
        json.dump(dict(commands=scripts_args), fp, indent=4)


if __name__ == '__main__':
    # parse command-line arguments
    parser = argparse.ArgumentParser(description=__desc__)

    parser.add_argument('-r', REPLAYS_FLAG, required=True, type=str,
                        help='Directory containing the replay logs or single replay file to process.')
    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR, help='Directory in which to save results.')
    parser.add_argument('-c', '--clear', help='Whether to clear output directories before generating results.',
                        action='store_true')

    parser.add_argument('-t', '--trajectories', type=int, default=NUM_TRAJECTORIES,
                        help='Number of trajectories to use in reward learning.')
    parser.add_argument('-l', '--length', type=int, default=TRAJ_LENGTH,
                        help='Length of trajectories used in reward learning.')
    parser.add_argument('-hz', '--horizon', type=int, default=HORIZON, help='Planning horizon of the "learner" agent.')
    parser.add_argument('-e', '--epochs', type=int, default=MAX_EPOCHS,
                        help='The maximum number of gradient descent steps.')
    parser.add_argument('-lr', '--learn-rate', type=float, default=LEARNING_RATE,
                        help='The gradient descent learning/update rate.')
    parser.add_argument('-nw', '--normalize', type=str2bool, default=NORM_THETA,
                        help='Whether to normalize reward weights at each step of the algorithm.')
    parser.add_argument('-pt', '--prune', type=float, default=PRUNE_THRESHOLD,
                        help='Likelihood below which stochastic outcomes are pruned.')
    parser.add_argument('-dt', '--diff', type=float, default=DIFF_THRESHOLD,
                        help='The termination threshold for the weight vector difference.')

    parser.add_argument('-p', '--processes', type=none_or_int, default=PROCESSES,
                        help='Number of processes/cores to use. If unspecified, all available cores will be used')
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Verbosity level.')
    parser.add_argument('--format', help='Format of images', default=IMG_FORMAT)
    parser.add_argument('-s', '--seed', type=int, default=SEED, help='Seed for random number generation.')

    parser.add_argument('-pp', '--post-process', action='store_true',
                        help='Whether to perform post-process over the data resulting from IRL.')
    parser.add_argument(SAVE_COMMANDS_FLAG, action='store_true',
                        help='Whether to save a json file containing a a list with python commands, one for each '
                             'replay file to be processed, e.g., for parallelized deployment.')
    args = parser.parse_args()

    # create output
    create_clear_dir(args.output, False)

    # checks input files
    if os.path.isfile(args.replays):
        files = [args.replays]
    elif os.path.isdir(args.replays):
        files = list(get_files_with_extension(args.replays, 'csv'))
    else:
        raise ValueError('Input path is not a valid file or directory: {}.'.format(args.replays))

    # checks save commands file only, no need to actually process data
    if args.save_commands:
        _save_commands()
        exit(0)

    # sets up log to file
    log_level = logging.WARN if args.verbosity == 0 else logging.INFO if args.verbosity == 1 else logging.DEBUG
    logging.basicConfig(format='%(message)s', level=log_level)

    # saves args
    with open(os.path.join(args.output, 'args.json'), 'w') as fp:
        json.dump(vars(args), fp, indent=4)

    # create replayer and process all files
    analyzer = RewardModelAnalyzer(
        replays=files,
        output=args.output,
        clear=args.clear,
        num_trajectories=args.trajectories,
        length=args.length,
        normalize=args.normalize,
        learn_rate=args.learn_rate,
        epochs=args.epochs,
        diff=args.diff,
        prune=args.prune,
        horizon=args.horizon,
        seed=args.seed,
        verbosity=args.verbosity,
        processes=args.processes,
        img_format=args.format
    )
    analyzer.process_files()

    logging.info('=================================')
    if analyzer.results is None or len(analyzer.results) == 0 or \
            analyzer.trajectories is None or len(analyzer.trajectories) == 0:
        logging.warning('Inexistent or incomplete results!')
        exit()

    if args.post_process:

        # performs post-processing of results
        output_dir = os.path.join(args.output, 'post-process')
        create_clear_dir(output_dir, False)
        change_log_handler(os.path.join(output_dir, 'post-process.log'), args.verbosity)

        logging.info('Post-processing IRL data for the following {} files:'.format(len(analyzer.results)))
        for filename in analyzer.results:
            logging.info('\t{}, player: "{}", agent: "{}", map: "{}", {} steps'.format(
                filename, analyzer.get_player_name(filename), analyzer.agent_names[filename],
                analyzer.map_tables[filename].name, len(analyzer.trajectories[filename])))

        logging.info('Saving post-process results in "{}"...'.format(output_dir))

        process_players_data(analyzer, os.path.join(output_dir, 'player_behavior'), args.clear, args.verbosity)
        cluster_reward_weights(analyzer, os.path.join(output_dir, 'rewards'),
                               clear=args.clear, verbosity=args.verbosity)
        evaluate_reward_models(analyzer, os.path.join(output_dir, 'evaluation'),
                               os.path.join(output_dir, 'rewards', 'cluster-weights.csv'),
                               os.path.join(output_dir, 'rewards', 'clusters.csv'),
                               args.clear, args.verbosity)
