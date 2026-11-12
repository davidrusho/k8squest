#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on). The answer of this task is given on cka1, by solution-cka1.sh:
#   kubectl config use-context cluster1
#   kubectl config current-context > ~/cluster1-confirm.txt
#   kubectl get configmap ctx-marker -n default -o jsonpath='{.data.token}' >> ~/cluster1-confirm.txt
true
