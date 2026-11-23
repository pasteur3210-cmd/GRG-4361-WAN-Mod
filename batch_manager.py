"""Persistent per-batch folders; archive previous batches without deleting records.

Legacy V1.1.3 data remain unchanged in records/ when a first new batch is made.
All new batches are under records/batches/<batch_id>/.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

STATE_FILE = 'active_batch.json'
BATCHES_DIR = 'batches'
BATCH_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$')


def validate_batch_id(batch_id):
    batch_id = str(batch_id).strip()
    if not BATCH_ID_RE.fullmatch(batch_id):
        raise ValueError('Batch ID must be 1–48 characters: A–Z, 0–9, underscore or hyphen; start with a letter or number.')
    if batch_id.upper() in {'LEGACY', 'DEFAULT'}:
        raise ValueError('Batch ID is reserved; choose a production lot number.')
    return batch_id


def active_batch(root):
    root = Path(root)
    state_file = root / STATE_FILE
    if not state_file.exists():
        # Preserve the pre-batch V1.1.3 workbook and records as the legacy batch.
        return 'LEGACY', root
    obj = json.loads(state_file.read_text(encoding='utf-8'))
    if obj.get('format') != 1:
        raise ValueError('Unrecognized batch state. No data reset was performed.')
    batch_id = validate_batch_id(obj['active_batch'])
    directory = root / BATCHES_DIR / batch_id
    if not directory.is_dir():
        raise FileNotFoundError(f'Active batch folder missing: {directory}. Restore it before continuing; do not create an empty replacement.')
    return batch_id, directory


def _write_state(root, batch_id):
    root = Path(root)
    fd, tmp = tempfile.mkstemp(prefix='.active_batch_', suffix='.tmp', dir=root)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump({'format': 1, 'active_batch': batch_id, 'changed_at': datetime.now().isoformat(timespec='seconds')}, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, root / STATE_FILE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def new_batch(root, batch_id, operator, physical_network_released=False):
    """Create isolated master/ledger, preserve prior workbook and approved Golden.

    GUI is responsible for a separate explicit confirmation that the previous
    batch is disconnected / restored, so new IP reuse will not collide.
    """
    from unified_store import ensure_workbook
    from default_verify import BASELINE, install_reference_if_missing, load_baseline

    root = Path(root)
    batch_id = validate_batch_id(batch_id)
    if not operator or not str(operator).strip():
        raise ValueError('Operator required to start a new batch.')
    if not physical_network_released:
        raise ValueError('Confirm all previous batch DUTs have been restored/disconnected from the test network before resetting IP allocation.')
    root.mkdir(parents=True, exist_ok=True)
    old_id, old_folder = active_batch(root)
    if old_id == batch_id:
        raise ValueError('This batch is already active.')
    target = root / BATCHES_DIR / batch_id
    if target.exists():
        raise FileExistsError(f'Batch {batch_id} already exists. Reusing an old batch ID is blocked to prevent mixing test histories.')
    target.mkdir(parents=True)
    try:
        # Preserve any user-approved Golden from the previous batch. Never silently
        # replace it with the bundled candidate or capture a new one for each DUT.
        src = old_folder / BASELINE
        if src.exists():
            load_baseline(old_folder)  # Validate before copying.
            shutil.copy2(src, target / BASELINE)
        else:
            # First-ever batch still has the packaged reference, but its approval
            # status remains an operator/site responsibility.
            install_reference_if_missing(target)
        if (target / BASELINE).exists():
            load_baseline(target)
        ensure_workbook(target)
        (target / 'batch_info.json').write_text(json.dumps({
            'batch_id': batch_id, 'operator': str(operator).strip(),
            'started_at': datetime.now().isoformat(timespec='seconds'),
            'previous_batch': old_id,
            'ip_pool': ['192.168.2.%d' % x for x in range(121,131)],
            'previous_batch_test_network_released_confirmed': True,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        # Commit the switch only after the fresh workbook and Golden are ready.
        _write_state(root, batch_id)
    except Exception:
        # Never delete an earlier batch. A failed new batch can be inspected;
        # subsequent use of same name is prevented until manually reconciled.
        raise
    return target
