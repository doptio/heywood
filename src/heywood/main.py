#!/usr/bin/env python

'''Python port of the Foreman gem.

Knows a few extra tricks:

 * Restart process when one fails, instead of kill all others.
 * Restart all processes on file-changes (using pyinotify).
'''

from .pyrocfile import main

def console_script():
    main()

if __name__ == '__main__':
    main()
