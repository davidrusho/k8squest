#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on).
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf"
$KC drain node01 --ignore-daemonsets --delete-emptydir-data
$KC uncordon node01
