kubectl -n k8squest patch cm app-config -p '{"data":{"APP_ENV":"dev"}}'
