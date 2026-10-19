#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
# The player does this inside the node: docker exec -it k8squest-multinode-worker bash
docker exec k8squest-multinode-worker systemctl enable --now kubelet
