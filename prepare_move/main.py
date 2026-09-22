import os
from pathlib import Path, PurePosixPath
import shutil
from typing import List

from prepare_toolbox.core import get_input, set_failed, debug, set_output
from prepare_toolbox.file import get_matching_files


def __behind_symlink(path: str) -> bool:
    """
    Whether the path is inside a symbolic link to a directory (e.g. 'in/link/file' with 'in/link -> ../..').
    Moving it would take a file out of the link's target, which can be outside the working directory.
    """
    return any(os.path.islink(parent) for parent in PurePosixPath(path).parents if str(parent) != ".")


def move() -> None:
    try:
        # source glob(s) to match
        source = get_input("source")
        # destination glob to match
        destination = str(Path(get_input("destination")))
        # ignore nonexistent files and arguments
        force = get_input("force")
        allow_outside = get_input("allow-outside-working-directory")

        moved: List[str] = []

        if not allow_outside:
            # This will raise an error if the destination is outside the current working directory
            Path(os.path.abspath(destination)).relative_to(os.getcwd())
        files = get_matching_files(source, excluded=None, relative_to=None, recursive=True,
                                   allow_outside_working_dir=allow_outside)
        if len(files) == 0:
            set_failed(f"'{source}' doesn't match any files")
        debug(f"Glob: {source}, matched files: {files}")
        # Never follow symbolic links: only a link itself is moved, not what it points to
        for path in list(files):
            if __behind_symlink(path):
                debug(f"Skipping '{path}', it is inside a symbolic link")
                files.remove(path)
        if len(files) > 1 and not os.path.isdir(destination):
            # Otherwise every file is moved onto the same path and all but the last one are lost
            set_failed(f"'{source}' matches {len(files)} files, the destination "
                       f"'{Path(destination).as_posix()}' must be an existing directory")
        for path in files:
            # Into the destination if it's a directory, otherwise to the destination itself (rename)
            if os.path.isdir(destination):
                new_path = os.path.join(destination, os.path.basename(os.path.normpath(path)))
            else:
                new_path = destination
            if os.path.exists(new_path):
                if not force:
                    set_failed(f"'{Path(new_path).as_posix()}' already exists, use 'force' to overwrite")
                # Like mv: never replace a directory with a file or the other way round
                if os.path.isdir(new_path) != os.path.isdir(path):
                    kind = "a directory" if os.path.isdir(new_path) else "a file"
                    set_failed(f"Cannot overwrite '{Path(new_path).as_posix()}', it is {kind}")
                # shutil.move doesn't overwrite an existing path, remove it first
                if os.path.isdir(new_path) and not os.path.islink(new_path):
                    shutil.rmtree(new_path)
                else:
                    os.remove(new_path)
            actual_path = shutil.move(path, new_path)
            # Always '/' (also on Windows): the paths are used in other steps
            moved.append(Path(actual_path).as_posix())
        set_output("paths", moved)
    except Exception as e:
        set_failed(e)


if __name__ == "__main__":
    move()
