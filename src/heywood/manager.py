'A menagerie of children.'

from __future__ import unicode_literals, division

from collections import namedtuple
from datetime import datetime
import fcntl
from heapq import heappop, heappush
import os
from select import select
from select import error as SelectError
from signal import signal, SIGHUP, SIGCHLD, SIGINT, SIGKILL, SIGTERM
from subprocess import Popen, PIPE, STDOUT
import sys
from time import time

dev_null = open('/dev/null', 'r')

def log(color_no, name, message):
    color_on, color_off = '\033[9%dm' % color_no, '\033[0m'
    stamp = datetime.now().strftime('%H:%M:%S')
    tag = '%8s' % name
    print color_on + stamp + tag + ' | ' + color_off + message

def parse_command(cmd):
    return os.path.expandvars(cmd).split()

class BaseProcess(object):
    'I keep track of one child.'

    def __init__(self, name, command, color_no):
        self.name = name
        self.command = command
        self.color_no = color_no
        self.process = None
        self.eof = False
        self.signalled = False
        self.buffered = None

    def signal(self, signo):
        self.signalled = True
        if self.process:
            os.killpg(self.process.pid, signo)

    @property
    def alive(self):
        return self.process and self.process.poll() is None

    def reap(self):
        if self.alive:
            return False

        if self.process:
            self.process.wait()
            self.drain()
            if self.process.returncode < 0:
                self.log('killed by signal %d', -self.process.returncode)
            elif self.process.returncode > 0:
                self.log('exited with code %d', self.process.returncode)
            elif not isinstance(self, Daemon):
                self.log('exited normally')

        self.process = self.buffered = None
        return True

    def set_process_group(self):
        os.setsid()

    def spawn(self):
        if self.process:
            return

        self.process = Popen(parse_command(self.command),
                             stdin=dev_null, stdout=PIPE, stderr=STDOUT,
                             preexec_fn=self.set_process_group)
        self.signalled = False
        self.eof = False
        self.buffered = ''
        if not isinstance(self, Daemon):
            self.log('started with pid %d', self.process.pid)

        # Make pipes non-blocking.
        fd = self.process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def fileno(self):
        if self.process:
            return self.process.stdout.fileno()

    def drain(self):
        if not self.process:
            return

        try:
            data = self.process.stdout.read(8192)
        except IOError:
            return

        data = data.decode('utf-8', 'replace')
        if data == '':
            self.eof = True

        self.buffered += data
        while '\n' in self.buffered:
            line, self.buffered = self.buffered.split('\n', 1)
            if line.strip():
                self.log('%s', line)

    def log(self, message, *args):
        log(self.color_no, self.name, message % args)

system_color_no = 7

class Process(BaseProcess):
    pass

class Daemon(BaseProcess):
    def __init__(self, name, command):
        BaseProcess.__init__(self, name, command, system_color_no)

class WatchdogProcess(Daemon):
    def __init__(self, directories):
        command = '{} -u -m heywood.watchdog {}'.format(sys.executable,
                                                        ' '.join(directories))
        Daemon.__init__(self, 'watch', command)

Deferred = namedtuple('Deferred', 'ready callback')

class ProcessManager(object):
    'I keep track of ALL THE CHILDREN.'

    def __init__(self):
        self.children = []
        self.deferred = []
        self.shutdown = False
        self.auto_respawn = True

    def go(self):
        self.install_signal_handlers()
        self.spawn_all()
        try:
            self.loop()
        finally:
            # This is here in case there are bugs inhere somewhere.
            self.signal_all(SIGKILL, BaseProcess, silent=True)

    def loop(self):
        while self.children:
            self.do_ready_deferreds()

            readable = self.select()
            self.drain(readable)

    def do_ready_deferreds(self):
        while self.deferred and self.deferred[0].ready < time():
            job = heappop(self.deferred)
            job.callback()

    def defer(self, ready, callback):
        heappush(self.deferred, Deferred(ready, callback))

    def reap_zombies(self):
        for child in self.children:
            if not child.alive:
                child.reap()
                if self.shutdown:
                    continue
                if self.auto_respawn or child.signalled:
                    self.defer(time() + 1, child.spawn)

        if self.shutdown:
            self.children = [c for c in self.children if c.alive]

    def select(self, timeout=1):
        pipes = dict((child.fileno(), child)
                     for child in self.children
                     if not child.eof)
        if not pipes:
            return []
        fds = filter(None, pipes.keys())
        try:
            readable, _, _ = select(fds, [], [], timeout)
        except SelectError:
            readable = []
        return [pipes[fd] for fd in readable]

    def drain(self, children):
        for child in children:
            child.drain()

    def install_signal_handlers(self):
        signal(SIGINT, self.termination_handler)
        signal(SIGTERM, self.termination_handler)
        signal(SIGHUP, self.restart_handler)
        signal(SIGCHLD, self.zombie_handler)

    def spawn_all(self):
        for child in self.children:
            if not child.alive:
                child.spawn()

    def zombie_handler(self, signo, frame):
        self.defer(0, self.reap_zombies)

    def restart_all(self):
        self.signal_all(SIGTERM, Process)
        self.log('re-spawning crashed children')
        self.spawn_all()

    def restart_handler(self, signo, frame):
        self.defer(0, self.restart_all)

    def termination_handler(self, signo, frame):
        if self.shutdown:
            self.signal_all(SIGKILL, BaseProcess)
        else:
            self.signal_all(SIGTERM, BaseProcess)
        self.shutdown = True

    def signal_all(self, signo, klass, silent=False):
        if not silent:
            self.log('sending signal %d to all children', signo)
        for child in self.children:
            if isinstance(child, klass):
                child.signal(signo)

    def setup_env(self):
        os.environ['PYTHONUNBUFFERED'] = 'true'

    def read_env(self, f):
        for line in f:
            name, value = line.split('=', 1)
            os.environ[name.strip()] = value.strip()

    def read_procfile(self, f):
        for i, line in enumerate(f):
            name, command = line.strip().split(':', 1)
            color_no = 1 + i % 6
            child = Process(name.strip(), command.strip(), color_no)
            self.children.append(child)

    def log(self, message, *args):
        log(system_color_no, 'system', message % args)

    def watch(self, directories):
        self.children.append(WatchdogProcess(directories))
        self.auto_respawn = False
