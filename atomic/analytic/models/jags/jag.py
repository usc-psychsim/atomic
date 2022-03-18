import logging
from ...models.jags import asist_jags as aj
from ...utils.activity_tracker import ActivityTracker, get_non_overlapping_activity_tracker_set, \
    get_sum_of_activity_durations, only_ongoing_activities, get_uniquely_non_overlapping_activity_tracker_set
from ...utils.time_period import TimePeriod
from ...utils.time_period import get_non_overlapping_set


def update_knowledge(player_id, category, confidence_value, elapsed_ms):
    # update knowledge about activity
    if player_id not in category:
        if confidence_value > 0.0:  # only start tracking if confidence greater than zero
            category[player_id] = [ActivityTracker(player_id, confidence_value, TimePeriod(elapsed_ms, -1))]
    else:
        player_preparing = category[player_id]
        last_tracker = player_preparing.pop()
        if last_tracker.ongoing:  # handle ongoing activity
            if confidence_value == 0.0:  # end last time period if ongoing
                last_tracker.time_period.end = elapsed_ms
                category[player_id].append(last_tracker)
            elif confidence_value != last_tracker.confidence:  # end last time period and start a new one
                last_tracker.time_period.end = elapsed_ms
                category[player_id].append(last_tracker)
                category[player_id].append(ActivityTracker(player_id, confidence_value, TimePeriod(elapsed_ms, -1)))
            else:
                category[player_id].append(last_tracker)
        else:  # handle when nothing is ongoing
            category[player_id].append(last_tracker)
            if confidence_value > 0.0:  # only start tracking if confidence greater than zero
                category[player_id].append(ActivityTracker(player_id, confidence_value, TimePeriod(elapsed_ms, -1)))

    category[player_id] = get_non_overlapping_activity_tracker_set(category[player_id])

from ..events import JagEvent


class Jag:

    def __init__(self, urn, connector, inputs, outputs, uid):
        self.__uid = uid
        self.__urn = urn
        self.__connector = {} if connector is None else connector
        self.__inputs = {} if inputs is None else inputs
        self.__outputs = {} if outputs is None else outputs

        self.__is_complete: bool = False
        self.__awareness = {}
        self.__preparing = {}
        self.__addressing = {}
        self.__completed = {}
        self.__completion_time = -1
        self.__estimated_preparation_duration = 0.0
        self.__estimated_addressing_duration = 0.0
        self.__depends_on = []

        self.__children = []
        self.__is_required = False
        self.__logger = logging.getLogger(__name__)
        self.__observers = []

    @property
    def id(self):
        return self.__uid

    @property
    def id_string(self):
        return str(self.__uid)

    @property
    def urn(self):
        return self.__urn

    @property
    def inputs(self):
        return self.__inputs

    @property
    def outputs(self):
        return self.__outputs

    @property
    def connector(self):
        return self.__connector

    @property
    def children(self):
        return self.__children

    @property
    def has_children(self):
        return len(self.__children) > 0

    @property
    def is_leaf(self):
        return len(self.__children) == 0

    def __get_activity_set(self, category_type):
        activity_tracker_set = []

        if category_type == "preparing":
            category = self.__preparing
        else:
            category = self.__addressing

        if len(self.__children) == 0:
            for key in category:
                activity_tracker_set += category[key]
        else:
            for child in self.__children:
                activity_tracker_set += child.__get_activity_set(category_type)

        not_overlapping_set = get_non_overlapping_activity_tracker_set(activity_tracker_set)
        return not_overlapping_set

    def __get_non_overlapping_activity_set(self, category_type):
        activity_tracker_set = []

        if category_type == "preparing":
            category = self.__preparing
        else:
            category = self.__addressing

        if len(self.__children) == 0:
            for key in category:
                activity_tracker_set += category[key]
        else:
            for child in self.__children:
                activity_tracker_set += child.__get_non_overlapping_activity_set(category_type)

        not_overlapping_set = get_uniquely_non_overlapping_activity_tracker_set(activity_tracker_set)
        return not_overlapping_set

    # AWARENESS
    def update_awareness(self, observer_player_id, aware_player_id, confidence_value, elapsed_ms):
        if self.is_leaf:
            update_knowledge(aware_player_id, self.__awareness, confidence_value, elapsed_ms)
        self.notify(observer_player_id, JagEvent.AWARENESS, self, elapsed_ms)
        # awareness should trickle down to children
        for child in self.__children:
            child.update_awareness(observer_player_id, aware_player_id, confidence_value, elapsed_ms)

    def awareness_time(self, player_id):
        if player_id in self.__awareness:
            player_awareness = self.__awareness[player_id]
            if len(player_awareness) > 0:
                return player_awareness[0].time_period.start
        return None

    def is_aware(self, player_id):
        if player_id in self.__awareness.keys():
            player_awareness = self.__awareness[player_id]
            last_tracker = player_awareness.pop()
            confidence = last_tracker.confidence
            self.__awareness[player_id].append(last_tracker)
            return confidence > 0.0
        return False

    # PREPARING
    def update_preparing(self, observer_player_id, preparing_player_id, confidence_value, elapsed_ms):
        if self.is_leaf:
            update_knowledge(preparing_player_id, self.__preparing, confidence_value, elapsed_ms)
        self.notify(observer_player_id, JagEvent.PREPARING, self, elapsed_ms)

    def preparing_duration(self):
        activity_set = self.__get_activity_set("preparing")
        if len(activity_set) == 0 or only_ongoing_activities(activity_set):
            return -1

        return get_sum_of_activity_durations(activity_set) / 1000

    def preparing_non_overlapping_duration(self):
        activity_set = self.__get_non_overlapping_activity_set("preparing")
        if len(activity_set) == 0 or only_ongoing_activities(activity_set):
            return -1

        return get_sum_of_activity_durations(activity_set) / 1000

    @property
    def estimated_preparation_duration(self):
        estimate = 0.0
        if len(self.__children) == 0:
            estimate = self.__estimated_preparation_duration
        else:
            for child in self.__children:
                estimate += child.estimated_preparation_duration

        return estimate

    # ADDRESSING
    def update_addressing(self, observer_player_id, addressing_player_id, confidence_value, elapsed_ms):
        if self.is_leaf:
            update_knowledge(addressing_player_id, self.__addressing, confidence_value, elapsed_ms)
        data = {'addressing_player_id': addressing_player_id, 'confidence_value': confidence_value, 'jag': self}
        self.notify(observer_player_id, JagEvent.ADDRESSING, data, elapsed_ms)

    def is_addressing(self, player_id):
        if player_id in self.__addressing.keys():
            player_addressing = self.__addressing[player_id]
            last_tracker = player_addressing.pop()
            ongoing = last_tracker.ongoing
            self.__addressing[player_id].append(last_tracker)
            return ongoing
        return False

    def addressing_duration(self):
        activity_set = self.__get_activity_set("addressing")
        if len(activity_set) == 0 or only_ongoing_activities(activity_set):
            return -1

        return get_sum_of_activity_durations(activity_set) / 1000

    def addressing_non_overlapping_duration(self):
        activity_set = self.__get_non_overlapping_activity_set("addressing")
        if len(activity_set) == 0 or only_ongoing_activities(activity_set):
            return -1

        return get_sum_of_activity_durations(activity_set) / 1000

    @property
    def estimated_addressing_duration(self):
        estimate = 0.0
        if len(self.__children) == 0:
            estimate = self.__estimated_addressing_duration
        else:
            for child in self.__children:
                estimate += child.estimated_addressing_duration

        return estimate

    def is_active(self):
        for key in self.__addressing:
            for activity in self.__addressing[key]:
                if activity.ongoing:
                    return True
        for child in self.__children:
            if child.is_active():
                return True
        return False

    # COMPLETION
    def update_completion_status(self, observer_player_id, completion_status, elapsed_ms):
        self.__is_complete = completion_status
        if self.__is_complete:
            if self.__completion_time == -1:
                self.__completion_time = elapsed_ms
                self.notify(observer_player_id, JagEvent.COMPLETION, self, elapsed_ms)
        else:
            self.__completion_time = -1

    @property
    def completion_time(self):
        return self.__completion_time

    def completion_duration(self):
        preparing_duration = self.preparing_duration()
        if preparing_duration < 0.0:
            return preparing_duration
        addressing_duration = self.addressing_duration()
        if addressing_duration < 0.0:
            return addressing_duration
        return preparing_duration + addressing_duration

    def completion_non_overlapping_duration(self):
        preparing_duration = self.preparing_non_overlapping_duration()
        if preparing_duration < 0.0:
            return preparing_duration
        addressing_duration = self.addressing_non_overlapping_duration()
        if addressing_duration < 0.0:
            return addressing_duration
        return preparing_duration + addressing_duration

    def is_complete(self):
        return self.__is_complete

    @property
    def estimated_completion_duration(self):
        return self.estimated_preparation_duration + self.estimated_addressing_duration

    def add_child(self, jag):
        jag.add_observer(self.notify)
        jag.add_observer(self.__handle_addressing)
        jag.add_observer(self.__handle_completion)

        self.__children.append(jag)

    def set_required(self, is_required):
        self.__is_required = is_required

    def is_required(self):
        return self.__is_required

    def add_observer(self, observer):
        self.__observers.append(observer)

    def matches(self, urn, inputs, outputs):
        if self.__urn != urn:
            return False

        for key, value in self.__inputs.items():
            if key not in inputs:
                return False

            if value != inputs[key]:
                return False

        return True

    def get_by_urn(self, urn, inputs, outputs=None):
        if self.matches(urn, inputs, outputs):
            return self

        for child in self.children:
            value = child.get_by_urn(urn, inputs, outputs)
            if value is not None:
                return value

        return None

    def get_by_id(self, uid):
        if self.id_string == uid:
            return self
        for child in self.children:
            value = child.get_by_id(uid)
            if value is not None:
                return value
        return None

    def depends_on(self, interdependency):
        self.__depends_on.append(interdependency)

    def to_string(self, level=1):
        indent = ''
        for x in range(level):
            indent += "\t"

        string = self.short_string()

        if self.is_leaf:
            string += "\n" + indent + "awareness=" + str(self.__awareness)
            string += "\n" + indent + "preparing=" + str(self.__preparing)
            string += "\n" + indent + "addressing=" + str(self.__addressing)

        for child in self.__children:
            string += "\n" + indent
            string += child.to_string(level + 1)
        return string

    def short_string(self):
        completion_status = "(Incomplete)"
        if self.__is_complete:
            completion_status = "(Complete)"
        short_id = self.__urn.replace("urn:ihmc:asist:", "")
        elapsed_time = f" ({self.preparing_duration():.1f}sec: {self.addressing_duration():.1f}sec: {self.completion_duration():.1f}sec)"

        inputs = ''
        if len(self.__inputs) != 0:
            inputs = f" {list(self.__inputs.values())}"

        return f"{short_id}{inputs}{elapsed_time}{completion_status}"

    def test_string(self):
        data = {
            'id': self.id_string,
            'urn': self.urn
        }

        return data

    def notify(self, observer_player_id, event_type, data, elapsed_ms):
        for observer in self.__observers:
            observer(observer_player_id, event_type, data, elapsed_ms)

    def __handle_completion(self, observer_player_id, event_type, data, elapsed_ms):
        if event_type != JagEvent.COMPLETION:
            return

        if self.__do_children_satisfy_completion():
            self.update_completion_status(observer_player_id, data.is_complete(), elapsed_ms)

    def __do_children_satisfy_completion(self):
        if len(self.__children) == 0:
            return True

        if 'operator' in self.__connector.keys():
            operator = self.__connector['operator']
            if operator == 'node.operator.and':
                for child in self.__children:
                    if not child.is_complete():
                        return False
                return True
            elif operator == 'node.operator.or':
                for child in self.__children:
                    if child.is_complete():
                        return True
                return False
            elif operator == 'node.operator.only_required':
                for child in self.__children:
                    if child.is_required():
                        if not child.is_complete():
                            return False
                return True

        print('__do_children_satisfy_completion: Should not get here')
        return False

    def __handle_addressing(self, observer_player_id, event_type, data, elapsed_ms):
        if event_type != JagEvent.ADDRESSING:
            return

        self.update_addressing(observer_player_id, data['addressing_player_id'], data['confidence_value'], elapsed_ms)

    def get_data(self, event_type, elapsed_ms):
        data = {
            'id': self.id_string,
        }

        if event_type == JagEvent.AWARENESS:
            data['elapsed_milliseconds'] = elapsed_ms
            data['urn'] = self.urn
            data['is_complete'] = self.is_complete()
            old_format = self.get_backward_compatible_data(self.__awareness)
            data['awareness'] = old_format
        elif event_type == JagEvent.PREPARING:
            data['elapsed_milliseconds'] = elapsed_ms
            data['is_complete'] = self.is_complete()
            old_format = self.get_backward_compatible_data(self.__preparing)
            data['preparing'] = old_format
        elif event_type == JagEvent.ADDRESSING:
            data['elapsed_milliseconds'] = elapsed_ms
            data['is_complete'] = self.is_complete()
            old_format = self.get_backward_compatible_data(self.__addressing)
            data['addressing'] = old_format
        elif event_type == JagEvent.COMPLETION:
            data['elapsed_milliseconds'] = elapsed_ms
            data['is_complete'] = self.is_complete()
            old_format = self.get_backward_compatible_data(self.__addressing)
            data['addressing'] = old_format

        return data

    def get_backward_compatible_data(self, category):
        old_format = {}
        for key in category:
            activity_tracker_set = category[key]
            last_activity_tracker = activity_tracker_set[-1]
            if last_activity_tracker.ongoing:
                old_format[key] = 1.0
            else:
                old_format[key] = 0.0
        return old_format

    def get_instance_data(self):
        data = {
            'id': self.id_string,
            'urn': self.__urn,
            'children': [],
            'inputs': self.__inputs,
            'outputs': self.__outputs
        }

        for child in self.__children:
            child_data = child.get_instance_data()
            if child.is_required():
                child_data['required'] = True
            data['children'].append(child_data)

        return data

    def __hash__(self):
        return hash((self.urn, str(self.inputs), str(self.outputs)))

    def __eq__(self, other):
        if not isinstance(other, type(self)): return NotImplemented
        return self.urn == other.urn and self.inputs == other.inputs and self.outputs == other.outputs

    # **************************************************************************
    # used for merging jags
    def get_awareness(self):
        return self.__awareness

    def get_preparing(self):
        return self.__preparing

    def get_addressing(self):
        return self.__addressing

    def set_awareness(self, awareness):
        self.__awareness = awareness

    def set_preparing(self, preparing):
        self.__preparing = preparing

    def set_addressing(self, addressing):
        self.__addressing = addressing

    def set_completion(self, is_complete, elapsed_ms):
        self.__is_complete = is_complete
        self.__completion_time = elapsed_ms

    def set_estimated_addressing_duration(self, estimated_addressing_duration):
        self.__estimated_addressing_duration = estimated_addressing_duration

    def set_estimated_preparation_duration(self, estimated_preparation_duration):
        self.__estimated_preparation_duration = estimated_preparation_duration

