import csv
from multiprocessing import Pool
import os
import subprocess

from atomic.parsing.replayer import filename_to_condition

home = '/home/david/working/atomic'

multi = True
profile = False
analyze = False

def run_inference(args):
	fname, sub_args = args
	root, log_name = sub_args
	env = {'PYTHONPATH': ':'.join([os.path.join(home, '..', 'psychsim'), home, os.path.join(home, '..', 'model-learning')])}
	cmd = ['python3', os.path.join(home, 'atomic', 'bin', 'model_inference.py'),
		os.path.join(root, fname), '--ignore_rationality', '--ignore_horizon', '-d', 'INFO',
		'-c', os.path.join(home, 'data', 'rewards', 'linear', 'phase1_clusters.csv'),
		'--metadata', os.path.join(home, 'data', 'ASU_2020_08', 'Raw', log_name)]
	if profile:
		cmd.append('--profile')
#	cmd += ['-n', '20']
	subprocess.run(cmd, env=env)

baseline = {'NoTriageNoSignal StaticMap': 0.19230769230769232, 'TriageNoSignal StaticMap': 0.15384615384615385, 
	'TriageSignal DynamicMap': 0.38461538461538464, 'TriageSignal StaticMap': 0.2692307692307692}

def evaluate_inference(data_file, condition):
	inference = {}
	current = None
	max_times = []
	better_times = []
	correct = f'{condition["CondBtwn"]} {condition["CondWin"][1]}'
	assert correct in baseline, f'Illegal condition: {correct}'
	with open(data_file, 'r') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='\t')
		for row in reader:
			t = int(row['Timestep'])
			if current is None:
				current = t
			elif t > current:
				if inference[correct] == max(inference.values()):
					# Max likelihood inference
					max_times.append(current)
				if inference[correct] > baseline[correct]:
					better_times.append(current)
				current = t
			inference[row['Condition']] = float(row['Belief'])
	if inference[correct] == max(inference.values()):
		# Max likelihood inference
		max_times.append(current)
	if inference[correct] > baseline[correct]:
		better_times.append(current)
	return {'Trial': condition['Trial'], '% Most Likely': len(max_times)/t, '% More Likely': len(better_times)/t,
		'Final Most Likely': t in max_times, 'Final More Likely': t in better_times}

if __name__ == '__main__':
	dirs = [os.path.join(home, 'data', 'ASU_2020_08', 'FalconEasy_1123'), 
		os.path.join(home, 'data', 'ASU_2020_08', 'FalconMedium_1123'), 
		os.path.join(home, 'data', 'ASU_2020_08', 'FalconHard_1123')]
	log_dir = os.path.join(home, 'data', 'ASU_2020_08', 'Raw')
	files = {}
	analyzees = {}
	for root in dirs:
		for fname in sorted(os.listdir(root)):
			base_name, ext = os.path.splitext(fname)
			if ext != '.csv':
				continue
			trial = filename_to_condition(base_name)['Trial']
			for log_name in sorted(os.listdir(log_dir)):
				if filename_to_condition(log_name)['Trial'] == trial:
					break
			else:
				print(f'Unable to find log file for {fname}')
				continue
			for analysis in ['conditions']:
				data_file = os.path.join(root, f'{base_name}_Analysis-{analysis}.tsv')
				if os.path.exists(data_file):
					if analyze:
						analyzees[data_file] = filename_to_condition(log_name)
				else:
					print(f'did not find {data_file}')
					files[fname] = (root, log_name)
					break
			else:
				print(f'Skipping, already processed: {fname}')
	if analyze:
		data = []
		total = {}
		for data_file, condition in analyzees.items():
			data.append(evaluate_inference(data_file, condition))
			for field, value in data[-1].items():
				if field != 'Trial':
					if isinstance(value, bool):
						if value:
							total[field] = total.get(field, 0) + 1
					else:
						total[field] = total.get(field, 0) + value
		for field in total:
			total[field] /= len(analyzees)
		print(total)
	elif multi:
		with Pool(processes=3) as pool:
			pool.map(run_inference, files.items())
	else:
		for args in sorted(files.items()):
			run_inference(args)
