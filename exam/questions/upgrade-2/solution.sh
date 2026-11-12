#!/bin/bash
# timeout: 300
# Runs as root on controlplane (via cka-kubeadm run-on).
kubeadm upgrade plan > /opt/course/kubeadm/upgrade-plan.txt 2>&1
