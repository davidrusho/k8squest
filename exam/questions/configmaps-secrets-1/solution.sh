kubectl -n k8squest create cm app-config --from-literal=APP_ENV=prod --from-literal=APP_DEBUG=false
