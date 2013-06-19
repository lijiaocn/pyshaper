#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import division

import getopt
import pickle
import re
import subprocess
import sys

class_re = re.compile('^class htb (\d+:\d+)\s+.*rate\s(\d+[KM]?bit)\s+ceil\s+(\d+[KM]?bit)')
rate_re = re.compile('^\s+rate\s+(\d+[KM]?bit)')

def colored(c, s):
    if c == '':
        return s
    if c == 'yellow':
        return '\033[33m' + s + '\033[0m'
    if c == 'red':
        return '\033[31m' + s + '\033[0m'
    return s

def main():
    opts, args = getopt.gnu_getopt(sys.argv[1:], 'n:')
    names_file = None
    for o, a in opts:
        if o == '-n':
            names_file = open(a, 'rb')
    if names_file is not None:
        names = pickle.load(names_file)
    else:
        names = {}
    if len(args) > 0:
        device = args[0]
    else:
        sys.stderr.write('interface name required as argument')
        sys.exit(1)
    cmdline = '/sbin/tc -s class show dev %s' % device
    tc = subprocess.Popen(cmdline.split(),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          close_fds=True)
    output = tc.stdout
    classes, root = parse_tc_output(output)
    render_tree(classes, root, names)

def parse_tc_output(output):
    classes = {}
    classid = None
    for line in output:
        m = class_re.search(line)
        if m is not None:
            classid, max_rate, ceil = m.groups()
            items = line.split()
            if items[3] == 'parent':
                parent = items[4]
            else:
                parent = None
            classes[classid] = {'parent': parent,
                                'max_rate': get_rate(max_rate),
                                'ceil': get_rate(ceil)}
            continue
        m = rate_re.search(line)
        if m is not None and classid is not None:
            rate = get_rate(m.group(1))
            classes[classid]['rate'] = rate
            classid = None
    root = None
    for classid, item in classes.iteritems():
        parent = item['parent']
        if parent:
            try:
                classes[parent]['children'].append(classid)
            except KeyError:
                classes[parent]['children'] = [classid]
        else:
            if root is None:
                root = classid
            else:
                print 'Two roots detected:', root, classid
                sys.exit(1)
    return classes, root

def get_color(r, m, c):
    if (c - r)/c < 0.05:
        return 'red'
    if (m - r)/m < 0.05:
        return 'yellow'
    return ''

def get_rate(r):
    r = r[:-3]
    if r[-1] == 'K':
        return int(r[:-1]) * 1000
    if r[-1] == 'M':
        return int(r[:-1]) * 1000000
    else:
        return int(r)

def render_tree(classes, root, names, prefix=''):
    name = names.get(root, root)
    s = name + ' ' * (50 - len(prefix)-len(name))
    rate = classes[root]['rate']
    max_rate = classes[root]['max_rate']
    ceil = classes[root]['ceil']
    color = get_color(rate, max_rate, ceil)
    sys.stdout.write(colored(color, '%s %11d %11d %11d\n' % (s, rate, max_rate,
                                                             ceil)))
    if not classes[root].has_key('children'):
        return
    children = classes[root]['children']
    children.sort()
    count = len(children)
    i = 0
    while i < count:
        if classes[children[i]]['rate'] != 0:
            if i+1 < count:
                write(prefix + u'\u251C\u2500\u2500')
                render_tree(classes, children[i], names, prefix + u'\u2502  ')
            else:
                write(prefix + u'\u2514\u2500\u2500')
                render_tree(classes, children[i], names, prefix + '   ')
        i += 1

def write(s):
    if isinstance(s, unicode):
        sys.stdout.write(s.encode('utf-8'))
    else:
        sys.stdout.write(s)

if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        sys.stderr.write(str(err) + '\n')
        sys.exit(1)
