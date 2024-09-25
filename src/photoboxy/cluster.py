import numpy as np
import PIL.Image as PILImage
from insightface.app import FaceAnalysis
from os.path import basename
from sklearn.cluster import AgglomerativeClustering
from .items import Image
from collections import Counter
import os
import glob
import json
from shutil import copyfile

class Embedder:
    def __init__(self):
        root = '.embedder'
        self.app = FaceAnalysis(name='buffalo_sc', root=root) # use fast models in buffalo_sc
        self.app.prepare(ctx_id=0)
    
    def embed(self, image: PILImage) -> list[dict[str, float]]:
        img = np.array(image.convert('RGB'))
        faces = self.app.get(img)
        return [ {'embed': face.normed_embedding.tolist(), 'bbox': face.bbox.tolist()} for face in faces ]

class Clusterer:
    def __init__(self):
        self.clusters = {}
        self.files = {}

    def cluster(self, filenames: list[str], bboxes: list[list[float]], features: list[list[float]], threshold: int) -> list:
        if len(filenames) != len(bboxes):
            raise Exception("The length of filenames and bounding boxes must match.")
        if len(filenames) != len(features):
            raise Exception("The length of filenames and features must match.")
        
        # Cluster features
        clusters = AgglomerativeClustering(n_clusters=None, distance_threshold=1.0, linkage='single').fit_predict(features)
        # only keep clusters that have the minimum number of instances (photos)
        c = Counter(clusters)    
        keep = set([x for x in c if c[x] >= threshold])
        # save off the information needed to generate cluster pages and bounding boxes
        for cluster, filename, bbox in zip(clusters, filenames, bboxes):
            if cluster not in keep: continue
            if cluster not in self.clusters: self.clusters[cluster] = set()
            if filename not in self.files: self.files[filename] = []
            # to generate the cluster pages, you need a list of files per cluster
            self.clusters[cluster].add(filename)
            # to generate the click targets on the image page, you need a way to
            # query the clusterer if it has clusters and bounding boxes for that image
            # using get_clusters(...)
            self.files[filename].append( {'cluster_id': cluster, 'bbox': bbox} )

    def get_clusters(self, filename: str) -> list:
        return self.files.get(filename, [])
    
    def generate(self, templates, dest_dir, source_dir):
        # 1st, make the destination directories
        cluster_dir = dest_dir+'/_faces'
        res_dir = cluster_dir+'/res'
        os.makedirs(res_dir, exist_ok=True)
        # 2nd, remove previous cluster pages since the clusters may be different and not use all the same
        # cluster numbers as previous runs
        for fn in glob.glob(cluster_dir+'*.html'):
            os.unlink(cluster_dir+fn)

        # 3th, copy over the resources
        # for each resource, copy it over
        for f in os.scandir(templates['res']):
            item = f.name
            copyfile(f"{templates['res']}/{item}", f"{res_dir}/{item}")

        # 4th, sort the clusters by length, longest first
        cluster_order = sorted(self.clusters.keys(), key=lambda c: len(self.clusters[c]), reverse=True)

        # 4th and a half, create a list for the index page to keep the first image thumbname and webpage for each cluster
        cluster_index = []

        # 5th, enumerate through the order cluster names, so that we can determine next and previous clusters for the template
        for index, cluster in enumerate(cluster_order):
            # determine the next and previous clusters
            prev = next_item = None
            if index > 0:
                prev = cluster_order[index - 1]
            if index < len(cluster_order) - 1:
                next_item = cluster_order[index + 1]
            
            # 6th, wrap the webpage and thumbnail urls into a list of dictionaries for the template
            # this is tricky
            images = []
            first = True # used to add only the first thumbnail to the index page
            for filename in self.clusters[cluster]:
                image_rel_webpage_url = filename.replace(source_dir, '..')+'.html'
                image_rel_thumbnail_url = "/thumb/".join(filename.replace(source_dir, '..').rsplit('/', 1))
                rec = {'webpage': image_rel_webpage_url, 'thumbnail': image_rel_thumbnail_url}
                images.append(rec)
                # save off the first webpage, thumbnail of the cluster for an index page
                if first:
                    cluster_index.append({'webpage': str(cluster)+'.html', 'thumbnail': image_rel_thumbnail_url})
                    first = False
            
            # generate the cluster page using the "faces" template
            html = templates["faces"].render(
                face_id = cluster,
                prev = prev,
                next = next_item,
                images = images,
                version = "0.0.1"
            )

            # lastly, write the html into the cluster page file
            with open(cluster_dir+f"/{cluster}.html", 'w') as fh:
                fh.write(html)
        
        # generate the index page using the "faces" template
        html = templates["faces"].render(
            face_id = "All Faces",
            images = cluster_index,
            version = "0.0.1"
        )

        # almost lastly, write the html into the cluster index file
        with open(cluster_dir+"/index.html", 'w') as fh:
            fh.write(html)

        # write a javascript file that can be updated and included to replace face ids with names
        with open(cluster_dir+"/names.js", 'w') as fh:
            fh.write("var names = ")
            json.dump(dict([(str(x),str(x)) for x in cluster_order]), fh, indent=2)
            fh.write(";\n")

