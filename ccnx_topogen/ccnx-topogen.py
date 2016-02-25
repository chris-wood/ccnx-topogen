import sys
import os
import json
from pydotplus.graphviz import graph_from_dot_file

class Link(object):
    def __init__(self, node, lid):
        self.node = node
        self.lid = lid

    def __str__(self):
        return self.node.name + "@" + str(self.lid)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.node.name == other.node.name and self.lid == other.lid

    def __ne__(self, other):
        return not self.__eq__(other)

class Face(object):
    def __init__(self, parent, face_info):
        self.parent = parent
        self.lid = face_info["id"]
        self.protocol = face_info["protocol"]
        self.port = face_info["port"]

    def __eq__(self, other):
        return self.lid == other.lid and self.protocol == other.protocol and self.port == other.port

    def __str__(self):
        return str(self.lid) + ":" + str(self.protocol) + "@" + str(self.port)

    def __repr__(self):
        return self.__str__()

class Forwarder(object):
    def __init__(self, name, address):
        self.name = name
        self.address = address
        self.routes = {}
        self.faces = {}

    def add_face(self, l):
        self.faces[l.lid] = l

    def get_face(self, fid):
        if fid in self.faces:
            return self.faces[fid]
        else:
            raise Exception("Face %s not present at %s" % (fid, str(self)))

    def add_route(self, r, link):
        if r not in self.routes:
            self.routes[r] = []
        self.routes[r].append(link)

    def __str__(self):
        return "FWD[%s]" % (self.name)

class Producer(Forwarder):
    def __init__(self, name, address, anchors):
        Forwarder.__init__(self, name, address)
        self.anchors = anchors

class ConfigEngine(object):
    def __init__(self):
        pass

    def execute(self, command):
        subprocess.call(command.split(" "))

class Config(object):
    ''' A configuration will be pickled down and then
    run on a forwarder. It is the responsibility of the
    orchestra slave to accept commands from the
    orchestra master to run.
    '''
    def __init__(self, engine):
        self.setups = []
        self.configures = []
        self.finals = []
        self.engine = engine

    def add_setup_command(self, command):
        self.setups.append(command)

    def add_configure_command(self, command):
        self.configures.append(command)

    def add_finalize_command(self, command):
        self.finals.append(command)

    def setup_interfaces(self):
        for setup in self.setups:
            self.engine.execute(setup)

    def configure_interfaces(self):
        for configure in self.configures:
            self.engine.execute(configure)

    def finalize(self):
        for final in self.finals:
            self.engine.execute(final)

    def __str__(self):
        return "\n".join(self.setups + self.configures + self.finals)

    def __repr__(self):
        return __str__(self)

class MetisConfigGenerator(object): # metis configuration file (bash script)
    def __init__(self):
        self.config = Config(ConfigEngine())

    # TODO: write the link creation line to the config file
    # add listener udp udp1 127.0.0.1 9696
    # add connection udp conn1 127.0.0.1 9697 127.0.0.1 9696
    # add route conn1 lci:/ 1

    def generate_config_for(self, forwarder):
        def make_connection_id(cid):
            return "conn%s" % str(cid)

        for link in forwarder.faces:
            link = forwarder.faces[link]
            cmd = "add listener %s %s %s %s" % (link.protocol, link.lid, link.parent.address, link.port)
            self.config.add_setup_command(cmd)

        index = 1
        for route_key in forwarder.routes:
            for face_pair in forwarder.routes[route_key]:
                source_face, dest_face = face_pair

                connection_id = make_connection_id(index)
                dest_face = dest_face.parent.get_face(dest_face.lid)
                source_face = source_face.parent.get_face(source_face.lid)

                cmd = "add connection %s %s %s %s %s %s" % (dest_face.protocol, connection_id, source_face.parent.address, source_face.port, dest_face.parent.address, dest_face.port)
                index += 1
                self.config.add_configure_command(cmd)

                cmd = "add route %s %s %s" % (connection_id, route_key, str(1))
                self.config.add_finalize_command(cmd)
        return self.config

class AthenaConfigGenerator(object): # athenactl (bash script)
    def __init__(self):
        pass

    def generate_config_for(self, forwarder):
        # TODO
        pass

class CCNLiteConfigGenerator(object): # ccn-ctl program (bash script)
    def __init__(self):
        pass

    def generate_config_for(self, forwarder):
        pass

class Network(object):
    def __init__(self):
        self.nodes = {}
        self.edges = set()

    def neighbors_by_interface(self, interface):
        nset = []
        interface = interface.parent.get_face(interface.lid)

        for edge in self.edges:
            if edge[0] == interface:
                nset.append(edge[1])
            elif edge[1] == interface:
                nset.append(edge[0])
        return nset

    def add_node(self, x, v):
        if not isinstance(v, Forwarder):
            raise Exception("Invalid node type")
        self.nodes[x] = v

    def get_node(self, x):
        if x in self.nodes:
            return self.nodes[x]
        else:
            raise Exception("Node %s not present" % (str(x)))

    def add_edge(self, i1, i2):
        self.edges.add((i1, i2))

class TopologyBuilder(object):
    def __init__(self, fname):
        self.graph = graph_from_dot_file(fname)
        self.edges = self.graph.get_edge_list()
        self.nodes = self.graph.get_node_list()

        self.net = Network()
        self.producers = []
        self.forwarders = []

        self.constructor_map = {}
        self.constructor_map["C"] = self.build_router
        self.constructor_map["R"] = self.build_router
        self.constructor_map["P"] = self.build_producer

    def build_router(self, name, address, faces, routes = []):
        consumer = Forwarder(name, address)
        for face_info in faces:
            consumer.add_face(Face(consumer, face_info))
        self.net.add_node(name, consumer)
        self.forwarders.append(consumer)

    def build_producer(self, name, address, faces, routes = []):
        producer = Producer(name, address, routes)
        for face_info in faces:
            producer.add_face(Face(producer, face_info))
        self.net.add_node(name, producer)
        self.producers.append(producer)
        self.forwarders.append(producer)

    def parse_node_label(self, label):
        data = json.loads(str(eval(label)).replace('\'','\"'))
        role = data["role"]
        name = data["name"]
        address = data["address"]
        faces = data["faces"]
        routes = {} if "routes" not in data else data["routes"]
        return self.constructor_map[role](name, address, faces, routes)

    def parse_link_label(self, source, sink, label):
        label = label.strip().replace("\"", "").split(",")
        l1_id = label[0]
        l2_id = label[1]

        l1 = self.net.get_node(source).get_face(l1_id)
        l2 = self.net.get_node(sink).get_face(l2_id)

        self.net.add_edge(l1, l2)

    def propogate_route_from_node(self, parent_face, interface, route):

        interface.parent.add_route(route, (interface, parent_face))

        ## TODO: comment
        node = interface.parent
        for face_id in node.faces:
            upstream_face = node.faces[face_id]
            neighbors = self.net.neighbors_by_interface(upstream_face)
            neighbors = filter(lambda i : i != parent_face, neighbors)
            for neighbor_face in neighbors:
                self.propogate_route_from_node(upstream_face, neighbor_face, route)

    def propogate_routes(self):
        ''' Propogate routes from each producer to the rest of the network using DSF.
        '''
        for producer in self.producers:
            for route in producer.anchors:
                for face_id in producer.faces:
                    ## TODO: comment
                    upstream_face = producer.faces[face_id]
                    neighbors = self.net.neighbors_by_interface(upstream_face)
                    for neighbor_face in neighbors:
                        self.propogate_route_from_node(upstream_face, neighbor_face, route)


if __name__ == "__main__":
    builder = TopologyBuilder(sys.argv[1])

    for node_id in builder.nodes:
        node = node_id.get_label()
        builder.parse_node_label(node)

    for face_id in builder.edges:
        source = str(face_id.get_source())
        sink = str(face_id.get_destination())
        builder.parse_link_label(source, sink, face_id.get_label())

    for node in builder.net.nodes:
        print node, builder.net.nodes[node].routes

    builder.propogate_routes()

    for node in builder.net.nodes:
        print node, builder.net.nodes[node].faces, builder.net.nodes[node].routes

    generator = MetisConfigGenerator()

    for forwarder in builder.forwarders:
        config = generator.generate_config_for(forwarder)
        print forwarder, "\n", config, "\n"

# TODO
# 1. write athena configuration
# 2. write tests for parsers
# 3. remove duplicate link creation
