#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import division

import getopt
import pickle
import re
import sys
import uuid
import yaml

def parse_aliases(config):
    aliases = {}
    for name in config:
        if isinstance(config[name], list):
            aliases[name] = config[name]
            # fixme validate format
        elif isinstance(config[name], str):
            aliases[name] = [config[name]]
            # fixme validate format
        else:
            raise Exception('invalid aliases item: %s: %s' % (name, repr(config[name])))
    return aliases

def parse_config(items):
    aliases = items.get('aliases', {})
    if not isinstance(aliases, dict):
        raise Exception('invalid aliases format')
    aliases = parse_aliases(aliases)
    try:
        device_name = items['device_name']
    except KeyError:
        raise Exception('device_name is not set')
    try:
        shaper = items['shaper']
    except KeyError:
        raise Exception('shaper is not set')
    if not isinstance(shaper, dict):
        raise Exception('invalid shaper format')
    tree = parse_node(aliases, shaper, {'attach_to': 0, 'id': 0})
    return device_name, aliases, tree

def parse_node(aliases, node, parent):
    if 'name' in node and 'range' in node:
        raise Exception('invalid node: %s, only name or range could be set, not both')
    if 'range' in node:
        raise Exception('shaper should start with named node, not range')
    if 'rate' not in node:
        raise Exception('rate is not set for node %s' % node['name'])
    rate, ceil = parse_rate(node['rate'])
    n = dict(name = node['name'], rate = rate, ceil = ceil, parent = parent,
             id = next_class_id())
    if n['name'] in aliases or n['name'] == 'DEFAULT':
        n['attach_to'] = n['id']
    else:
        n['attach_to'] = parent['attach_to']
    if 'children' in node:
        children = []
        for child in node['children']:
            if 'range' in child:
                range_v = child['range']
                direction, start_ip, end_ip = range_v.split()
                for ip_int in range(ip_to_int(start_ip), ip_to_int(end_ip) + 1):
                    child_name = uuid.uuid4()
                    aliases[child_name] = [direction + ' ' + int_to_ip(ip_int)]
                    children.append(parse_node(aliases, {'name': child_name,
                                                         'rate': child['rate']}, n))
            else:
                children.append(parse_node(aliases, child, n))
        fill_even_rates(children, n)
        if len(children):
            n_ceil = get_ceil(n['rate'], n['ceil'])
            for child in children:
                if child['ceil'] is not None and n_ceil < get_ceil(child['rate'], child['ceil']):
                    raise Exception('node %s has lower ceil rate than one of the ceil rates of its children' % parent['name'])
            n['children'] = children
    return n

def get_ceil(rate, ceil):
    if ceil is None or ceil < rate:
        return rate
    return ceil

def fill_even_rates(nodes, parent):
    to_fill = []
    total_rate = parent['rate']
    for node in nodes:
        if node['rate'] == 'even':
            to_fill.append(node)
        else:
            total_rate -= node['rate']
    if total_rate < 0:
        raise Exception('class %s has a lower rate than the sum of rates of its children' % parent['name'])
    if len(to_fill):
        even_rate = total_rate // len(to_fill)
        for node in to_fill:
            node['rate'] = even_rate

def ip_to_int(s):
    return reduce(lambda a, v: a*256+v, map(int, s.split('.')))

def int_to_ip(s):
    r = []
    for i in range(4):
        d, m = divmod(s, 256)
        r.insert(0, str(m))
        s = d
    return '.'.join(r)

rate_re = re.compile('^(\d+)([KM])bit$', re.I)
def parse_rate(r):
    def to_rate(x):
        if isinstance(x, int):
            return x
        if x == 'even':
            return 'even'
        m = rate_re.search(x)
        if m is None:
            raise Exception('invalid rate: %s:' % r)
        n, u = m.groups()
        n = int(n)
        if u in 'kK':
            n = n*1000
        else:
            n = n*1000000
        return n
    items = r.split()
    if len(items) < 1 or len(items) > 2:
        raise Exception('invalid rate: %s' % r)
    rate = to_rate(items[0])
    if len(items) == 1:
        ceil = None
    else:
        ceil = to_rate(items[1])
        if ceil == 'even':
            raise Exception('invalid rate: %s' % r)
    return rate, ceil

class_id_seq = 0
def next_class_id():
    global class_id_seq
    class_id_seq += 1
    return class_id_seq

qdisc_id_seq = 1
def next_qdisc_id():
    global qdisc_id_seq
    qdisc_id_seq += 1
    return qdisc_id_seq

filter_prio_seq = 0
def next_filter_prio():
    global filter_prio_seq
    filter_prio_seq += 1
    return filter_prio_seq

def execute(device_name, aliases, node):
    if node['ceil'] is None:
        ceil = node['rate']
    else:
        ceil = node['ceil']
    if ceil < node['rate']:
        ceil = node['rate']
    tc_args = (device_name, node['parent']['id'], node['id'], node['rate'], ceil)
    print 'class add dev %s parent 1:%d classid 1:%d htb rate %d ceil %d' % tc_args
    if node['name'] == 'DEFAULT':
        print 'filter add dev %s proto ip prio %d parent 1:%d \\' % (device_name, next_filter_prio(), node['parent']['attach_to'])
        print ' u32 match u32 0x0 0x0 at 0 classid 1:%d' % node['id']
    else:
        for filter_spec in aliases.get(node['name'], []):
            print 'filter add dev %s proto ip prio %d parent 1:%d \\' % (device_name, next_filter_prio(), node['parent']['attach_to'])
            print ' u32 match ip %s classid 1:%d' % (filter_spec, node['id'])
    if 'children' in node:
        for child in node['children']:
            execute(device_name, aliases, child)
    else:
        args = (device_name, node['id'], next_qdisc_id())
        print 'qdisc add dev %s parent 1:%d handle %d: sfq perturb 10' % args

def main():
    opts, args = getopt.gnu_getopt(sys.argv[1:], 'n:')
    names_file = None
    for o, a in opts:
        if o == '-n':
            names_file = a
    if len(args) > 0:
        config_file = open(args[0], 'rb')
    else:
        config_file = sys.stdin
    config_documents = [doc for doc in yaml.safe_load_all(config_file)]
    if len(config_documents) > 1:
        raise Exception('configuration file should be a single YAML document')
    device_name, aliases, tree = parse_config(config_documents[0])
    print 'tc qdisc del dev %s root > /dev/null 2>&1' % device_name
    print 'tc -batch <<EOF'
    print 'qdisc add dev %s root handle 1: htb r2q 1' % device_name
    execute(device_name, aliases, tree)
    print 'EOF'
    if names_file is not None:
        names_file = open(names_file, 'wb')
        pickle.dump(collect_names({}, aliases, tree), names_file)
        names_file.close()

def collect_names(names, aliases, node):
    node_id = '1:' + str(node['id'])
    if isinstance(node['name'], uuid.UUID):
        name = aliases[node['name']][0]
    else:
        name = node['name']
    names[node_id] = name
    if 'children' in node:
        for child in node['children']:
            collect_names(names, aliases, child)
    return names

if __name__ == '__main__':
    try:
        main()
    except Exception, e:
        sys.stderr.write(str(e))
        sys.stderr.write('\n')
        sys.exit(1)
