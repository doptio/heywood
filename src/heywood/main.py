#!/usr/bin/env python

'''Python port of the Foreman gem.

Knows a few extra tricks:

 * Restart process when one fails, instead of kill all others.
 * Restart all processes on file-changes (using pyinotify).
'''

from heywood.manager import ProcessManager

def main():
    manager = ProcessManager()
    with open('Procfile') as f:
        manager.read_procfile(f)
    manager.go()

def console_script():
    main()

if __name__ == '__main__':
    console_script()
