kubectl get no -o jsonpath='{.items[*].status.addresses[?(@.type=="InternalIP")].address}' > /opt/course/k8squest/ips.txt
