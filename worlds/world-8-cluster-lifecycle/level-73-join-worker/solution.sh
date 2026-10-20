#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
# The player does this by hand: kubeadm token create --print-join-command on k8squest-cp,
# then the printed command (with sudo) on k8squest-worker.
. ../_shared/lib.sh
join_worker
