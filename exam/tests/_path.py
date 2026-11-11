import subprocess
import sys
from pathlib import Path

EXAM = Path(__file__).resolve().parent.parent
if str(EXAM) not in sys.path:
    sys.path.insert(0, str(EXAM))

# The unit tests make no cluster calls. Any real subprocess is recorded and refused; a test that needs
# subprocess.run patches it (mock.patch.object over this guard). test_zzz_no_subprocess.py checks the record.
SUBPROCESS_CALLS = []
REAL_RUN = subprocess.run       # both kept for the one syntax-only `bash -n` test; nothing else may use them
REAL_POPEN = subprocess.Popen   # the real run() calls Popen, so it is restored with it


def _blocked_run(*args, **kwargs):
    SUBPROCESS_CALLS.append(args[0] if args else kwargs.get("args"))
    raise AssertionError("a unit test tried to start a real subprocess: %r" % (SUBPROCESS_CALLS[-1],))


class _BlockedPopen:
    def __init__(self, *args, **kwargs):
        _blocked_run(*args, **kwargs)


subprocess.run = _blocked_run
subprocess.Popen = _BlockedPopen
