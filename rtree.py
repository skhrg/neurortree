import math
import re

import torch

class Point:
    def __init__(self, priority, coords, names, data, datanames):
        # each range is left inclusive and right exclusive, i.e., [left, right)
        self.priority = priority
        self.coords = coords
        self.names = names
        self.data = data
        self.datanames = datanames

    def is_intersect(self, dimension, left, right):
        return not (left >= self.coords[dimension*] or \
            right <= self.coords[dimension])

    def is_intersect_multi_dimension(self, ranges):
        for i in range(len(coords)):
            if ranges[i*2] >= self.coords[i] or \
                    ranges[i*2+1] <= self.coords[i]:
                return False
        return True

    def is_covered_by(self, other, ranges):
        for i in range(len(coords)):
            if (max(self.coords[i], ranges[i*2]) < \
                    max(other.coords[i], ranges[i*2]))or \
                    (min(self.coords[i], ranges[i*2+1]) > \
                    min(other.coords[i], ranges[i*2+1])):
                return False
        return True

    def __str__(self):
        result = ""
        for i in range(len(self.names)):
            result += "%s: %d, " % (self.names[i],
                self.coords[i])
        for i in range(len(self.datanames)):
            result += "%s: %s," % (self.datanames[i],
                str(self.data[i]))
        return result

def load_rules_from_file(file_name):
    rules = []
    rule_fmt = re.compile(r'^@(\d+).(\d+).(\d+).(\d+)/(\d+) '\
        r'(\d+).(\d+).(\d+).(\d+)/(\d+) ' \
        r'(\d+) : (\d+) ' \
        r'(\d+) : (\d+) ' \
        r'(0x[\da-fA-F]+)/(0x[\da-fA-F]+) ' \
        r'(.*?)')
    for idx, line in enumerate(open(file_name)):
        elements = line[1:-1].split('\t')
        line = line.replace('\t',' ')

        sip0, sip1, sip2, sip3, sip_mask_len, \
        dip0, dip1, dip2, dip3, dip_mask_len, \
        sport_begin, sport_end, \
        dport_begin, dport_end, \
        proto, proto_mask = \
        (eval(rule_fmt.match(line).group(i)) for i in range(1, 17))

        sip0 = (sip0 << 24) | (sip1 << 16) | (sip2 << 8) | sip3
        sip_begin = sip0 & (~((1 << (32 - sip_mask_len)) - 1))
        sip_end = sip0 | ((1 << (32 - sip_mask_len)) - 1)

        dip0 = (dip0 << 24) | (dip1 << 16) | (dip2 << 8) | dip3
        dip_begin = dip0 & (~((1 << (32 - dip_mask_len)) - 1))
        dip_end = dip0 | ((1 << (32 - dip_mask_len)) - 1)

        if proto_mask == 0xff:
            proto_begin = proto
            proto_end = proto
        else:
            proto_begin = 0
            proto_end = 0xff

        rules.append(Rule(idx, [sip_begin, sip_end+1,
            dip_begin, dip_end+1,
            sport_begin, sport_end+1,
            dport_begin, dport_end+1,
            proto_begin, proto_end+1]))
    return rules

class Node:
    def __init__(self, id, ranges, points, depth):
        self.id = id
        self.ranges = ranges
        self.points = points
        self.depth = depth
        self.children = []
        self.compute_state()
        self.action = None

    def compute_state(self):
        self.state = []
        for i in range(4):
            for j in range(4):
                self.state.append(((self.ranges[i] - i % 2)  >> (j * 8)) & 0xff)
        for i in range(4):
            for j in range(2):
                self.state.append(((self.ranges[i+4] - i % 2) >> (j * 8)) & 0xff)
        self.state.append(self.ranges[8])
        self.state.append(self.ranges[9] - 1)
        self.state = [[i / 256 for i in self.state]]
        self.state = torch.tensor(self.state)

    def get_state(self):
        return self.state
    
    def get_children(self):
        return self.children

    # if the node encompasses a point, return true
    # TODO: implement this method
    def encompasses(point):
        pass

    # inserts a point into a node
    def insert_point(point):
        self.points.append(point)

    def __str__(self):
        result = "ID:%d\tAction:%s\tDepth:%d\tRange:\t%s\nChildren: " % (
            self.id, str(self.action), self.depth, str(self.ranges))
        for child in self.children:
            result += str(child.id) + " "
        result += "\nPoints:\n"
        for point in self.points:
            result += str(points) + "\n"
        return  result

class Tree:
    def __init__(self, rules, leaf_threshold,
        refinements = {
            "node_merging"      : False,
            "rule_overlay"      : False,
            "region_compaction" : False,
            "rule_pushup"       : False,
            "equi_dense"        : False}):
        # hyperparameters
        self.leaf_threshold = leaf_threshold
        self.refinements = refinements

        self.rules = rules
        self.root = self.create_node(0, [0, 2**32, 0, 2**32, 0, 2**16, 0, 2**16, 0, 2**8], rules, 1)
        if (self.refinements["region_compaction"]):
            self.refinement_region_compaction(self.root)
        self.current_node = self.root
        self.nodes_to_cut = [self.root]
        self.depth = 1
        self.node_count = 1

    def create_node(self, id, ranges, rules, depth):
        node = Node(id, ranges, rules, depth)

        if self.refinements["rule_overlay"]:
            self.refinement_rule_overlay(node)

        return node

    def get_depth(self):
        return self.depth

    def get_current_node(self):
        return self.current_node

    def is_leaf(self, node):
        return len(node.rules) <= self.leaf_threshold

    def is_finish(self):
        return len(self.nodes_to_cut) == 0

    # takes a point as input, returns leaf node that you would insert the point to
    def find_insertion_node(self, point):
        cur_node = self.root

        while not self.is_leaf(cur_node):
            for child in cur_node.get_children()
                if child.encompasses(point):
                    cur_node = child
                    break
        return cur_node
        
    def update_tree(self, node, children):
        if self.refinements["node_merging"]:
            children = self.refinement_node_merging(children)

        if self.refinements["equi_dense"]:
            children = self.refinement_equi_dense(children)

        if (self.refinements["region_compaction"]):
            for child in children:
                self.refinement_region_compaction(child)

        node.children.extend(children)
        children.reverse()
        self.nodes_to_cut.pop()
        self.nodes_to_cut.extend(children)
        self.current_node = self.nodes_to_cut[-1]

    def cut_current_node(self, cut_dimension, cut_num):
        self.depth = max(self.depth, self.current_node.depth + 1)
        node = self.current_node
        node.action = (cut_dimension, cut_num)
        range_left = node.ranges[cut_dimension*2]
        range_right = node.ranges[cut_dimension*2+1]
        range_per_cut = math.ceil((range_right - range_left) / cut_num)

        children = []
        for i in range(cut_num):
            child_ranges = node.ranges.copy()
            child_ranges[cut_dimension*2] = range_left + i * range_per_cut
            child_ranges[cut_dimension*2+1] = min(range_right,
                range_left + (i+1) * range_per_cut)

            child_rules = []
            for rule in node.rules:
                if rule.is_intersect(cut_dimension,
                    child_ranges[cut_dimension*2],
                    child_ranges[cut_dimension*2+1]):
                    child_rules.append(rule)

            child = self.create_node(self.node_count, child_ranges, child_rules, node.depth + 1)
            children.append(child)
            self.node_count += 1

        self.update_tree(node, children)
        return children

    def cut_current_node_multi_dimension(self, cut_dimensions, cut_nums):
        self.depth = max(self.depth, self.current_node.depth + 1)
        node = self.current_node
        node.action = (cut_dimensions, cut_nums)

        range_per_cut = []
        for i in range(len(cut_dimensions)):
            range_left = node.ranges[cut_dimensions[i]*2]
            range_right = node.ranges[cut_dimensions[i]*2+1]
            cut_num = cut_nums[i]
            range_per_cut.append(
                math.ceil((range_right - range_left) / cut_num))

        cut_index = [0 for i in range(len(cut_dimensions))]
        children = []
        while True:
            # compute child ranges
            child_ranges = node.ranges.copy()
            for i in range(len(cut_dimensions)):
                dimension = cut_dimensions[i]
                child_ranges[dimension*2] = node.ranges[dimension*2] + \
                    cut_index[i] * range_per_cut[i]
                child_ranges[dimension*2+1] = min(node.ranges[dimension*2+1],
                    node.ranges[dimension*2] + (cut_index[i]+1) * range_per_cut[i])

            # compute child rules
            child_rules = []
            for rule in node.rules:
                if rule.is_intersect_multi_dimension(child_ranges):
                    child_rules.append(rule)

            # create new child
            child = self.create_node(self.node_count, child_ranges, child_rules, node.depth + 1)
            children.append(child)
            self.node_count += 1

            # update cut index
            cut_index[0] += 1
            i = 0
            while cut_index[i] == cut_nums[i]:
                cut_index[i] = 0
                i += 1
                if i < len(cut_nums):
                    cut_index[i] += 1
                else:
                    break

            if i == len(cut_nums):
                break# ;

        self.update_tree(node, children)
        return children

    def cut_current_node_split(self, cut_dimension, cut_position):
        self.depth = max(self.depth, self.current_node.depth + 1)
        node = self.current_node
        node.action = (cut_dimension, cut_position)
        range_left = node.ranges[cut_dimension*2]
        range_right = node.ranges[cut_dimension*2+1]
        range_per_cut = cut_position - range_left

        children = []
        for i in range(2):
            child_ranges = node.ranges.copy()
            child_ranges[cut_dimension*2] = range_left + i * range_per_cut
            child_ranges[cut_dimension*2+1] = min(range_right,
                range_left + (i+1) * range_per_cut)

            child_rules = []
            for rule in node.rules:
                if rule.is_intersect(cut_dimension,
                    child_ranges[cut_dimension*2],
                    child_ranges[cut_dimension*2+1]):
                    child_rules.append(rule)

            child = self.create_node(self.node_count, child_ranges, child_rules, node.depth + 1)
            children.append(child)
            self.node_count += 1

        self.update_tree(node, children)
        return children
        return

    def get_next_node(self):
        self.nodes_to_cut.pop()
        if len(self.nodes_to_cut) > 0:
            self.current_node = self.nodes_to_cut[-1]
        else:
            self.current_node = None
        return self.current_node

    def check_contiguous_region(self, node1, node2):
        count = 0
        for i in range(5):
            if node1.ranges[i*2+1] == node2.ranges[i*2] or \
                    node2.ranges[i*2+1] == node1.ranges[i*2]:
                if count == 1:
                    return False
                else:
                    count = 1
            elif node1.ranges[i*2] != node2.ranges[i*2] or \
                    node1.ranges[i*2+1] != node2.ranges[i*2+1]:
                return False
        if count == 0:
            return False
        return True

    def merge_region(self, node1, node2):
        for i in range(5):
            node1.ranges[i*2] = min(node1.ranges[i*2], node2.ranges[i*2])
            node1.ranges[i*2+1] = max(node1.ranges[i*2+1], node2.ranges[i*2+1])

    def refinement_node_merging(self, nodes):
        while True:
            flag = True
            merged_nodes = [nodes[0]]
            last_node = nodes[0]
            for i in range(1, len(nodes)):
                if self.check_contiguous_region(last_node, nodes[i]):
                    if set(last_node.rules) == set(nodes[i].rules):
                        self.merge_region(last_node, nodes[i])
                        flag = False
                        continue

                merged_nodes.append(nodes[i])
                last_node = nodes[i]

            nodes = merged_nodes
            if flag:
                break

        return nodes

    def refinement_rule_overlay(self, node):
        if len(node.rules) == 0 or len(node.rules) > 10000:
            return

        new_rules = []
        for i in range(len(node.rules) - 1):
            rule = node.rules[len(node.rules) -  1 - i]
            flag = False
            for j in range(0, len(node.rules) -  1 - i):
                high_priority_rule = node.rules[j]
                if rule.is_covered_by(high_priority_rule, node.ranges):
                    flag = True
                    break
            if not flag:
                new_rules.append(rule)
        new_rules.append(node.rules[0])
        new_rules.reverse()
        node.rules = new_rules

    def refinement_region_compaction(self, node):
        if len(node.rules) == 0:
            return

        new_ranges = node.rules[0].ranges.copy()
        for rule in node.rules[1:]:
            for i in range(5):
                new_ranges[i*2] = min(new_ranges[i*2], rule.ranges[i*2])
                new_ranges[i*2+1] = max(new_ranges[i*2+1], rule.ranges[i*2+1])
        for i in range(5):
            node.ranges[i*2] = max(new_ranges[i*2], node.ranges[i*2])
            node.ranges[i*2+1] = min(new_ranges[i*2+1], node.ranges[i*2+1])
        node.compute_state()

    def refinement_rule_pushup(self):
        nodes_by_layer = [None for i in range(self.depth)]

        current_layer_nodes = [self.root]
        nodes_by_layer[0] = current_layer_nodes
        for i in range(self.depth - 1):
            next_layer_nodes = []
            for node in current_layer_nodes:
                next_layer_nodes.extend(node.children)
            nodes_by_layer[i+1] = next_layer_nodes
            current_layer_nodes = next_layer_nodes

        for i in reversed(range(self.depth)):
            for node in nodes_by_layer[i]:
                if len(node.children) == 0:
                    node.pushup_rules = set(node.rules)
                else:
                    node.pushup_rules = node.children[0].pushup_rules.copy()
                    for j in range(1, len(node.children)):
                        node.pushup_rules = node.pushup_rules.intersection(node.children[j].pushup_rules)
                    for child in node.children:
                        child.pushup_rules = child.pushup_rules.difference(node.pushup_rules)

    def refinement_equi_dense(self, nodes):
        # try to merge
        nodes_copy = []
        max_rule_count = -1
        for node in nodes:
            nodes_copy.append(
                Node(node.id, node.ranges.copy(),
                    node.rules.copy(), node.depth))
            max_rule_count = max(max_rule_count, len(node.rules))
        while True:
            flag = True
            merged_nodes = [nodes_copy[0]]
            last_node = nodes_copy[0]
            for i in range(1, len(nodes_copy)):
                if self.check_contiguous_region(last_node, nodes_copy[i]):
                    rules = set(last_node.rules).union(set(nodes_copy[i].rules))
                    if len(rules) < len(last_node.rules) + len(nodes_copy[i].rules) and \
                        len(rules) < max_rule_count:
                        rules = list(rules)
                        rules.sort(key=lambda i: i.priority)
                        last_node.rules =rules
                        self.merge_region(last_node, nodes_copy[i])
                        flag = False
                        continue

                merged_nodes.append(nodes_copy[i])
                last_node = nodes_copy[i]

            nodes_copy = merged_nodes
            if flag:
                break

        # check condition
        if len(nodes_copy) <= 8:
            nodes = nodes_copy
        return nodes

    def compute_result(self, is_efficuts = False):
        if self.refinements["rule_pushup"]:
            self.refinement_rule_pushup()

        # memory space
        # header: 2 bytes
        # region boundary for non-leaf: 16 bytes
        # each child pointer: 4 bytes
        # each rule pointer: 4 bytes
        # each rule: 16 bytes
        result = {"bytes_per_rule": 0, "memory_access": 0}
        nodes = [self.root]
        while len(nodes) != 0:
            next_layer_nodes = []
            for node in nodes:
                next_layer_nodes.extend(node.children)

                # compute bytes per rule
                x = result["bytes_per_rule"]
                result["bytes_per_rule"] += 2 + len(node.children) * 4
                if not self.is_leaf(node):
                    result["bytes_per_rule"] += 16

                if self.refinements["rule_pushup"]:
                    result["bytes_per_rule"] += len(node.pushup_rules) * 4
                elif self.is_leaf(node):
                    result["bytes_per_rule"] += len(node.rules) * 4

                    if is_efficuts:
                        result["bytes_per_rule"] += len(node.rules) * 16

                # compute memory access
                if self.is_leaf(node):
                    if is_efficuts:
                        result["memory_access"] = max(result["memory_access"],
                            node.depth)
                    else:
                        result["memory_access"] = max(result["memory_access"],
                            (node.depth - 1)*2 + 1 + len(node.rules))

            nodes = next_layer_nodes
        result["bytes_per_rule"] = result["bytes_per_rule"] / len(self.rules) + 16
        if is_efficuts:
            result["bytes_per_rule"] -= 16
        return result

    def print_layers(self, layer_num = 5):
        nodes = [self.root]
        for i in range(layer_num):
            if len(nodes) == 0:
                return

            print("Layer", i)
            next_layer_nodes = []
            for node in nodes:
                print(node)
                next_layer_nodes.extend(node.children)
            nodes = next_layer_nodes

    def __str__(self):
        result = ""
        nodes = [self.root]
        while len(nodes) != 0:
            next_layer_nodes = []
            for node in nodes:
                result += "%d; %s; %s; [" % (
                    node.id, str(node.action), str(node.ranges))
                for child in node.children:
                    result += str(child.id) + " "
                result += "]\n"
                next_layer_nodes.extend(node.children)
            nodes = next_layer_nodes
        return result
