import os
import shutil
from typing import List

from prepare_toolbox.core import get_input, set_failed, debug, set_output
from prepare_toolbox.file import get_matching_files


def move() -> None:
    try:
        # source glob(s) to match
        source = get_input("source")
        # destination glob to match
        destination = get_input("destination")
        # ignore nonexistent files and arguments
        force = get_input("force")

        paths: List[str] = []
        files = get_matching_files(source, excluded=None, relative_to=None, recursive=True)
        if len(files) == 0:
            set_failed(f"'{source}' doesn't match any files")
        debug(f"Glob: {source}, matched files: {files}")
        for path in files:
            if os.path.isfile(path):
                if os.path.isdir(destination):
                    new_path = os.path.join(destination, os.path.basename(path))
                else:
                    new_path = destination
                if os.path.exists(new_path) and not force:
                    set_failed(f"'{new_path}' already exists, use 'force' to overwrite")
            actual_path = shutil.move(path, destination)
            paths.append(actual_path)
        set_output("paths", paths)
    except Exception as e:
        set_failed(e)


if __name__ == "__main__":
    move()
