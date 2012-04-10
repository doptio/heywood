# Pyrocfile - Simple Python impementation of Procfile manager
# Written by Chris Testa (http://testa.co/) in 2011
# Released in the Public Domain

import argparse, logging, os.path, random, re, select, signal, subprocess

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
    def __init__(self, procfile, concurrencies, env, cwd):
        self.procfile = procfile
        self.concurrencies = concurrencies
        self.env = env
        self.cwd = cwd
        self.processes = []
        self.loggers = {}
        self.running = False
        self.loggers['system'] = _new_logger('system', color=9)

    def start_all(self):
        for id, command in self.procfile.iteritems():
            for i in xrange(int(self.concurrencies.get(id, 1))):
                p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, env=self.env, cwd=self.cwd)
                self.processes.append(p)
                self.loggers[p.pid] = logger = _new_logger('%s.%d' % (id, i+1))
                logger.info('started with pid %d', p.pid)

    def watch(self):
        fp_to_p = {}
        rlist = []
        for p in self.processes:
            fp_to_p[p.stdout] = p
            fp_to_p[p.stderr] = p
            rlist.extend([p.stdout, p.stderr])
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

    def interrupt(self):
        self.running = False

def main():
    parser = argparse.ArgumentParser(description='Work with Procfiles.')
    parser.add_argument('--concurrency', '-c',
        help='Specify the number of each process type to run. The value passed in should be in the format process=num,process=num')
    parser.add_argument('--env', '-e',
        help='Specify an alternate environment file. You can specify more than one file by using: --env file1,file2.')
    parser.add_argument('--procfile', '-f', default='Procfile',
        help='Specify an alternate location for the application\'s Procfile. This file\'s containing directory will be assumed to be the root directory of the application.')
    args = parser.parse_args()

    procfile = {}
    with open(args.procfile) as f:
        for line in f.readlines():
            match = re.search(r'([a-zA-Z0-9_-]+):(.*)', line)
            if not match:
                raise Exception('Bad Procfile line')
            procfile[match.group(1)] = match.group(2)
    cwd = os.path.dirname(os.path.realpath(args.procfile))

    concurrencies = dict([kv.split('=') for kv in args.concurrency.split(',')]) if args.concurrency else {}

    env = None
    if args.env:
        env = {}
        for envfname in args.env.split(','):
            with open(envfname) as f:
                env.update(dict([ l.split('=') for l in f ]))
    
    process_manager = ProcessManager(procfile, concurrencies, env, cwd)
    process_manager.start_all()

    def _interrupt(signum, frame):
        print "SIGINT received"
        process_manager.interrupt()
    signal.signal(signal.SIGINT, _interrupt)
    process_manager.watch()

if __name__ == '__main__':
    main()
