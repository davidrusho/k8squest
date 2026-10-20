#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Puts the machines into the state before level 73: a control plane initialised with
# Flannel installed and Ready, the worker prepared but not joined, and no bootstrap token.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
require_vms
ensure_packages "$K8S_NEW_MINOR" "$K8S_NEW_PKG" "$K8S_NEW"
log "resetting both machines"
reset_nodes
prep_nodes
log "initialising the control plane"
control_plane_up "$K8S_NEW"
# the player has to create the token they join with
vm_sh "$CP_VM" 'for t in $(kubeadm token list | awk "NR>1 {print \$1}"); do kubeadm token delete "$t" >/dev/null; done'
give_player_kubectl
export_kubeconfig
log "the cluster has one node; $WK_VM is prepared and not joined"
