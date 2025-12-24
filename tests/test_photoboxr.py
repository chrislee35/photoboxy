import sys
import shutil
import os

sys.path.append('src')
from photoboxy.photoboxy import generate_album
shutil.rmtree("tests/output")
shutil.rmtree(".db")
test_dir: str = "tests/input"
if os.environ.get('PHOTOBOXY_TEST_INPUT'):
    test_dir = os.environ['PHOTOBOXY_TEST_INPUT']
generate_album(source_dir=test_dir, dest_dir="tests/output")
