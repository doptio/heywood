'''Send gunicorn a HUP when .py files are changed.'''

import logging
import os
import pyinotify as pyi
import re
import signal
import sys
from threading import Timer

logger = logging.getLogger('heywood.watchdog')

class GenericEventHandler(pyi.ProcessEvent):
    def __init__(self, watchdirs):
        self.manager = pyi.WatchManager()
        self.wmask = pyi.IN_CREATE | pyi.IN_MODIFY | pyi.IN_MOVED_TO
        self.wpatterns = [re.compile('^[^.].*\.py$')]

        for dirname in watchdirs:
            logger.debug('watch: %s', dirname)
            self.manager.add_watch(dirname, self.wmask, rec=True)

    def loop(self):
        notifier = pyi.Notifier(self.manager, self)
        notifier.loop()

    def callback(self, event):
        raise NotImplementedError('Override this')

    def changed(self, event):
        # Add new directories to watch
        if event.dir and event.mask & pyi.IN_CREATE:
            logger.debug('watch: %s', event.pathname)
            self.manager.add_watch(event.pathname, self.wmask)
            return

        # Is this even interesting?
        for r in self.wpatterns:
            if r.match(event.name):
                break
        else:
            return

        logger.debug('change: %s %s', event.pathname, event.mask)
        self.callback(event)

    process_IN_CREATE = changed
    process_IN_MODIFY = changed
    process_IN_MOVED_TO = changed

class GunicornHUP(GenericEventHandler):
    def __init__(self, dirs):
        GenericEventHandler.__init__(self, dirs)
        self.wait_time = 250
        self.timer = None
        self.changed = set()

    def kill_it_with_fire(self):
        print_list('Changed', self.changed)
        print('HUP\'ping parent!')
        self.changed = set()
        os.kill(os.getppid(), signal.SIGHUP)

    def callback(self, event):
        self.changed.add(event.path)
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(self.wait_time / 1000.0,
                           self.kill_it_with_fire)
        self.timer.start()

def print_list(heading, elements):
    print(heading + ':')
    for e in elements:
        print('  * ' + e)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    directories = sys.argv[1:]
    print_list('Watching', directories)

    handler = GunicornHUP(directories)
    handler.loop()
