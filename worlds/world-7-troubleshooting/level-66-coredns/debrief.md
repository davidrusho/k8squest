# 🎓 LEVEL 66 DEBRIEF: Names That Stopped Resolving

**Congratulations!** You followed a failing lookup to the cluster DNS and fixed two separate faults in it.

---

## 📊 What Happened

CoreDNS was broken twice. First the `coredns` Deployment was scaled to 0, so no pod answered on the `kube-dns` Service: lookups from `dns-client` **timed out**. Scaling it back up changed the symptom to an immediate **NXDOMAIN**, because the second fault was in the Corefile: the `kubernetes` plugin served the zone `cluster.locl`, not `cluster.local`. CoreDNS then had no authority for the cluster's names and passed them to the upstream resolver, which knows nothing about Services.

## 🔧 The Fix

```bash
kubectl scale deployment coredns -n kube-system --replicas=2
kubectl edit configmap coredns -n kube-system         # kubernetes cluster.local in-addr.arpa ip6.arpa {
kubectl rollout restart deployment/coredns -n kube-system
kubectl exec -n k8squest dns-client -- nslookup web.k8squest.svc.cluster.local
```

## 🎯 Key Takeaways

1. Test DNS from inside a pod (`kubectl exec ... nslookup`). A test from your laptop says nothing about the cluster's DNS.
2. A timeout means nobody answered (no pods, no endpoints, blocked traffic). NXDOMAIN means somebody answered and has no such name (wrong zone, wrong name, wrong namespace).
3. CoreDNS carries the label `k8s-app=kube-dns`, and its Service is called `kube-dns`, both for compatibility with the DNS server it replaced. Its configuration is the `coredns` ConfigMap in `kube-system`.
4. In the Corefile, the `kubernetes` plugin line names the cluster domain. The `reload` plugin applies a changed Corefile on its own, but allow up to two minutes; a rollout restart is immediate.
5. `kubectl logs -n kube-system -l k8s-app=kube-dns` shows what CoreDNS saw. A syntactically valid but wrong Corefile logs nothing alarming, which is why this fault needs a read of the configuration.

## 📚 Official Docs

- [Debugging DNS Resolution](https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/)
- [Customizing DNS Service](https://kubernetes.io/docs/tasks/administer-cluster/dns-custom-nameservers/)
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)

## 🚀 Next

**Level 67:** a node is NotReady and the kubelet is innocent. The pod network is missing.
