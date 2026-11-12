#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on): a fresh answer directory.
rm -rf /opt/course/kubeadm
mkdir -p /opt/course
mkdir -m 1777 /opt/course/kubeadm
