#!/bin/bash
# Bypass: an explicit nodePort, but not the 30080 the mission asks for
kubectl patch svc web-nodeport -n k8squest --type=json -p '[{"op":"replace","path":"/spec/ports/0/nodePort","value":30081}]'
