'''Send gunicorn a HUP when .py files are changed.'''

from __future__ import division, print_function, unicode_literals

import logging
import os
from glob import glob
from itertools import chain
import signal
import sys
from threading import Timer
from time import sleep

logger = logging.getLogger('heywood.watchdog')


def watch_paths(to_watch):
    while True:
        original_status = current_status = stat_paths(to_watch)

        while original_status == current_status:
            sleep(1.0)
            current_status = stat_paths(to_watch)

        changed = original_status.symmetric_difference(current_status)
        print_list('Changed', set([path for path, stat in changed]))

        print('HUP\'ping parent!')
        os.kill(os.getppid(), signal.SIGHUP)


def stat_paths(to_watch):
    all = set()
    for pattern in to_watch:
        all.update((path, os.stat(path))
                   for file_or_directory in super_glob(pattern)
                   for path in all_files(file_or_directory))
    return all


def all_files(file_or_directory):
    'return all files under file_or_directory.'
    if os.path.isdir(file_or_directory):
        return [os.path.join(dirname, filename)
                for dirname, dirnames, filenames in os.walk(file_or_directory)
                for filename in filenames]
    else:
        return [file_or_directory]


def super_glob(pattern):
    'glob that understands **/ for all sub-directories recursively.'
    pieces = pattern.split('/')
    if '**' in pieces:
        prefix = '/'.join(pieces[:pieces.index('**')])
        postfix = '/'.join(pieces[pieces.index('**') + 1:])
        roots = [dirname
                 for dirname, dirnames, filenames in os.walk(prefix)]
        patterns = [root + '/' + postfix for root in roots]
    else:
        patterns = ['/'.join(pieces)]
    return chain.from_iterable(glob(pattern) for pattern in patterns)


def print_list(heading, elements):
    print(heading + ':')
    for e in elements:
        print('  * ' + e)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    signal.signal(signal.SIGTERM, lambda signo, frame: os._exit(0))

    to_watch = [os.path.expanduser(t.decode('utf-8'))
                for t in sys.argv[1:]]
    print_list('Watching', to_watch)

    watch_paths(to_watch)
