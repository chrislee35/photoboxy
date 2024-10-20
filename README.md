# PhotoBoxy

A simple static HTML photo album generator. 

One template, boring, is included.

It uses ffmpeg to handle videos.

It uses configuration files from JAlbum to read in comments and to ignore files.

I'm planning on adding image detection algorithms to group photos and to produce timelines of people.

# How to use

1. Have a folder of photos, videos, and documents
2. Install ffmpeg to convert videos
3. Install LibreOffice to covert documents
4. `python -m photoboxy <source directory> --dest-dir <destination directory>`
5. This will automatically resize, transcode, thumbnail all your media
6. This will also create slideshows at each tree level
7. This will also detect faces in the photos and cluster them into numbered clusters
8. To rename the clusters, you can run the face server via `python -m photoboxy.face_server`

# Todo

1. Create an algorithm to detect the best photo in a folder
2. Create a social graph of tagged faces
3. Create a time line
4. Create a geomap from exif geolocation data
5. Create an WebUI (akin to face server) to generate the photoalbum and control the clustering (or reclustering) algorithm
6. Used tagged faces as a training set for supervised face tagging


