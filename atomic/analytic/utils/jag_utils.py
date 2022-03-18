from uuid import uuid4

from src.models.jags.jag import Jag
from src.models.joint_activity_model import JointActivityModel
from src.models.jags import asist_jags as aj


def merge_jags(jag1, jag2):
    if jag1 != jag2:
        print("WARNING: cannot merge jags that are not the equal instances")
        return None

    merged_jag = Jag(jag1.urn, jag1.connector, jag1.inputs, jag1.outputs, uuid4())

    awareness1 = jag1.get_awareness()
    awareness2 = jag2.get_awareness()
    awareness1.update(awareness2)
    merged_jag.set_awareness(awareness1)

    preparing1 = jag1.get_preparing()
    preparing2 = jag2.get_preparing()
    preparing1.update(preparing2)
    merged_jag.set_preparing(preparing1)

    addressing1 = jag1.get_addressing()
    addressing2 = jag2.get_addressing()
    addressing1.update(addressing2)
    merged_jag.set_addressing(addressing1)

    is_complete = jag1.is_complete() or jag2.is_complete()
    completion_time_1 = jag1.completion_time
    completion_time_2 = jag2.completion_time
    merged_jag.set_completion(is_complete, min(completion_time_1, completion_time_2))

    merged_jag.set_estimated_preparation_duration(max(jag1.estimated_preparation_duration, jag2.estimated_preparation_duration))
    merged_jag.set_estimated_addressing_duration(max(jag1.estimated_addressing_duration, jag2.estimated_addressing_duration))

    for child1 in jag1.children:
        child2 = jag2.get_by_urn(child1.urn, child1.inputs)
        merged_child = merge_jags(child1, child2)
        merged_jag.add_child(merged_child)

    return merged_jag
