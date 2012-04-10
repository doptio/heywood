'A menagerie of children.'

from __future__ import unicode_literals, division

import fcntl
from logging import getLogger, StreamHandler, Formatter, INFO
import os
from select import select
from select import error as SelectError
from signal import signal, SIGHUP, SIGTERM, SIGINT
from subprocess import Popen, PIPE, STDOUT

dev_null = open('/dev/null', 'r')

class Process(object):
    'I keep track of one child.'

    def __init__(self, name, command, color_no):
        self.name = name
        self.command = command
        self.logger = _new_logger(name, color_no)
        self.process = None
        self.eof = False

    def terminate(self):
        # FIXME - need process groups!
        self.process.terminate()

    def kill(self):
        # FIXME - need process groups!
        self.process.kill()

    def reap(self):
        pass

    def spawn(self):
        # FIXME - need process groups!
        self.process = Popen(self.command, shell=True,
                             stdin=dev_null, stdout=PIPE, stderr=STDOUT)
        self.eof = False
        self.log('started with pid %d', self.process.pid)

        # Make pipes non-blocking.
        fd = self.process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def fileno(self):
        return self.process.stdout.fileno()

    def drain(self):
        data = self.process.stdout.read(8192)
        if data == '':
            self.eof = True
        return data

    def log(self, *args):
        self.logger.info(*args)

def _new_logger(name, color=None):
    logger = getLogger(name)
    hdlr = StreamHandler()
    color, end_color = '\033[9%dm' % (color), '\033[0m'
    formatter = Formatter(color + '%(asctime)s %(name)20s |' + end_color + ' %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(INFO)
    return logger

class ProcessManager(object):
    'I keep track of ALL THE CHILDREN.'

    def __init__(self):
        self.children = {}
        self.syslogger = _new_logger('system', color=7)

    def go(self):
        self.install_signal_handlers()
        self.spawn_all()

        try:
            self.loop()

        finally:
            self.syslogger.info('sending SIGKILL to all children')
            for p in self.children.values():
                p.kill()

    def loop(self):
        self.running = True
        while self.running:
            readable = self.select()
            self.drain(readable)

    def select(self, timeout=1):
        pipes = dict((child.fileno(), child)
                     for child in self.children.values()
                     if not child.eof)
        try:
            readable, _, _ = select(pipes.keys(), [], [], timeout)
        except SelectError:
            readable = []
        return [pipes[fd] for fd in readable]

    def drain(self, children):
        for child in children:
            data = child.drain()
            for line in data.strip('\n').split('\n'):
                if line.strip():
                    child.log(line)

    def install_signal_handlers(self):
        # FIXME - need to reap zombies
        signal(SIGINT, self.signal_handler)
        signal(SIGTERM, self.signal_handler)
        signal(SIGHUP, self.signal_handler)

    def spawn_all(self):
        for child in self.children.values():
            child.spawn()

    def signal_handler(self, signo, frame):
        self.shutdown = True
        self.running = False

        # FIXME - escalate to SIGKILL after two attempts?
        self.syslogger.info('sending SIGTERM to all children')
        for p in self.children.values():
            p.terminate()

    def read_procfile(self, f):
        for i, line in enumerate(f):
            name, command = line.strip().split(':', 1)
            color_no = 1 + i % 6
            child = Process(name.strip(), command.strip(), color_no)
            self.children[name.strip()] = child
