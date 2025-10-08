import os
import tempfile
from contextlib import contextmanager
from typing import Generator

TESTDIR = os.path.join(os.path.split(__file__)[0], 'tests/data')


@contextmanager
def make_temp_file(extension: str) -> Generator[str, None, None]:
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
    temp_path = temp_file.name
    temp_file.close()
    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
