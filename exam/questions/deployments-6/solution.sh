kubectl -n k8squest set resources deploy web --requests=cpu=100m,memory=128Mi --limits=cpu=200m,memory=256Mi
