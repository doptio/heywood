# Pyrocfile - Simple Python impementation of Procfile manager
# Written by Chris Testa (http://testa.co/) in 2011
# Released in the Public Domain

import argparse, logging, os.path, random, re, select, signal, subprocess
import fcntl

def _new_logger(name, color=None):
    logger = logging.getLogger(name)
    hdlr = logging.StreamHandler()
    color, end_color = '\033[9%dm' % (color or random.randint(1, 6)), '\033[0m'
    formatter = logging.Formatter(color + '%(asctime)s %(name)20s |' + end_color + ' %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)
    return logger

class ProcessManager():
    def __init__(self):
        self.running = False
        self.procfile = {}
        self.processes = []
        self.loggers = {
            'system': _new_logger('system', color=9),
        }

    def start_all(self):
        for id, command in self.procfile.items():
            p = subprocess.Popen(command, shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            self.processes.append(p)
            self.loggers[p.pid] = logger = _new_logger(id)
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
                rready, _, _ = select.select(rlist, [], [], 1)
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
        except select.error:
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
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGHUP, self.signal_handler)

    def read_procfile(self, f):
        for line in f:
            name, command = line.strip().split(':', 1)
            self.procfile[name.strip()] = command.strip()

def main():
    manager = ProcessManager()
    with open('Procfile') as f:
        manager.read_procfile(f)
    manager.install_signal_handlers()
    manager.start_all()
    manager.loop()

if __name__ == '__main__':
    main()
