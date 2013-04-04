#!/usr/bin/env python

'''Python port of the Foreman gem.

Knows a few extra tricks:

 * Restart process when one fails, instead of kill all others.
 * Restart all processes on file-changes.
'''

from optparse import OptionParser
import os

from heywood.manager import ProcessManager

def main(procfile, watch):
    manager = ProcessManager()
    with open(procfile) as f:
        manager.read_procfile(f)
    manager.setup_env()
    if os.path.exists('.env'):
        with open('.env') as f:
            manager.read_env(f)
    if watch:
        manager.watch(watch)
    manager.go()

def console_script():
    opts, args = parser.parse_args()
    main(opts.procfile, opts.watch)

parser = OptionParser()
parser.add_option('-w', '--watch', action='append', default=[])
parser.add_option('-f', '--procfile', default='Procfile')

if __name__ == '__main__':
    console_script()
