#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
# The player runs these with kubectl on the control plane or on their own computer.
. ../_shared/lib.sh
kc drain "$WK_NODE" --ignore-daemonsets --delete-emptydir-data --timeout=180s
# (the maintenance would happen here)
kc uncordon "$WK_NODE"
