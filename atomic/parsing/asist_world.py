import json
import logging

from psychsim.world import World

from atomic.teamwork.ac import make_ac_handlers
from atomic.teamwork.asi import make_asi, make_team


class ASISTWorld(World):
    TESTBED_SOURCES = {'metadata-web', 'gui', 'simulator'}
    DIALOG_SOURCES = {'uaz_dialog_agent', 'tomcat_speech_analyzer'}
    DECISION_INTERVAL = 5

    def __init__(self, config=None, logger=logging):
        super().__init__()
        self.config = config
        self.logger = logger
        self.info = None
        self.msg_types = set()

        self.participants = None
        # Mappings between player and participant IDs
        self.participant2player = None
        self.player2participant = None

        # Team agent
        self.team = None

        # Time variables
        self.now = None
        self.start_time = None
        self.last_decision = None

        # Assume we start in the planning stage
        self.planning = True

    def create_participant(self, name):
        agent = self.addAgent(name)
        return agent

    def create_team(self):
        agent = make_team(self)
        self.addAgent(agent)
        return agent

    def process_start(self, msg):
        for key, value in msg['data'].items():
            if key == 'client_info':
                self.participant2player = {client['unique_id']: client for client in value if client['unique_id']}
                self.player2participant = {client['playername']: unique_id 
                                           for unique_id, client in self.participant2player.items()}
            elif key not in self.info:
                self.info[key] = value
        # Create player
        self.participants = {name: self.create_participant(name) for name in self.player2participant}
        # Create AC handlers
        self.acs = make_ac_handlers(self.config)
        # Create team agent
        self.team = self.create_team()

        for ac in self.acs.values():
            ac.augment_world(self, self.team, self.participants)
        self.team.initialize_effects(self.acs)

    def process_msg(self, msg):
        if msg['msg']['source'] in self.TESTBED_SOURCES:
            self.process_testbed_msg(msg)
        elif msg['msg']['source'] in self.acs:
            self.process_AC_msg(msg)
        if not self.planning:
            if self.last_decision is None or self.elapsed_time(self.last_decision) >= self.DECISION_INTERVAL:
                self.logger.debug(f'Evaluating interventions at time {self.now}')
                self.last_decision = self.now

    def process_testbed_msg(self, msg):
        if msg['msg']['sub_type'] == 'trial':
            self.info = msg['msg']
            self.info.update(msg['data']['metadata']['trial'])
        elif msg['msg']['sub_type'] == 'start':
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
        msg_topic = msg.get('topic', '')
        if (msg_topic == 'trial') or (msg_topic in AC.filters):
            AC.wrapper.handle_message(msg_topic, msg['msg'], msg['data'])
        # add_joint_activity(world, world.agents[data['participant_id']], team.name, data['jag'])

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
        print(msg)

    def close(self):
        if self.msg_types:
            self.logger.warning(f'Unknown message types: {", ".join(sorted(self.msg_types))}')
