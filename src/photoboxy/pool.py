import os
import time
from subprocess import Popen, PIPE
from multiprocessing import Process

# create a process pool for long running tasks in the background
# by default it will use os.cpu_count() as the number of workers
class Pool:
    def __init__(self, count=None):
        self.count = count or os.cpu_count()
        self.children: list[Popen] = []

    def wait_for_availability(self):
        while len(self.children) >= self.count:
            finished = [x for x in self.children if x.poll() is not None]
            self.children = [x for x in self.children if x.poll() is None]
            for child in finished: child.wait()
            if len(finished) == 0: time.sleep(0.1)

    def fork_cmd(self, cmd):
        self.wait_for_availability()
        p = Popen(cmd, shell=True)
        self.children.append(p)

    def fork_proc(self, proc, args=None):
        if args:
            p = Process(target=proc, args=args)
        else:
            p = Process(target=proc)
        # make the returns compatible with Popen
        p.poll = lambda s: [None, 0][s.is_alive()]
        p.wait = p.join
        self.children.append(p)
        p.start()
        
    def waitall(self):
        for child in self.children:
            child.wait()