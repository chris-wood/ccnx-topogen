import sys
import os
import json
from pydotplus.graphviz import graph_from_dot_file

class Interface(object):
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

class Link(object):
    def __init__(self, link_info):
        self.lid = link_info["id"]
        self.protocol = link_info["protocol"]
        self.port = link_info["port"]

    def __eq__(self, other):
        return self.lid == other.lid and self.protocol == other.protocol and self.port == other.port

class Forwarder(object):
    def __init__(self, name):
        self.name = name
        self.routes = {}
        self.links = {}

    def add_link(self, l):
        self.links[l.lid] = l

    def get_link(self, lid):
        if lid in self.links:
            return self.links[lid]
        else:
            raise Exception("Link %s not present at %s" % (lid, str(self)))

    def add_route(self, r, lid):
        if r not in self.routes:
            self.routes[r] = []
        self.routes[r].append(lid)

    def __str__(self):
        return "FWD[%s]" % (self.name)

class Producer(Forwarder):
    def __init__(self, name, anchors):
        Forwarder.__init__(self, name)
        self.anchors = anchors

class MetisConfigGenerator(object): # metis configuration file (bash script)
    def __init__(self):
        pass

    def generate_config_for(self, forwarder):
        pass

class AthenaConfigGenerator(object): # athenactl (bash script)
    def __init__(self):
        pass

    def generate_config_for(self, forwarder):
        pass

class CCNLiteConfigGenerator(object): # ccn-ctl program (bash script)
    def __init__(self):
        pass

    def generate_config_for(self, forwarder):
        pass

class Graph(object):
    def __init__(self):
        self.nodes = {}
        self.edges = set()

    def neighbors_by_interface(self, interface):
        nset = []
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

        self.net = Graph()
        self.producers = []

        self.constructor_map = {}
        self.constructor_map["C"] = self.build_router
        self.constructor_map["R"] = self.build_router
        self.constructor_map["P"] = self.build_producer

    def build_router(self, name, links, routes = []):
        consumer = Forwarder(name)
        for link_info in links:
            consumer.add_link(Link(link_info))
        self.net.add_node(name, consumer)

    def build_producer(self, name, links, routes = []):
        producer = Producer(name, routes)
        for link_info in links:
            producer.add_link(Link(link_info))
        self.net.add_node(name, producer)
        self.producers.append(producer)

    def parse_node_label(self, label):
        data = json.loads(str(eval(label)).replace('\'','\"'))
        role = data["role"]
        name = data["name"]
        links = data["links"]
        routes = {} if "routes" not in data else data["routes"]
        return self.constructor_map[role](name, links, routes)

    def parse_link_label(self, source, sink, label):
        label = label.strip().replace("\"", "").split(",")
        l1_id = label[0]
        l2_id = label[1]

        l1 = self.net.get_node(source).get_link(l1_id)
        l2 = self.net.get_node(sink).get_link(l2_id)

        i1 = Interface(self.net.get_node(source), l1)
        i2 = Interface(self.net.get_node(sink), l2)

        self.net.add_edge(i1, i2)

    def propogate_route_from_node(self, parent_interface, interface, route):
        parent = parent_interface.node
        interface.node.add_route(route, parent_interface.node.links[parent_interface.lid.lid])

        node = interface.node
        for link_id in node.links:
            upstream_interface = Interface(node, node.links[link_id])
            neighbors = self.net.neighbors_by_interface(upstream_interface)
            neighbors = filter(lambda i : i != parent_interface, neighbors)
            for neighbor_interface in neighbors:
                self.propogate_route_from_node(upstream_interface, neighbor_interface, route)

    def propogate_routes(self):
        ''' Propogate routes from each producer to the rest of the network using DSF.
        '''
        for producer in self.producers:
            for route in producer.anchors:
                for link_id in producer.links:
                    upstream_interface = Interface(producer, producer.links[link_id])
                    neighbors = self.net.neighbors_by_interface(upstream_interface)
                    for neighbor_interface in neighbors:
                        self.propogate_route_from_node(upstream_interface, neighbor_interface, route)


if __name__ == "__main__":
    builder = TopologyBuilder(sys.argv[1])

    for node_id in builder.nodes:
        node = node_id.get_label()
        builder.parse_node_label(node)

    for link_id in builder.edges:
        source = str(link_id.get_source())
        sink = str(link_id.get_destination())
        builder.parse_link_label(source, sink, link_id.get_label())

    for node in builder.net.nodes:
        print node, builder.net.nodes[node].routes

    builder.propogate_routes()

    for node in builder.net.nodes:
        print node, builder.net.nodes[node].routes

# TODO
# 1. export new DOT file
# 2. rename Graph to Network
# 3. plug in Network to the configuration generator

