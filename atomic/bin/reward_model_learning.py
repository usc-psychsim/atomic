import argparse
import json
import logging
import os
from model_learning.util import str2bool
from model_learning.util.io import create_clear_dir, get_files_with_extension
from atomic.model_learning.linear.post_process import PostProcessor
from atomic.model_learning.linear.analyzer import RewardModelAnalyzer, OUTPUT_DIR, \
    NUM_TRAJECTORIES, TRAJ_LENGTH, HORIZON, MAX_EPOCHS, LEARNING_RATE, NORM_THETA, PRUNE_THRESHOLD, DIFF_THRESHOLD, \
    PROCESSES, IMG_FORMAT, SEED

__author__ = 'Pedro Sequeira'
__email__ = 'pedrodbs@gmail.com'
__desc__ = 'Loads several log files containing the information about different players\' behavior on the ASIST ' \
           'search and rescue task and performs linear reward model learning for each datapoint using the ' \
           'Maximum Entropy Inverse Reinforcement Learning algorithm (MaxEnt IRL). Statistics about the learned ' \
           'rewards models are also gathered and saved in the output directory.'

if __name__ == '__main__':
    # parse command-line arguments
    parser = argparse.ArgumentParser(description=__desc__)

    parser.add_argument('-r', '--replays', required=True, type=str,
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

    parser.add_argument('-p', '--processes', type=int, default=PROCESSES,
                        help='Number of processes/cores to use. If unspecified, all available cores will be used')
    parser.add_argument('-v', '--verbosity', action='count', default=0, help='Verbosity level.')
    parser.add_argument('--format', help='Format of images', default=IMG_FORMAT)
    parser.add_argument('-s', '--seed', type=int, default=SEED, help='Seed for random number generation.')
    args = parser.parse_args()

    # sets up log to file
    log_level = logging.WARN if args.verbosity == 0 else logging.INFO if args.verbosity == 1 else logging.DEBUG
    logging.basicConfig(format='%(message)s', level=log_level)

    # create output
    create_clear_dir(args.output, False)

    # saves args
    with open(os.path.join(args.output, 'args.json'), 'w') as fp:
        json.dump(vars(args), fp, indent=4)

    # checks input files
    if os.path.isfile(args.replays):
        files = [args.replays]
    elif os.path.isdir(args.replays):
        files = list(get_files_with_extension(args.replays, 'csv'))
    else:
        raise ValueError('Input path is not a valid file or directory: {}.'.format(args.replays))

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

    # performs post-processing of results
    post_processor = PostProcessor(analyzer)
    post_processor.run()
