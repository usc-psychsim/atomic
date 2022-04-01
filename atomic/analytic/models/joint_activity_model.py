from uuid import uuid4
from ..handlers import stabilize, diagnose, unlock, pick_up, drop_off, at_proper_triage_area, get_in_range
from ..models.jags.registry import JagRegistry
from ..models.jags import asist_jags as aj


# @TODO: belongs to some configuration, refactor
__HANDLERS__ = {
    'urn:ihmc:asist:stabilize': {
        'Event:Triage': stabilize.handle_triage,
    },
    'urn:ihmc:asist:diagnose': {
        'Event:Triage': diagnose.handle_triage,
    },
    'urn:ihmc:asist:unlock-victim': {
        'Event:ProximityBlockInteraction': unlock.handle_proximity,
    },
    'urn:ihmc:asist:pick-up-victim': {
        'Event:VictimPickedUp': pick_up.handle_victim_picked_up,
    },
    'urn:ihmc:asist:drop-off-victim': {
        'Event:VictimPickedUp': drop_off.handle_victim_picked_up,
        'Event:VictimPlaced': drop_off.handle_victim_placed,
    },
    'urn:ihmc:asist:at-proper-triage-area': {
        'Event:VictimEvacuated': at_proper_triage_area.handle_victim_evacuated,
    },
    'urn:ihmc:asist:get-in-range': {
        'Event:location': get_in_range.handle_location_update,
    }
}


class JointActivityModel:
    def __init__(self, jags):
        self.__registry = JagRegistry(jags)
        self.__jag_instances = []

    @staticmethod
    def __dispatch(event_type, data, jag_instances):
        if len(jag_instances) == 0:
            return

        for jag_instance in jag_instances:
            # dispatch first to bubble up events
            JointActivityModel.__dispatch(event_type, data, jag_instance.children)

            if jag_instance.urn not in __HANDLERS__:
                continue

            handlers = __HANDLERS__.get(jag_instance.urn)

            if event_type not in handlers:
                continue

            handlers[event_type](jag_instance, data)

    @property
    def jag_instances(self):
        return self.__jag_instances

    def dispatch(self, event_type, data):
        JointActivityModel.__dispatch(event_type, data, self.__jag_instances)

    def get_by_id(self, uid):
        for instance in self.__jag_instances:
            value = instance.get_by_id(uid)
            if value is not None:
                return value
        return None

    # only inspect top level jags
    def get(self, urn, inputs=None, outputs=None):
        for instance in self.__jag_instances:
            if instance.matches(urn, inputs, outputs):
                return instance
        return None

    def get_by_urn_recursive(self, urn, inputs=None, outputs=None):
        for instance in self.__jag_instances:
            if instance.get_by_urn(urn, inputs, outputs):
                return instance
        return None


    #  @todo id should be a parameter and default to uuid4: uid=uuid4() and set of children
    def create(self, urn, inputs=None, outputs=None):
        jag = self.__registry.create_instance(urn, inputs, outputs)
        self.__jag_instances.append(jag)
        return jag

    def create_from_instance(self, instance_description):
        jag = self.__registry.create_instance_from_description(instance_description)
        self.__jag_instances.append(jag)
        return jag

    def get_known_victims(self):
        rescue_victim_jags = []
        for jag in self.__jag_instances:
            if jag.urn == aj.RESCUE_VICTIM['urn']:
                rescue_victim_jags.append(jag)
        return rescue_victim_jags

    def get_known_rescued_victims(self):
        rescue_victim_jags = []
        for jag in self.__jag_instances:
            if jag.urn == aj.RESCUE_VICTIM['urn']:
                if jag.is_complete():
                    rescue_victim_jags.append(jag)
        return rescue_victim_jags

