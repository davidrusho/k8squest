#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on): no snapshot file may exist before the task starts.
rm -f /opt/backup.db
