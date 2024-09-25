import diskcache
import json
import os
import shutil
import time
from .directory import Directory
from .template_manager import TemplateManager
from .pool import Pool
from .cluster import Embedder, Clusterer
from threading import Thread

class Updater:
    # through away clusters that don't have enough images to make them worth while
    # i.e., the face cluster must appear in at least {CLUSTER_THRESHOLD} images to be considered
    CLUSTER_THRESHOLD = 3

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
        self.db = diskcache.Index(dest_dir+'/.db')
        
        self.directory = Directory(fullpath, updater=self)
        self.pool = Pool()
        self.embedder = Embedder()
        self.clusterer = Clusterer()

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

    def embed(self, img):
        return self.embedder.embed(img)

    def cluster(self):
        self.state = 'clustering'
        self.timestamps['cluster_s'] = time.time()
        bboxes = []
        embeddings = []
        filenames = []
        # for every file in the database, not just those that were updated
        for filename in self.db.keys():
            # get the data
            data = self.get_data(filename)
            # see if the file has embeddings, this test is cheaper than testing if the file still exists
            if 'metadata' not in data: continue
            if 'embeddings' not in data['metadata']: continue
            # make sure that the source still exists
            if not os.path.exists(filename): continue
            # put each embedding, since an image can have multiple faces, into an embeddings list
            # keep the filename and bounding box in a list so that we can join the answer back into the metadata
            for embed in data['metadata']['embeddings']:
                filenames.append(filename)
                embeddings.append(embed['embed'])
                bboxes.append(embed['bbox'])
        # run the clustering algorithm
        self.clusterer.cluster(filenames, bboxes, embeddings, Updater.CLUSTER_THRESHOLD)
    
    def generate(self, dest_dir, template_name='boring'):
        self.state = 'generating'
        self.timestamps['gen_s'] = time.time()
        templates = TemplateManager.get_templates(template_name)
        self.directory.generate(templates, dest_dir)
        self.pool.waitall()
        # the clusterer needs to know the source dir so that it can rewrite the filenames
        # into relative urls for the images and thumbnails
        self.clusterer.generate(templates, dest_dir, self.source_dir)
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
        print("Clustering")
        
        l = 0
        while self.state in ['clustering']:
            print(".", end="", flush=True)
            l += 1
            if l == 10:
                print(("\b" * 10)+(" " * 10)+("\b" * 10), end="", flush=True)
                l = 0
            time.sleep(0.5)

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
