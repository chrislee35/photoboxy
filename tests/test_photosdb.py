import unittest
import sys
import os
import shutil
sys.path.append('.')
sys.path.append('src')
from src.photoboxy.photobox_db import PhotoboxDB, Photo, Tag

class TestPhotosDB(unittest.TestCase):
    def test_initialization(self):
        if os.path.exists('tests/output/.db'):
            shutil.rmtree('tests/output/.db')
        db: PhotoboxDB = PhotoboxDB('tests/output/.db')
        tag_id: int = db.add_new_tag("test_tag")
        self.assertEqual(1, tag_id, "The first tag_id should be `1`")
        tag: Tag | None = db.get_tag(tag_id)
        self.assertIsNotNone(tag, "Tag should be defined for tag_id=1")
        tags: list[Tag] = db.tags()
        self.assertEqual(1, len(tags), "There should only be 1 tag")
        self.assertEqual("test_tag", tags[0].label, "The label of the first tag should be 'test_tag'.")

        photo: Photo | None = db.get_photo("input/master.jpg")
        self.assertIsNone(photo, "The photo object should be None")
        photo2: Photo = Photo("input/master.jpg", "2025-11-26 11:00:00", 35569, "2025-11-26 11:00:00", {}, "output/master.jpg", "2025-11-26", [])
        db.add_photo(photo2)
        photo3: Photo | None = db.get_photo("input/master.jpg")
        self.assertIsNotNone(photo3, "The photo object should not be None")
        all_photos: list[Photo] = [x for x in db.photos()]
        self.assertEqual(1, len(all_photos), "There should only be 1 photo in the list of all photos")
        res: bool = db.add_face_to_photo(photo3.filepath, 10, 10, 20, 20, None, 1)  # pyright: ignore[reportOptionalMemberAccess]
        self.assertTrue(res, "Adding face to photo should return true.")
        photo4: Photo | None = db.get_photo("input/master.jpg")
        self.assertIsNotNone(photo4, "Photo should be defined.")
        self.assertEqual(1, len(photo4.faces), "There should be 1 face tagged in the photo.")  # pyright: ignore[reportOptionalMemberAccess]
        self.assertEqual(20, photo4.faces[0].bbox.bottom, "The bottom should be at 20 px.")  # pyright: ignore[reportOptionalMemberAccess]
        tag2: Tag | None = db.get_tag(1)
        self.assertEqual(1, len(tag2.photos), "There should be 1 photo in the list of photos for this tag")  # pyright: ignore[reportOptionalMemberAccess]

        res2: bool = db.remove_face_from_photo(2, photo4.filepath)  # pyright: ignore[reportOptionalMemberAccess]
        self.assertFalse(res2, "There is no face with tag_id=2, so it should return false.")
        res3: bool = db.remove_face_from_photo(1, photo4.filepath, 30, 30)  # pyright: ignore[reportOptionalMemberAccess]
        self.assertFalse(res3, "There is no face bounding x=30, y=30, so it should return false.")
        res4: bool = db.remove_face_from_photo(1, photo4.filepath, 15, 15)  # pyright: ignore[reportOptionalMemberAccess]
        self.assertTrue(res4, "There is a face bounding x=15, y=15, so it should return true.")
        
        photo5: Photo | None = db.get_photo("input/master.jpg")
        self.assertIsNotNone(photo5, "The photo object should not be None")
        self.assertEqual(0, len(photo5.faces), "There should be no faces tagged in the photo.")  # pyright: ignore[reportOptionalMemberAccess]
        tag3: Tag | None = db.get_tag(1)
        self.assertEqual(0, len(tag3.photos), "There should be no photos in the list of photos for this tag")  # pyright: ignore[reportOptionalMemberAccess]

        # add the face back to the photo
        res5: bool = db.add_face_to_photo(photo5.filepath, 10, 10, 20, 20, None, 1)  # pyright: ignore[reportOptionalMemberAccess]
        self.assertTrue(res5, "Adding face to photo should return true.")
        photo6: Photo | None = db.get_photo("input/master.jpg")
        self.assertEqual(1, len(photo6.faces), "There should be 1 face tagged in the photo.")  # pyright: ignore[reportOptionalMemberAccess]

        res6: bool = db.remove_tag(2)
        self.assertFalse(res6, "There is no tag_id=2, so this should return false.")
        res7: bool = db.remove_tag(1)
        self.assertTrue(res7, "There is tag_id=1, so this should return true.")
        tags2: list[Tag] = db.tags()
        self.assertEqual(0, len(tags2), "There should not be any tags.")

        photo7: Photo | None = db.get_photo("input/master.jpg")
        self.assertIsNotNone(photo7, "The photo object should not be None")
        self.assertEqual(1, len(photo7.faces), "There should be still be 1 face in the photo.")  # pyright: ignore[reportOptionalMemberAccess]
        self.assertIsNone(photo7.faces[0].tag_id, "The tag_id of the face should be None.")  # pyright: ignore[reportOptionalMemberAccess]

if __name__ == '__main__':
    unittest.main()  # pyright: ignore[reportUnusedCallResult]