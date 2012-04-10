'I manager children.'

from __future__ import unicode_literals, division

import fcntl
from logging import getLogger, StreamHandler, Formatter, INFO
import os
from select import select
from select import error as SelectError
from signal import signal, SIGHUP, SIGTERM, SIGINT
from subprocess import Popen, PIPE

def _new_logger(name, color=None):
    logger = getLogger(name)
    hdlr = StreamHandler()
    color, end_color = '\033[9%dm' % (color), '\033[0m'
    formatter = Formatter(color + '%(asctime)s %(name)20s |' + end_color + ' %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(INFO)
    return logger

class ProcessManager():
    def __init__(self):
        self.running = False
        self.procfile = {}
        self.processes = []
        self.loggers = {
            'system': _new_logger('system', color=7),
        }

    def start_all(self):
        for i, (name, command) in enumerate(self.procfile.items()):
            p = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
            self.processes.append(p)
            self.loggers[p.pid] = logger = _new_logger(name, color=1 + i % 6)
            logger.info('started with pid %d', p.pid)

    def loop(self):
        fp_to_p = {}
        rlist = []
        for p in self.processes:
            fp_to_p[p.stdout] = p
            fp_to_p[p.stderr] = p
            rlist.extend([p.stdout, p.stderr])

        # FIXME - Do this in start_all.
        # Make all pipes non-blocking.
        for pipe in rlist:
            fd = pipe.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        try:
            self.running = True
            while self.running:
                rready, _, _ = select(rlist, [], [], 1)
                for r in rready:
                    p = fp_to_p[r]
                    logger = self.loggers[p.pid]

                    data = r.read(8192)
                    if data == '':
                        # This pipe is empty, remove it.
                        # FIXME - reap and restart child.
                        rlist.remove(r)
                        continue

                    for line in data.strip('\n').split('\n'):
                        if line.strip():
                            logger.info(line)

        except SelectError:
            pass

        finally:
            logger = self.loggers['system']
            logger.info('sending SIGTERM to all processes')
            for p in self.processes:
                p.terminate()

    def signal_handler(self, signo, frame):
        self.running = False

    def install_signal_handlers(self):
        # FIXME - need to reap zombies
        signal(SIGINT, self.signal_handler)
        signal(SIGTERM, self.signal_handler)
        signal(SIGHUP, self.signal_handler)

    def read_procfile(self, f):
        for line in f:
            name, command = line.strip().split(':', 1)
            self.procfile[name.strip()] = command.strip()
