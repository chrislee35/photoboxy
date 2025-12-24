import time
from multiprocessing.context import Process
from subprocess import Popen
from typing import Callable

# create a process pool for long running tasks in the background
# by default it will use os.cpu_count() as the number of workers
class Pool:
    def __init__(self, count: int=2) -> None:
        self.count: int = count
        self.children: list[Process] = []

    def wait_for_availability(self) -> None:
        while len(self.children) >= self.count:
            finished: list[Process] = [x for x in self.children if not x.is_alive()]
            self.children = [x for x in self.children if x.is_alive()]
            for child in finished:
                child.join()
            if len(finished) == 0:
                time.sleep(0.1)

    def do_work(self, cmd_or_proc: str | Callable[..., None], args: list[str] | None =None) -> None:
        self.wait_for_availability()
        if isinstance(cmd_or_proc, str):
            self.do_proc(proc=self.cmd_wrapper, args=[cmd_or_proc])
        else:
            self.do_proc(proc=cmd_or_proc, args=args)
    
    def cmd_wrapper(self, cmd: str) -> None:
        p: Popen[bytes] = Popen[bytes](cmd, shell=True)
        p.wait()  # pyright: ignore[reportUnusedCallResult]

    def do_proc(self, proc: Callable[..., None], args: list[str] | None =None) -> None:
        if args:
            p: Process = Process(target=proc, args=args)
        else:
            p: Process = Process(target=proc)
        self.children.append(p)
        p.start()
        
    def waitall(self) -> None:
        for child in self.children:
            child.join()