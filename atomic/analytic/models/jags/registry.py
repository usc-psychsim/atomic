from uuid import uuid4

from .jag import Jag


class JagRegistry:

    def __init__(self, jags=()):
        self.__jags = {}

        for jag in jags:
            self.load_jag(jag)

    def load_jag(self, jag):
        urn = jag['urn']
        self.__jags[urn] = jag

    def create_instance(self, urn, inputs, outputs):
        if urn not in self.__jags:
            print(f"no jag definition for {urn} in registry.")
            return

        definition = self.__jags[urn]
        uid = definition.get('id', uuid4())
        jag = JagRegistry.from_definition(definition, uid, inputs, outputs)

        if 'children' in definition:
            for child_reference in definition['children']:
                child_urn = child_reference['urn']
                child = self.create_instance(child_urn, inputs, outputs)
                if 'required' in child_reference.keys():
                    child_required = child_reference['required']
                    child.set_required(child_required)

                jag.add_child(child)

        return jag

    def create_instance_from_description(self, instance_description):
        urn = instance_description['urn']
        if urn not in self.__jags:
            print(f"no jag definition for {urn} in registry.")
            return

        definition = self.__jags[urn]
        uid = instance_description['id']
        inputs = instance_description['inputs']
        outputs = instance_description['outputs']
        jag = JagRegistry.from_definition(definition, uid, inputs, outputs)

        if 'children' in instance_description:
            for child_description in instance_description['children']:
                child = self.create_instance_from_description(child_description)
                if 'required' in child_description.keys():
                    child_required = child_description['required']
                    child.set_required(child_required)

                jag.add_child(child)

        return jag

    @staticmethod
    def from_definition(definition, uid, inputs, outputs):
        urn = definition['urn']
        connector = None
        if 'connector' in definition:
            connector = definition['connector']
        return Jag(urn, connector, inputs, outputs, uid)
