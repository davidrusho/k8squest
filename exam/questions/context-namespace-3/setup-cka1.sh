#!/bin/bash
# node: cka1
# Runs as user cka1 on k8s-lab (the level starts it as that user): back to a starting context other than cluster1, and no
# earlier answer file.
set -eu
rm -f "$HOME/cluster1-confirm.txt"
other=$(kubectl config get-contexts -o name | grep -vx cluster1 | head -n 1)
[ -n "$other" ] || { echo "cka1 has no context besides cluster1"; exit 1; }
kubectl config use-context "$other"
