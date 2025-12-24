import sys
import shutil

sys.path.append('src')
from photoboxy.photoboxy import generate_album
shutil.rmtree("tests/output")
shutil.rmtree(".db")
generate_album(source_dir="tests/input", dest_dir="tests/output")
