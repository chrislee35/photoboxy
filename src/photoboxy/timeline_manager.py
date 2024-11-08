import diskcache
from datetime import datetime
from collections import Counter
from os.path import dirname, basename

from jinja2 import Environment, FileSystemLoader
import os
import time
from glob import glob
from random import random

class TimelineManager:
    def __init__(self, db: diskcache.Index, source_dir: str, dest_dir: str):
        self.db = db
        self.names = db['.names']
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.timeline = []
        self.processed = False

    def process(self):
        if self.processed: return
        self.timeline = []
        for item in self.db:
            if item.startswith('.'): continue
            data = self.db[item]
            if data.get('metadata') and data['metadata'].get('DateTime') and not data['metadata']['DateTime'].startswith('0000') and not data['metadata']['DateTime'].startswith('    '):
                mdt = data['metadata']['DateTime'].replace(': ', ':0')
                self.timeline.append(
                    # by putting the datetime first, I use natural sorting instead of a lambda function
                    (datetime.strptime(mdt, '%Y:%m:%d %H:%M:%S'), item)
                )
            else:
                self.timeline.append(
                    (datetime.strptime(data['mtime'], "%Y-%m-%d %H:%M:%S UTC"), item)
                )
        self.timeline.sort()
        self.processed = True

    def count_per_month(self):
        c = Counter(
            [x[0].strftime("%Y") for x in self.timeline]
        )
        return c
    
    def folder_dates(self):
        # stage 1, get all the timestamps per folder
        folders = {}
        for (ts, item) in self.timeline:
            dn = dirname(item)
            if dn not in folders:
                folders[dn] = []
            folders[dn].append(ts.replace(hour=0, minute=0, second=0, microsecond=0))
        # stage 2, for each folder, determine the spread and the average
        dated_folders = []
        for folder in folders.keys():
            if len(folders[folder]) < 3: continue
            times = [x.timestamp() for x in folders[folder]]
            delta = max(times) - min(times)
            if delta > 7*24*60*60: continue
            avg = sum(times)/len(times)
            dated_folders.append(
                (datetime.fromtimestamp(avg).replace(hour=0, minute=0, second=0, microsecond=0),
                folder)
            )
        
        return sorted(dated_folders)

    def show_graph(self):
        self.process()
        counts = self.count_per_month()
        photos = []
        months = []
        for month in sorted(counts):
            months.append(month)
            photos.append(counts[month])

        import matplotlib.pyplot as plt
        from mpl_toolkits.axisartist.axislines import AxesZero
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(8,8), dpi=80, edgecolor='blue')
        fig.subplots_adjust(right=0.85)
        ax = fig.add_subplot(axes_class=AxesZero)
        ax.axis["right"].set_visible(False)
        ax.axis["top"].set_visible(False)

        ax.barh(range(len(photos)), photos)
        plt.yticks(range(len(months)), months)
        plt.gcf().autofmt_xdate()
        plt.title('Number of photos per year')
        plt.show()

    def find_best_photo_in_month(self, folders: list[str]):
        """ folders is a list of directories 
        we need to go through each folder, without recursion, and select the best photo
        then we need to pick the best photo across all the folders
        """
        if len(folders) == 0: return None
        best_score = 0.0
        best_photo = None
        for folder in folders:
            score, photo = self.find_best_photo_in_folder(folder)
            if score > best_score:
                best_score = score
                best_photo = photo
        return best_photo
    
    def find_best_photo_in_folder(self, folder: str) -> tuple[float, str]:
        files = glob(folder+"/*")
        best_score = 0.0
        best_photo = None
        photo_exts = ('jpg', 'jpeg')
        for fn in files:
            if fn.lower().split('.')[-1] not in photo_exts: continue
            score = self.score_photo(fn)
            if score > best_score:
                best_score = score
                best_photo = fn
        return best_score, best_photo
        
    def score_photo(self, filename):
        # grab the metadata of the file from the database
        data = self.db[self.source_dir+'/'+filename]
        # get the tags: list of (face_id, boundingbox)
        tags = data.get('tags', [])
        # we want around 5 to 6 faces in the photo
        weights = [0.0, 0.3, 0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.5, 0.3, 0.1, 0.1]
        # find the weight for each face
        weight = 0.0
        if len(tags) >= len(weights):
            weight = 0.05
        else:
            weight = weights[len(tags)]

        score = 0.0
        # for each tagged face in the photo
        for i, tag in enumerate(tags):
            # get the face_id, a number
            face_id = tag['face_id']
            face_weight = 0.0
            # see if I've mapped this face_id to a name, e.g., 3890: Chris Lee
            if face_id in self.names and not self.names[face_id].isnumeric():
                face_weight = 1.0
            # calculate the weight of the face and the weight of the number of faces
            # add it to the cumulative score
            score += face_weight * weight
        # return score with a little bit of noise, and other useless comments.
        return score + random()*0.1

    def generate_calendar(self):
        self.process()
        folder_times = self.folder_dates()
        year = 0
        calendar = []
        for (timestamp, folder) in folder_times:
            if timestamp.year != year:
                year = timestamp.year
                month = 0
                months = [ {'thumbnail': None, 'folders': []} for i in range(12) ]
                calendar.append(
                    {
                        "year": year,
                        "months": months
                    }
                )
            calendar[-1]["months"][timestamp.month-1]['folders'].append( 
                { 
                    'day': timestamp.day,
                    'folder': folder.replace(self.source_dir+'/', '')
                }
            )
        
        for year in calendar:
            for i, month in enumerate(year["months"]):
                thumbnail = None
                folders = [x['folder'] for x in month['folders']]
                photo = self.find_best_photo_in_month(folders)
                if photo:
                    thumbnail = "/thumb/".join(photo.rsplit('/', 1))
                    month['thumbnail'] = thumbnail

        loader = FileSystemLoader(searchpath=os.path.dirname(__file__)+'/templates/boring/')
        env = Environment(loader=loader)

        template = env.get_template("calendar.html")
        html = template.render(
            calendar = calendar,
            version = "0.0.1"
        )

        with open(self.dest_dir+'/calendar.html', 'w') as fh:
            fh.write(html)

if __name__ == "__main__":
    source_dir = "/home/chris/bakudan/imgs/photos"
    dest_dir = "/home/chris/Jungle/photoboxy"
    db = diskcache.Index(dest_dir+'/.db')
    timeline_manager = TimelineManager(db, source_dir, dest_dir)
    timeline_manager.generate_calendar()
    
    


 
    

