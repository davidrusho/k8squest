kubectl -n k8squest run fe --image=nginx --port=80 --labels="tier=frontend,env=prod"
