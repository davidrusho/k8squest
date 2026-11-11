kubectl create clusterrole node-reader --verb=get,list,watch --resource=no
kubectl create clusterrolebinding read-nodes --clusterrole=node-reader --user=jane
