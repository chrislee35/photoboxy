from datetime import datetime
from collections import Counter
import os
from os.path import dirname, basename
from glob import glob
from random import random
from dataclasses import dataclass

from matplotlib.axes._axes import Axes
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from mpl_toolkits.axisartist.axislines import AxesZero  # pyright: ignore[reportMissingTypeStubs]

from jinja2.environment import Template
from jinja2.environment import Environment
from jinja2.loaders import FileSystemLoader

from .photobox_db import Photo, PhotoboxDB, Tag

@dataclass
class Folder:
    day: int
    folder: str
    basename: str

@dataclass
class Month:
    thumbnail: str | None
    folders: list[Folder]

@dataclass
class Year:
    year: int
    months: list[Month]

class TimelineManager:
    def __init__(self, db: PhotoboxDB, source_dir: str, dest_dir: str):
        self.db: PhotoboxDB = db
        self.source_dir: str = source_dir
        self.dest_dir: str = dest_dir
        self.timeline: list[tuple[datetime, str]] = []
        self.processed: bool = False

    def process(self) -> None:
        if self.processed:
            return
        self.timeline = []
        for filename in self.db.filepaths():
            photo: Photo | None = self.db.get_photo(filepath=filename)
            if not photo:
                continue
            date_time: str | None  = photo.metadata.get('DateTime')
            if date_time:
                if date_time.startswith('0000') or date_time.startswith('    '):
                    # invalid date_time string, set it to None
                    date_time = None
            if date_time:
                    mdt: str = date_time.replace(': ', ':0')
                    self.timeline.append(
                        # by putting the datetime first, I use natural sorting instead of a lambda function
                        (datetime.strptime(mdt, '%Y:%m:%d %H:%M:%S'), filename)
                    )
            else:
                self.timeline.append(
                    (datetime.strptime(photo.sort_key, "%Y-%m-%d %H:%M:%S UTC"), filename)
                )
        self.timeline.sort()
        self.processed = True

    def count_per_month(self) -> Counter[str]:
        c: Counter[str] = Counter[str](
            [x[0].strftime(format="%Y") for x in self.timeline]
        )
        return c
    
    def folder_dates(self) -> list[tuple[datetime, str]]:
        # stage 1, get all the timestamps per folder
        folders: dict[str, list[datetime]] = {}
        for (ts, item) in self.timeline:
            dn: str = dirname(p=item)
            if dn not in folders:
                folders[dn] = []
            folders[dn].append(ts.replace(hour=0, minute=0, second=0, microsecond=0))
        # stage 2, for each folder, determine the spread and the average
        dated_folders: list[tuple[datetime, str]] = []
        for folder in folders.keys():
            # filter out folders with too few items
            #if len(folders[folder]) < 3: continue
            times: list[float] = [x.timestamp() for x in folders[folder]]
            avg: float = sum(times)/len(times)
            # filter out folders with too large of a spread, to prevent the algorithm from selecting the completely wrong month
            delta: float = avg - min(times)
            if delta > 60*24*60*60:
                continue

            dated_folders.append(
                (datetime.fromtimestamp(timestamp=avg).replace(hour=0, minute=0, second=0, microsecond=0),
                folder)
            )
        
        return sorted(dated_folders)

    def show_graph(self) -> None:
        self.process()
        counts: Counter[str] = self.count_per_month()
        photos: list[int] = []
        months: list[str] = []
        for month in sorted(counts):
            months.append(month)
            photos.append(counts[month])

        plt.style.use(style='dark_background')
        fig: Figure = plt.figure(figsize=(8,8), dpi=80, edgecolor='blue')  # pyright: ignore[reportUnknownMemberType]
        fig.subplots_adjust(right=0.85)
        ax: Axes = fig.add_subplot(axes_class=AxesZero)  # pyright: ignore[reportUnknownMemberType]
        # this is verified correct, regardless of what pyright says
        ax.axis["right"].set_visible(False)  # pyright: ignore[reportUnknownMemberType]
        ax.axis["top"].set_visible(False)  # pyright: ignore[reportUnknownMemberType]

        ax.barh(y=range(len(photos)), width=photos)  # pyright: ignore[reportUnusedCallResult, reportUnknownMemberType]
        plt.yticks(ticks=range(len(months)), labels=months)  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
        plt.gcf().autofmt_xdate()
        plt.title(label='Number of photos per year')  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
        plt.show()  # pyright: ignore[reportUnknownMemberType]

    def find_best_photo_in_month(self, folders: list[str]) -> str | None:
        """ folders is a list of directories 
        we need to go through each folder, without recursion, and select the best photo
        then we need to pick the best photo across all the folders
        """
        if len(folders) == 0:
            return None
        best_score: float = 0.0
        best_photo: str | None = None
        for folder in folders:
            score, photo = self.find_best_photo_in_folder(folder)
            if score > best_score:
                best_score = score
                best_photo = photo
        return best_photo
    
    def find_best_photo_in_folder(self, folder: str) -> tuple[float, str | None]:
        files: list[str] = glob(pathname=f"{self.dest_dir}/{folder}/*")
        best_score: float = -1.0
        best_photo: str | None = None
        photo_exts: tuple[str, str] = ('jpg', 'jpeg')
        for fn in files:
            if fn.lower().split(sep='.')[-1] not in photo_exts:
                continue
            score: float = self.score_photo(filename=fn)
            if score > best_score:
                best_score = score
                best_photo = fn.removeprefix(self.dest_dir).strip('/')
        return best_score, best_photo
        
    def score_photo(self, filename: str) -> float:
        # grab the metadata of the file from the database
        key: str = filename.replace(self.dest_dir, self.source_dir)
        photo: Photo | None = self.db.get_photo(filepath=key)
        if not photo:
            return -1.0
        # we want around 5 to 6 faces in the photo
        weights: list[float] = [0.0, 0.3, 0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.5, 0.3, 0.1, 0.1]
        # find the weight for each face
        weight: float = 0.5
        tags: list[int] = [ face.tag_id for face in photo.faces if face.tag_id ]
        if len(tags) < len(weights):
            weight = weights[len(tags)]

        score: float = 0.0
        # for each tagged face in the photo
        for face in photo.faces:
            # get the face_id, a number
            face_weight: float = 0.1
            # see if I've mapped this face_id to a name, e.g., 3890: Chris Lee
            if face.tag_id is None:
                continue
            tag: Tag | None = self.db.get_tag(face.tag_id)
            if tag and not str(tag.label).isnumeric():
                face_weight = 1.0
            # calculate the weight of the face and the weight of the number of faces
            # add it to the cumulative score
            score += face_weight * weight
        # return score with a little bit of noise, and other useless comments.
        return score + random()*0.1

    def generate_calendar(self) -> None:
        self.process()
        folder_times: list[tuple[datetime, str]] = self.folder_dates()
        year = 0
        calendar: list[Year] = []
        for (timestamp, folder) in folder_times:
            if timestamp.year != year:
                year: int = timestamp.year
                months: list[Month] = [ Month(thumbnail=None, folders=[]) for _ in range(12) ]
                calendar.append(Year(year=year, months=months))

            folder_path: str = folder.replace(self.source_dir+'/', '')
            folder_basename: str = basename(p=folder)
            calendar[-1].months[timestamp.month-1].folders.append(Folder(day=timestamp.day, folder=folder_path, basename=folder_basename))
        
        for year_obj in calendar:
            for month_obj in year_obj.months:
                folders: list[str] = [x.folder for x in month_obj.folders]
                photo: str | None = self.find_best_photo_in_month(folders)
                if photo:
                    thumbnail: str = "/thumb/".join(photo.rsplit(sep='/', maxsplit=1))
                    month_obj.thumbnail = thumbnail

        loader: FileSystemLoader = FileSystemLoader(searchpath=os.path.dirname(__file__)+'/templates/boring/')
        env: Environment = Environment(loader=loader)

        template: Template = env.get_template(name="calendar.html")
        html: str = template.render(
            calendar = calendar,
            version = "0.0.1"
        )

        with open(file=self.dest_dir+'/calendar.html', mode='w') as fh:
            fh.write(html)  # pyright: ignore[reportUnusedCallResult]
