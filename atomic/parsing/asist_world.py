import json
import logging

from psychsim.action import ActionSet
from psychsim.pwl.keys import WORLD, isTurnKey, state2agent
from psychsim.world import World
from psychsim.agent import Agent

from atomic.analytic import make_ac_handlers
from atomic.teamwork.interventions import interventions, text2intervention
from atomic.teamwork.asi import make_asi, make_team, Team

import pandas as pd
import matplotlib.pyplot as plt


class ASISTWorld(World):
    TESTBED_SOURCES = {'metadata-web', 'gui', 'simulator'}
    DIALOG_SOURCES = {'uaz_dialog_agent', 'tomcat_speech_analyzer'}
    DECISION_INTERVAL = 5

    def __init__(self, config=None, logger=None):
        super().__init__()
        self.config = config
        if logger is None:
            self.logger = logging
        else:
            self.logger = logger
        self.info = {}
        self.msg_types = set()
        self.prior_beliefs = None
        self.prior_leader = None

        self.participants = None
        # Mappings between player and participant IDs
        self.participant2player = None
        self.player2participant = None
        self.asi = None
        self.intervention_args = {}
        self.actual_intervention = None
        self.compliance = empty_compliance()
        self.compliance_data = None

        # Team agent
        self.acs = {}
        self.team = None

        # Time variables
        self.now = None
        self.start_time = None
        self.last_decision = None

        # Assume we start in the planning stage
        self.planning = True

        self.defineState(WORLD, 'clock', int)
        self.setState(WORLD, 'clock', 0)

        self.run_count = 0
        self.log_columns = ['team', 'trial', 'ASI', 'timestamp', 'score']
        if self.config.getboolean('output', 'decision', fallback=False):
            self.log_columns += sorted([f'valid {verb}' for verb in interventions.keys() - {'notify early phase', 'notify late phase', 'reflect'}])
            self.log_columns += sorted([f'V({verb})' for verb in interventions.keys() | {'do nothing'}])
            self.log_columns += sorted([f'B({var})' for var in Team.processes])
        self.log_columns += ['actor', 'intervention', 'message']
        self.ac_columns = set()
        self.log_data = pd.DataFrame()

    def create_participant(self, name):
        agent = self.addAgent(PlayerModel(name))
        agent.noop = agent.addAction({'verb': 'do nothing'})
        return agent

    def create_team(self):
        agent = make_team(self)
        self.addAgent(agent)
        return agent

    def create_agents(self, msg):
        self.run_count += 1
        # Create player
        self.participants = {name: self.create_participant(name) for name in self.player2participant}
        # Create AC handlers
        self.acs = make_ac_handlers(self.config, world=self, logger=self.logger, version=0)
        # Any AC handling of this start message?
        for AC in self.acs.values():
            AC.handle_message(msg)
        # Create team agent
        self.team = self.create_team()
        for ac in self.acs.values():
            ac.augment_world(self, self.team, self.participants)
        self.team.initialize_effects(self.acs)

        self.asi = make_asi(self, self.team, self.participants, self.acs, self.config)
        for action in self.asi.actions:
            if action['verb'] not in self.intervention_args:
                self.intervention_args[action['verb']] = {}
        for AC in self.acs.values():
            AC.asi = self.asi

        self.setOrder([{self.asi.name}, set(self.agents.keys())-{self.asi.name}])
        self.asi.initialize_team_beliefs(self.prior_beliefs)
 
    def process_start(self, msg):
        for key, value in msg['data'].items():
            if key == 'client_info':
                self.participant2player = {client['unique_id']: client for client in value if client['unique_id']}
                if len(self.participant2player) < 3:
                    raise ValueError(f'Duplicate unique_id for participant: {[(c["unique_id"], c["callsign"]) for c in value]}')
                self.player2participant = {client['playername'].split('_')[0].capitalize(): unique_id 
                                           for unique_id, client in self.participant2player.items()}
            elif key not in self.info:
                self.info[key] = value
        if self.info['condition'] == '2':
            self.info['intervention_agents'][0] = 'Human'
        self.create_agents(msg)

    def process_msg(self, msg):
        intervention = None
        if msg['msg']['source'] in self.TESTBED_SOURCES:
            self.process_testbed_msg(msg)
        elif msg['msg']['source'] in self.acs:
            self.process_AC_msg(msg)
        elif self.asi is not None and msg['msg']['source'] == self.asi.name and msg['msg']['sub_type'] == 'Intervention:Chat':
            actual_intervention = msg['data']['content']
            ratio, verb = text2intervention(actual_intervention)
            self.compliance[verb]['intervention'] = self.now                    
            if self.config.getboolean('output', 'actual', fallback=True):
                self.log_decision({'verb': verb}, actual_intervention)
        if self.now is not None:
            if self.last_decision is None or self.elapsed_time(self.last_decision) >= self.DECISION_INTERVAL:
                # Run simulation to identify ASI action
                self.logger.debug(f'Evaluating interventions at time {self.now}')
                verbs = [action['verb'] for action in self.asi.actions if action != self.asi.noop]
                verbs = [verb for verb in verbs if verb[:6] != 'notify' and verb != 'reflect']
                pre_state = {f'valid {verb}': self.asi.getState(f'valid {verb}', unique=True) for verb in verbs}
                result = {self.asi.name: {}}
                asi_model = self.asi.get_true_model()
                self.step(debug=result, select='max')
                self.state.normalize()
                decision = result[self.asi.name]['__decision__'][asi_model]['action']
                assert decision == self.getAction(self.asi.name, unique=True)
                if 'V' in result[self.asi.name]['__decision__'][asi_model]:
                    pre_state.update({f'V({a["verb"]})': table['__EV__'] 
                                     for a, table in result[self.asi.name]['__decision__'][asi_model]['V'].items()})
                if self.config.getboolean('output', 'decision', fallback=False):
                    # Add current ASI beliefs to log
                    if len(self.asi.belief_data) == 0:
                        self.logger.warning(f'No beliefs at intervention time {self.now}')
                    try:
                        beliefs = self.asi.belief_data.iloc[-1]
                    except IndexError:
                        beliefs = None
                    if beliefs is not None:
                        pre_state.update({f'B({var})': beliefs[var] for var in self.team.processes if var in beliefs})
                if self.config.getboolean('output', 'ac', fallback=False):
                    # Add AC variables to log entry
                    ignore = {'callsign', 'player', 'Player', 'team', 'ASI', 
                              'trial', 'timestamp', 'Requestor', 'Requestee'}
                    for ac in self.acs.values():
                        if ac.last is not None:
                            name_blocks = ac.name.split('_')
                            name_prefix = '_'.join([name_blocks[1]]+name_blocks[3:]).lower()
                            for index, row in ac.last.iterrows():
                                player = 'Team'
                                for field in ['Player', 'player', 'callsign']:
                                    if field in row:
                                        player = row[field]
                                        break
                                else:
                                    if 'Requestor' in row:
                                        player = f'{row["Requestor"]}_asks_{row["Requestee"]}'
                                values = [(var, value) for var, value in row.items()
                                          if var not in ignore]
                                for var, value in values:
                                    for color in ['RED', 'GREEN', 'BLUE']:
                                        if color in var:
                                            var = var.replace(f'{color}_', '')
                                            player = color.capitalize()
                                            break
                                    label = f'{player}_{name_prefix}_{var}'
                                    self.ac_columns.add(label)
                                    pre_state[label] = value
                # Update compliance stats
                if self.config.get('output', 'compliance', fallback=False):
                    for verb, entry in self.compliance.items():
                        if pre_state.get(f'valid {verb}', False):
                            entry[entry['intervention'] is not None] += 1
                # Generate chat message
                args = self.intervention_args.get(decision['verb'], {})
                intervention = self.asi.generate_message(decision, args, self.run_count)
                if self.config.getboolean('output', 'decision', fallback=False) or (intervention is not None and self.config.getboolean('output', 'hypothetical', fallback=False)):
                    self.log_decision(decision, intervention, pre_state, replay=True)
                # Clear intervention content
                if decision != self.asi.noop and decision['verb'] in self.intervention_args:
                    self.intervention_args[decision['verb']].clear()
                self.last_decision = self.now
                # Spin until ASI's turn is up again
                for var in self.state.keys():
                    if isTurnKey(var):
                        if state2agent(var) == self.asi.name:
                            self.setFeature(var, 0, recurse=True)
                        else:
                            self.setFeature(var, 1, recurse=True)
        return intervention

    def make_record(self, values=None):
        record = {'team': self.info['experiment_name'],
                  'ASI': ','.join(self.info.get('intervention_agents', [])),
                  'trial': self.info["trial_number"],
                  'timestamp': None if self.now is None else 15*60-self.now[0]*60-self.now[1],
                  'score': self.current_score(),
                  }
        if values:
            record.update(values)
        return record

    def log_decision(self, decision, intervention, additional=None, replay=False):
        record = self.make_record(additional)
        record.update({'actor': 'replay' if replay else self.asi.name,
                       'intervention': interventions[decision['verb']]['id'] if intervention is not None else None,
                       'message': intervention})
        self.log_data = pd.concat([self.log_data, pd.DataFrame.from_records([record])], ignore_index=True)
        return record

    def current_score(self):
        if 'ac_cmu_ta2_ted' not in self.acs:
            score = None
        elif self.acs['ac_cmu_ta2_ted'].last is None:
            score = 0
        else:
            score = self.acs['ac_cmu_ta2_ted'].last['team_score_agg'].iloc[-1]
        return score

    def process_testbed_msg(self, msg):
        if msg['msg']['sub_type'] == 'trial' or msg['msg']['sub_type'] == 'replay':
            self.info = msg['msg']
            self.info.update(msg['data']['metadata'][msg['msg']['sub_type']])
        elif msg['msg']['sub_type'] == 'start':
            if self.participants is None:
                # Sometimes there are duplicate start messages?
                self.process_start(msg)
        elif msg['msg']['sub_type'] == 'state':
            self.update_state(msg)
        elif msg['msg']['sub_type'][:5] == 'Event':
            self.process_event(msg)
        elif msg['msg']['sub_type'][:7] == 'Mission':
            self.logger.debug(f'Ignoring mission message of type: {msg["msg"]["sub_type"]}')
        elif msg['msg']['sub_type'] == 'stop':
            self.process_stop(msg)
        else:
            self.msg_types.add(msg['msg']['sub_type'])
            self.logger.debug(f'Unknown message of type: {msg["msg"]["sub_type"]}')

    def process_AC_msg(self, msg):
        try:
            AC = self.acs[msg['msg']['source']]
        except KeyError:
            self.logger.warning(f'Processing message by unknown AC {msg["msg"]["source"]}')
            return None
        delta = AC.handle_message(msg, self.now)
        if delta:
            for var, value in delta.items():
                self.setFeature(var, value, recurse=True)
            self.asi.update_interventions(AC, delta)

    def update_state(self, msg):
        try:
            self.now = tuple([int(item) for item in msg['data']['mission_timer'].split(':')])
        except ValueError:
            pass
        except KeyError:
            pass
        else:
            if self.start_time is None:
                self.start_time = self.now
                self.logger.debug(f'Starting at time {self.now}')
            if self.now is not None:
                self.setState(WORLD, 'clock', 900-self.now[0]*60-self.now[1], recurse=True)

    def process_event(self, msg):
        if msg['msg']['sub_type'] == 'Event:PlanningStage':
            self.planning = msg['data']['state'] != 'Stop'

    def elapsed_time(self, start=None):
        if start is None:
            start = self.start_time
        if start is None:
            return -1
        else:
            return (start[0]-self.now[0])*60 + start[1] - self.now[1]

    def process_stop(self, msg):
        self.log_decision(self.asi.noop, None)
        for AC in self.acs.values():
            topic_list = [topic for topic in AC.ignored_topics
                          if 'versioninfo' not in topic.split('/')
                          and 'response' not in topic.split('/')
                          and 'heartbeats' not in topic.split('/')]
            if topic_list:
                print(AC.name, sorted(topic_list))

        if self.config.get('output', 'compliance', fallback=False):
            for verb, entry in self.compliance.items():
                entry['team'] = self.info['experiment_name']
                entry['ASI'] = ','.join(self.info.get('intervention_agents', []))
                entry['trial'] = self.info["trial_number"]
                entry['before'] = entry[False]
                entry['after'] = entry[True]
                entry['when'] = 15*60 - (entry['intervention'][0]*60+entry['intervention'][1]) if entry['intervention'] is not None else None
                entry['intervention'] = verb
                del entry[False]
                del entry[True]
            self.compliance_data = pd.DataFrame.from_dict(self.compliance, orient='index')
            self.compliance = empty_compliance()
                  
        # Save state for subsequent trial with this team
        self.prior_beliefs = self.asi.getBelief(model=self.asi.get_true_model())
        self.prior_leader = self.team.leader
        self.initialize()
        self.info.clear()
        self.msg_types = set()

        self.participants = None
        self.participant2player = None
        self.player2participant = None
        self.acs = {}
        self.team = None
        self.now = None
        self.start_time = None
        self.last_decision = None
        self.planning = True

        self.defineState(WORLD, 'clock', int)
        self.setState(WORLD, 'clock', 0)

    def close(self):
        self.log_data = self.log_data[0:0]
        if self.msg_types:
            self.logger.warning(f'Unknown message types: {", ".join(sorted(self.msg_types))}')


class PlayerModel(Agent):
    pass


def empty_compliance():
    return {intervention: {False: 0, True: 0, 'intervention': None} for intervention in interventions}