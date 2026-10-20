#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Puts the machines into the state before level 72: no cluster, both machines prepared
# (the end state of level 71).
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
require_vms
ensure_packages "$K8S_NEW_MINOR" "$K8S_NEW_PKG" "$K8S_NEW"
log "resetting both machines"
reset_nodes
prep_nodes
log "both machines are prepared; there is no cluster"
