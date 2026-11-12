#!/bin/bash
# timeout: 900
# Runs as root on controlplane (via cka-kubeadm run-on).
kubeadm upgrade apply "$(kubeadm version -o short)" -y
