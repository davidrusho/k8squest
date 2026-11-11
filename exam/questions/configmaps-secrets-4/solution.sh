kubectl get secret db-creds -n k8squest -o jsonpath='{.data.password}' | base64 -d > /opt/course/k8squest/password.txt
