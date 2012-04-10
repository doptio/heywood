#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Send gunicorn a HUP when .py files are changed
"""
import os
import os.path
import sys
import re
import signal
import logging

from threading import Timer
from optparse import OptionParser

try:
    import pyinotify as pyi
except ImportError:
    print >>sys.stderr, """Pyinotify package not found.
    You can try apt-get install python-pyinotify
    or maybe pip install pyinotify
    """
    raise

logger = logging.getLogger('heywood.watchdog')

class GenericEventHandler(pyi.ProcessEvent):
    """Handles events on specific dirs, then call call the callback method

    @ivar manager: The manager to use for watching new directories

    @ivar wmask: pyinotify mask to use for watching new directories
    @type wmask: int

    @ivar wpatterns: patterns that trigger action
    @type wpatterns: list of regexp
    """
    manager = None
    wmask = 0
    wpatterns = [ re.compile( '^[^.].*\.py$' ) ]

    def __init__(self, watchdirs, manager=None, callback=None):
        if not manager:
            manager = pyi.WatchManager()

        if callback and callable(callback):
            self.callback = callback

        self.manager = manager
        self.wmask = pyi.IN_CREATE | pyi.IN_MODIFY | pyi.IN_MOVED_TO

        for dirname in watchdirs:
            logger.debug("watch: %s" % dirname)
            self.manager.add_watch(dirname, self.wmask, rec=True)

    def loop(self):
        """Main loop - B{blocks}
        """
        notifier = pyi.Notifier(self.manager, self)
        notifier.loop()

    def callback(self, event):
        """Default callback does nothing
        """
        raise NotImplementedError("Override this")

    def changed(self, event):
        """Something changed, trigger callback if matching pattern
        or add dir to watchlist
        """
        # Add new directories to watch
        if event.dir and event.mask & pyi.IN_CREATE:
            logger.debug("watch: %s" % event.pathname)
            self.manager.add_watch(event.pathname, self.wmask)
            return

        # Return if none of our pattern matches
        for r in self.wpatterns:
            if r.match(event.name):
                break
        else:
            # else clause called if no break was reached
            return

        logger.debug("change: %s %s" % ( event.pathname, event.mask ))

        self.callback(event)

    process_IN_CREATE = changed
    process_IN_MODIFY = changed
    process_IN_MOVED_TO = changed

class GunicornHUP(GenericEventHandler):
    wait_time = 250
    timer = None

    def callback(self, event):
        def kill_it_with_fire():
            print('HUP\'ping parent!')
            os.kill(os.getppid(), signal.SIGHUP)

        if self.timer:
            self.timer.cancel()
        self.timer = Timer(self.wait_time / 1000.0, kill_it_with_fire)
        self.timer.start()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    handler = GunicornHUP(sys.argv[1:])
    handler.loop()
