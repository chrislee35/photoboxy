from flask import Flask, send_file, request, redirect, jsonify
import diskcache
import json
from .template_manager import TemplateManager
from .face_tag_manager import FaceTagManager

from jinja2 import Environment, FileSystemLoader
import os
import time

loader = FileSystemLoader(searchpath=os.path.dirname(__file__)+'/templates/boring/')
env = Environment(loader=loader)

source_dir = "/home/chris/bakudan/imgs/photos"
dest_dir = "/home/chris/Jungle/photoboxy"
db = diskcache.Index(dest_dir+'/.db')
tag_manager = FaceTagManager(db)
app = Flask(__name__)

def save():
    tag_manager.save()

    faces_order = sorted(tag_manager.faces.keys(), key=lambda c: len(tag_manager.faces[c]), reverse=True)
    faces_dir = dest_dir+"/faces"

    # backup previous file if it exists
    if os.path.exists(faces_dir+"/names.js"):
        date = time.strftime("%Y%m%d%H%M%S")
        os.rename(faces_dir+"/names.js", faces_dir+f"/names-{date}.js")

    # write a javascript file that can be updated and included to replace face ids with names
    with open(faces_dir+"/names.js", 'w') as fh:
        fh.write("var names = ")
        names = {}
        for face_id in faces_order:
            names[face_id] = tag_manager.names.get(face_id, str(face_id))
        json.dump(names, fh, indent=2)
        fh.write(";\n")

@app.route('/')
def show_faces():
    # 4th and a half, create a list for the index page to keep the first image thumbname and webpage for each cluster
    faces_index = []

    # 1st, sort the clusters by length, longest first
    faces_order = sorted(tag_manager.faces.keys(), key=lambda c: len(tag_manager.faces[c]), reverse=True)
    # 5th, enumerate through the order cluster names, so that we can determine next and previous clusters for the template
    for face_id in faces_order:
        # 6th, wrap the webpage and thumbnail urls into a list of dictionaries for the template
        # this is tricky
        fewest_c = 10000 # used to add the photo with the fewest faces
        fewest = None
        for file_id, filename in enumerate(tag_manager.faces[face_id]):
            num_faces = len(tag_manager.files[filename])
            if num_faces < fewest_c:
                image_rel_thumbnail_url = f"/thumb/{face_id}/{file_id}"
                name = tag_manager.names.get(face_id, face_id)
                fewest = {'face_id': str(face_id), 'name': name, 'thumbnail': image_rel_thumbnail_url}
                fewest_c = num_faces
        if fewest:
            faces_index.append(fewest)

    # generate the index page using the "faces" template
    template = env.get_template("server_home.html")
    html = template.render(
        faces = faces_index,
        version = "0.0.1"
    )

    return html

@app.route('/face/<int:face_id>')
def show_face_images(face_id: int):
    name = tag_manager.names.get(face_id, face_id)
    images = []
    src_filenames = list(tag_manager.faces[face_id])
    for file_id, src_filename in enumerate(src_filenames):
        images.append( { 'file_id': file_id } )

    names = json.dumps(sorted(list(set([x for x in tag_manager.names.values() if not x.isnumeric()]))))
    # generate the index page using the "faces" template
    template = env.get_template("server_face.html")
    html = template.render(
        name = name,
        face_id = face_id,
        images = images,
        version = "0.0.1",
        names = names
    )
    return html

@app.route('/page/<int:face_id>/<int:file_id>')
def page(face_id:int, file_id:int):
    src_filename = list(tag_manager.faces[face_id])[file_id]
    n = p = None
    if file_id > 0:
        p = file_id - 1
    if file_id + 1 < len(list(tag_manager.faces[face_id])):
        n = file_id + 1

    basename = src_filename.split('/')[-1]
    tags = tag_manager.files[src_filename]
    data = db[src_filename]
    scale = data['metadata'].get('scale', 1.0)
    items = []
    for tag in tags:
        name = tag_manager.names.get(tag['face_id'], tag['face_id'])
        left, top, right, bottom = [int(x * scale) for x in tag['bbox']]
        width = right - left
        height = bottom - top
        items.append({'face_id': tag['face_id'], 'name': name, 'top': top, 'left': left, 'width': width, 'height': height})

    name = tag_manager.names[face_id]
    names = json.dumps(sorted(list(set([x for x in tag_manager.names.values() if not x.isnumeric()]))))
    template = env.get_template("server_page.html")
    html = template.render(
        image_name = basename,
        face_id = face_id,
        face_name = name,
        file_id = file_id,
        src_filename = src_filename,
        tags = items,
        next = n,
        prev = p,
        names = names
    )
    return html

@app.route('/thumb/<int:face_id>/<int:file_id>')
def thumbnail(face_id:int, file_id:int):
    src_filename = list(tag_manager.faces[face_id])[file_id]
    thumb = "/thumb/".join(src_filename.replace(source_dir, dest_dir).rsplit('/', 1))
    return send_file(thumb)

@app.route('/image/<int:face_id>/<int:file_id>')
def image(face_id:int, file_id:int):
    src_filename = list(tag_manager.faces[face_id])[file_id]
    img = src_filename.replace(source_dir, dest_dir)
    return send_file(img)

@app.route('/res/<path>')
def res(path: str):
    return send_file('templates/boring/res/'+path)

@app.route('/rename', methods=["POST"])
def rename():
    data = request.get_json()
    face_id = int(data['face_id'])
    name = data['name']
    tag_manager.rename_faceid(face_id, name)
    save()
    return jsonify({'status': 'OK', 'name': name})

@app.route('/retag', methods=["POST"])
def retag():
    global faces_order
    data = request.get_json()
    src_filename = data['src_filename']
    old_face_id = int(data['face_id'])
    name = data['name']
    meta = db[src_filename]
    scale = meta['metadata'].get('scale', 1.0)
    x = int(data['x']) / scale
    y = int(data['y']) / scale

    new_face_id = None
    for fid, fname in tag_manager.names.items():
        if fname == name:
            new_face_id = fid
            break

    if not new_face_id:
        new_face_id = tag_manager.add_new_facename(name)
        faces_order = sorted(tag_manager.faces.keys(), key=lambda c: len(tag_manager.faces[c]), reverse=True)

    new_file_id = tag_manager.retag(src_filename, old_face_id, new_face_id, x, y)
    save()
    return jsonify({'status': 'OK', 'new_face_id': new_face_id, 'new_file_id': new_file_id, 'name': name})

@app.route('/untag', methods=["POST"])
def untag():
    data = request.get_json()
    src_filename = data['src_filename']
    old_face_id = int(data['face_id'])
    meta = db[src_filename]
    scale = meta['metadata'].get('scale', 1.0)
    x = int(data['x']) / scale
    y = int(data['y']) / scale

    tag_manager.remove_tag(src_filename, old_face_id, x, y)
    save()
    return jsonify({'status': 'OK'})

@app.route('/tag', methods=["POST"])
def tag():
    global faces_order
    data = request.get_json()
    src_filename = data['src_filename']
    name = data['name']
    left = int(data['left'])
    top = int(data['top'])
    height = int(data['height'])
    width = int(data['width'])
    meta = db[src_filename]
    scale = meta['metadata'].get('scale', 1.0)

    x1 = left / scale
    y1 = top / scale
    x2 = (left + width) / scale
    y2 = (top + height) / scale
    bbox = [x1,y1,x2,y2]

    new_face_id = None
    for fid, fname in tag_manager.names.items():
        if fname == name:
            new_face_id = fid
            break
    if not new_face_id:
        new_face_id = tag_manager.add_new_facename(name)
        faces_order = sorted(tag_manager.faces.keys(), key=lambda c: len(tag_manager.faces[c]), reverse=True)

    tag_manager.tag_face(src_filename, bbox, new_face_id)
    save()
    return jsonify({'status': 'OK', 'face_id': new_face_id, 'name': name})

@app.route('/merge', methods=["POST"])
def merge():
    data = request.get_json()
    face_id = int(data['face_id'])
    name = data['name']

    new_face_id = None
    for fid, fname in tag_manager.names.items():
        if fname == name:
            new_face_id = fid
            break
    if not new_face_id:
        new_face_id = tag_manager.add_new_facename(name)
        faces_order = sorted(tag_manager.faces.keys(), key=lambda c: len(tag_manager.faces[c]), reverse=True)

    for filename in tag_manager.faces[face_id]:
        if filename not in tag_manager.faces[new_face_id]:
            tag_manager.faces[new_face_id].append(filename)
        for tag in tag_manager.files[filename]:
            if tag['face_id'] == face_id:
                tag['face_id'] = new_face_id

    tag_manager.names.pop(face_id)
    tag_manager.faces.pop(face_id)
    return jsonify({'status': 'OK', 'face_id': new_face_id, 'url': f'/face/{new_face_id}'})
        


if __name__ == "__main__":
    app.run(debug=True)