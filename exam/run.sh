#!/bin/sh
# Start the CKA exam practice server in the foreground (127.0.0.1:6081). Ctrl-C stops it.
cd "$(dirname "$0")" || exit 1
exec python3 -u server.py
