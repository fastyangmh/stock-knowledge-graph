"""Local Linux filesystem guards; locks coordinate cooperating pipeline processes."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import os
import tempfile
from .core import ROOT


def private_path(path):
    path = Path(path).absolute()
    resolved = path.resolve()
    if resolved == ROOT or ROOT.is_relative_to(resolved):
        raise ValueError("private path may not replace the project or its ancestor")
    if resolved.is_relative_to((ROOT/"data").resolve()):
        raise ValueError("private input/output may not be in public data/")
    if resolved.is_relative_to(ROOT) and not resolved.is_relative_to(ROOT/"local"/"private"):
        raise ValueError("within the repository, private output must be under local/private/")
    return resolved


@contextmanager
def exclusive_lock(resource):
    import fcntl  # This project targets Linux/NAS, not Windows.
    key = hashlib.sha256(str(Path(resource).resolve()).encode()).hexdigest()
    directory = Path(tempfile.gettempdir()) / f"stock-graph-locks-{os.getuid()}"
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory/key).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another process is using this output") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
