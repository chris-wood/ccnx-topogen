import sys
import os
import json
from pydotplus.graphviz import graph_from_dot_file

class Link(object):
    def __init__(self, link_info):
        self.lid = link_info["id"]
        self.protocol = link_info["protocol"]
        self.port = link_info["port"]

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

    def add_node(self, x, v):
        print x, v
        if not isinstance(v, Forwarder):
            raise Exception("Invalid node type")
        self.nodes[x] = v

    def get_node(self, x):
        if x in self.nodes:
            return self.nodes[x]
        else:
            raise Exception("Node %s not present" % (str(x)))

    def add_edge(self, x, y):
        if not isinstance(x, Link):
            raise Exception("Invalid source node type for edge")
        if not isinstance(y, Link):
            raise Exception("Invalid destination node type for edge")
        self.edges.add((x, y))

class TopologyBuilder(object):
    def __init__(self, fname):
        self.graph = graph_from_dot_file(fname)
        self.edges = self.graph.get_edge_list()
        self.nodes = self.graph.get_node_list()

        self.net = Graph()

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

        print l1_id, l2_id

        l1 = self.net.get_node(source).get_link(l1_id)
        l2 = self.net.get_node(sink).get_link(l2_id)

        self.net.add_edge(l1, l2)

## TODO
# - implement build_ROLE functions to classify nodes
# - create class for a node and instance for each type (based on role)
# - create class for the forwarder that holds the FIB and link table
# - implement Dijkstra algorithm to propogate routes from the producer to consumer

builder = TopologyBuilder(sys.argv[1])

# 1. build networkX graph from dot file
for node_id in builder.nodes:
    node = node_id.get_label()
    builder.parse_node_label(node)

for link_id in builder.edges:
    source = str(link_id.get_source())
    sink = str(link_id.get_destination())
    builder.parse_link_label(source, sink, link_id.get_label())

# 2. propogate routes to every link in the graph (according to a routing protocol?)
# 3. update link labels
# 4. export new dot file
