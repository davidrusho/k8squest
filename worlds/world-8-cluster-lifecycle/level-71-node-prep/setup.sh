#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Puts the machines into the state before level 71: no cluster on either machine, the
# worker fully prepared, the control-plane machine with the packages and none of the
# preparation (swap on, IP forwarding off, br_netfilter not loaded or configured,
# containerd on its defaults).
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
require_vms
ensure_packages "$K8S_NEW_MINOR" "$K8S_NEW_PKG" "$K8S_NEW"
log "resetting both machines"
reset_nodes
vm_script "$WK_VM" prep-node.sh
vm_script "$CP_VM" unprep-node.sh
log "$CP_VM is unprepared; $WK_VM is ready"
