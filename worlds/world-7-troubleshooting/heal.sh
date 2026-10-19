#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Run by the engine (and engine/reset.py, and the test harness) before a World 7 level
# is reset, so a fault an earlier level left behind cannot block the reset that follows
# (with the API server down even `kubectl apply` of the namespace fails). Each level's
# setup.sh heals again before it injects its own fault.
cd "$(dirname "$0")" || exit 1
. ./_shared/lib.sh
require_game_context || exit 1
heal_cluster
