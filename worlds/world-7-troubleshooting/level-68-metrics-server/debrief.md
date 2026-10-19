# 🎓 LEVEL 68 DEBRIEF: kubectl top Shows Nothing

**Congratulations!** You followed the resource metrics pipeline from `kubectl top` back to the kubelets and fixed the link that was broken.

---

## 📊 What Happened

`kubectl top` does not read metrics itself. It calls the `metrics.k8s.io` API, which the API server serves through an **APIService** that points at the `metrics-server` Service in `kube-system`. metrics-server in turn scrapes every node's kubelet. Here its `--kubelet-insecure-tls` argument was missing. kind's kubelets serve certificates that the cluster CA did not sign, so metrics-server could not scrape them, never became Ready, the Service had no endpoints and the APIService was unavailable. kubectl reported `Metrics API not available`.

## 🔧 The Fix

```bash
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl logs -n kube-system -l k8s-app=metrics-server        # x509: ... doesn't contain any IP SANs
kubectl patch deployment metrics-server -n kube-system --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl top nodes
kubectl top pods -n k8squest
```

## 🎯 Key Takeaways

1. The pipeline is: kubelet -> metrics-server -> `metrics.k8s.io` APIService -> `kubectl top` (and HPA, and VPA from World 6).
2. An APIService has an `Available` condition. When it is False, the message points at the Service or pod behind it.
3. metrics-server holds only the latest sample in memory. It is for `kubectl top` and autoscaling, not for history.
4. The metrics-server README says the kubelet certificate "needs to be signed by cluster Certificate Authority (or disable certificate validation by passing `--kubelet-insecure-tls`)", and describes the flag as "for testing purposes only". It is the right fix for kind and the wrong one for production.
5. Metrics for a new pod appear after a scrape interval. An empty `kubectl top pods` right after a deploy is not a fault.

## 📚 Official Docs

- [Resource metrics pipeline](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)
- [Tools for monitoring resources](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-usage-monitoring/)
- [metrics-server README](https://github.com/kubernetes-sigs/metrics-server)
- [kubectl top](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/)

## 🚀 Next

**Level 69:** a container that crashes before you can look at it.
