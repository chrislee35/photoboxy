import os
import time
from subprocess import Popen, PIPE
from multiprocessing import Process

# create a process pool for long running tasks in the background
# by default it will use os.cpu_count() as the number of workers
class Pool:
    def __init__(self, count=None):
        self.count = count or os.cpu_count()
        self.children: list[Process] = []

    def wait_for_availability(self):
        while len(self.children) >= self.count:
            finished = [x for x in self.children if not x.is_alive()]
            self.children = [x for x in self.children if x.is_alive()]
            for child in finished: child.join()
            if len(finished) == 0: time.sleep(0.1)

    def do_work(self, cmd_or_proc, args=None):
        self.wait_for_availability()
        if isinstance(cmd_or_proc, str):
            self.do_proc(self.cmd_wrapper, args=[cmd_or_proc])
        else:
            self.do_proc(cmd_or_proc, args)
    
    def cmd_wrapper(self, cmd):
        Popen(cmd, shell=True)

    def do_proc(self, proc, args=None):
        if args:
            p = Process(target=proc, args=args)
        else:
            p = Process(target=proc)
        self.children.append(p)
        p.start()
        
    def waitall(self):
        for child in self.children:
            child.join()