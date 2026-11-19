"""Read bounded, checksum-verified local evidence available at the requested cutoff."""
import hashlib
from pathlib import Path

from .dates import timestamp
from .research import guarded
from .research_history import strict_json


MIB = 1024 * 1024
MAX_ENTRIES = 512


def bounded_bytes(path, limit):
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError('calendar source missing, empty or exceeds size budget')
    with path.open('rb') as stream:
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError('calendar source exceeds size budget')
    return body


def load_evidence(path, cutoff, budget, schema, validate_entry):
    path = guarded(path)
    body = bounded_bytes(path, min(budget, 4 * MIB))
    budget -= len(body)
    document = strict_json(body)
    if document.get('schema_version') != schema or not isinstance(document.get('entries'), list):
        raise ValueError('invalid calendar schema')
    if len(document['entries']) > MAX_ENTRIES:
        raise ValueError('calendar version count exceeds budget')
    eligible, archived_hashes = [], {}
    for entry in document['entries']:
        if timestamp(entry['saved_at']) > cutoff:
            continue
        validate_entry(entry)
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('calendar archive path must be relative to the calendar')
        archive = guarded(path.parent / relative)
        if archive not in archived_hashes:
            raw = bounded_bytes(archive, min(budget, 32 * MIB))
            budget -= len(raw)
            archived_hashes[archive] = hashlib.sha256(raw).hexdigest()
        if archived_hashes[archive] != entry['sha256']:
            raise ValueError('calendar source checksum mismatch: ' + entry['id'])
        eligible.append(entry)
    return eligible, budget
