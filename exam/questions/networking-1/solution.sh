kubectl run tmp --image=busybox -n k8squest --rm -i --restart=Never -- wget -qO- http://web-svc > /opt/course/k8squest/body.txt
