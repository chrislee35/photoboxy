import dbm
import json
import time
import shutil
from .directory import Directory
from .template_manager import TemplateManager
from .pool import Pool
from threading import Thread

class Updater:
    def __init__(self, fullpath, dest_dir):
        self.stats = {
            'total': {
                'folder': 1, # for the inputroot
                'image': 0,
                'video': 0,
                'note': 0,
            },
            'changed': {
                'folder': 0,
                'image': 0,
                'video': 0,
                'note': 0,
            },
            'generated': {
                'folder': 0,
                'image': 0,
                'video': 0,
                'note': 0,
            },
            'skipped': 0
        }
        self.changes = []
        self.source_dir = fullpath
        self.dest_dir = dest_dir
        self.state = 'initialized'

        # open or create database in read/write mode with synchronization on writes
        self.db = dbm.open(dest_dir+'/photoboxy.dbm', 'c', 0o666)
        self.directory = Directory(fullpath, updater=self)
        self.pool = Pool()

        self.print_stats_thread = Thread(target=self.print_stats_continuous)
        self.timestamps = {
            'init': time.time(),
            'enum_s': None,
            'enum_e': None,
            'gen_s': None,
            'gen_e': None
        }
        
    def _add_change(self, type, filename):
        self.stats['changed'][type] += 1
        self.changes.append(filename)
    
    def _add_total(self, type):
        self.stats['total'][type] += 1
        
    def _add_skip(self):
        self.stats['skipped'] += 1

    def _add_generated(self, type):
        self.stats['generated'][type] += 1
    
    def enumerate(self):
        self.state = 'enumerating'
        self.timestamps['enum_s'] = time.time()
        self.print_stats_thread.start()
        self.directory.enumerate(self)
        self.state = 'enumerated'
        self.timestamps['enum_e'] = time.time()
    
    def generate(self, dest_dir, template_name='boring'):
        self.state = 'generating'
        self.timestamps['gen_s'] = time.time()
        templates = TemplateManager.get_templates(template_name)
        self.directory.generate(templates, dest_dir)
        self.pool.waitall()
        self.state = 'generated'
        self.timestamps['gen_e'] = time.time()
        self.print_stats_thread.join()
    
    def update_template(self, dest_dir, template_name='boring'):
        templates = TemplateManager.get_templates(template_name)
        self.directory.update_template(templates, dest_dir)
        self.pool.waitall()
    
    def get_data(self, filename):
        data = self.db.get(filename)
        if data:
            data = json.loads(data)
        return data
    
    def set_data(self, filename, data):
        if not 'relpath' in data:
            relpath = filename.replace(self.source_dir, "").lstrip('/')
            data['relpath'] = relpath
        
        if 'mtime' in data.keys() and 'date' not in data.keys():
            date = data['mtime'].split(' ')[0]
            data['date'] = date

        self.db[filename] = json.dumps(data)

    def fork_proc(self, proc, args):
        self.pool.do_work(proc, args)
    
    def fork_cmd(self, cmd):
        self.pool.do_work(cmd)

    def print_stats_monitor(self):
        # TODO: figure out how to stop this if the user only wants to enumerate
        while self.state != 'generated':
            self.print_stats()
            time.sleep(1)

    def print_stats_continuous(self):
        print(f"State: {self.state}")
        print( "           Folders        Images         Videos         Notes          Total")
        last_len = 0
        while self.state in ['initialized','enumerating']:
            t = self.stats['total']
            c = self.stats['changed']
            tt = sum( [t['folder'], t['image'], t['video'], t['note']] )
            ct = sum( [c['folder'], c['image'], c['video'], c['note']] )
            folder = f"{t['folder']}/{c['folder']}"
            image = f"{t['image']}/{c['image']}"
            video = f"{t['video']}/{c['video']}"
            note = f"{t['note']}/{c['note']}"
            total = f"{tt}/{ct}"
            if last_len > 0:
                print("\b" * last_len, end="", flush=True)
            line = f"Enumerated {folder:14s} {image:14s} {video:14s} {note:14s} {total:14s}"
            last_len = len(line)
            print(line, end="", flush=True)
            time.sleep(1)
        
        print()
        print( "            Folders   Images   Videos    Notes    Total")
        last_len = 0
        while self.state in ['generating']:
            metric = self.stats['generated']
            folder = metric['folder']
            image = metric['image']
            video = metric['video']
            note = metric['note']
            total = sum([folder, image, video, note])
            if last_len > 0: print("\b" * last_len, end="", flush=True)
            line = f"Generated  {folder : 8d} {image : 8d} {video : 8d} {note : 8d} {total : 8d}"
            last_len = len(line)
            print(line, end="", flush=True)
            time.sleep(1)

    def print_stats(self):
        metric = self.stats['total']
        folder = metric['folder']
        image = metric['image']
        video = metric['video']
        note = metric['note']
        total = sum([folder, image, video, note])

        print(f"State: {self.state}")
        print( "           Folders  Images  Videos   Notes      Total")
        print(f"Enumerated {folder : 7d} {image : 7d} {video : 7d} {note : 7d} {total : 10d}")
        metric = self.stats['changed']
        folder = metric['folder']
        image = metric['image']
        video = metric['video']
        note = metric['note']
        total = sum([folder, image, video, note])
        print(f"Changed    {folder : 7d} {image : 7d} {video : 7d} {note : 7d} {total : 10d}")
        metric = self.stats['generated']
        folder = metric['folder']
        image = metric['image']
        video = metric['video']
        note = metric['note']
        total = sum([folder, image, video, note])
        print(f"Generated  {folder : 7d} {image : 7d} {video : 7d} {note : 7d} {total : 10d}")
        print(f"Enumeration took {self.timestamps['enum_e'] - self.timestamps['enum_s'] : 0.2f}s  Generation took {self.timestamps['gen_e'] - self.timestamps['gen_s'] : 0.2f}s")
