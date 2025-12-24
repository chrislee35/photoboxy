from collections import Counter
import unittest
import sys
sys.path.append('.')
sys.path.append('src')
from src.photoboxy.photobox_db import PhotoboxDB
from src.photoboxy.timeline_manager import TimelineManager

class TestTimelineManager(unittest.TestCase):
    def test_initialization(self) -> None:
        db: PhotoboxDB = PhotoboxDB(database_dir="/home/chris/Documents/photoboxy/.db")
        print(len(db.filepaths()))
        tlm: TimelineManager = TimelineManager(db=db, source_dir="/media/veracrypt1/imgs/photos", dest_dir="/home/chris/Documents/photoboxy/album/")
        tlm.process()
        counts: Counter[str] = tlm.count_per_month()
        print(counts)

if __name__ == '__main__':
    unittest.main()  # pyright: ignore[reportUnusedCallResult]