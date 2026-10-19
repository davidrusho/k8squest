# 🎓 LEVEL 67 DEBRIEF: A Node Without a Network

**Congratulations!** You read a node's Ready condition closely enough to see that the kubelet was fine and the pod network was not.

---

## 📊 What Happened

The kindnet DaemonSet (kind's CNI plugin) had been given a `nodeSelector` for the label `k8squest.io/cni=true`, which `k8squest-multinode-worker2` did not carry. The DaemonSet controller therefore removed the kindnet pod from that node, and the node's CNI configuration was gone. The kubelet kept reporting, and said exactly what was wrong: `container runtime network not ready: NetworkReady=false ... cni plugin not initialized`. A node whose runtime has no network is NotReady, and pods pinned to it stayed Pending.

## 🔧 The Fix

```bash
kubectl describe node k8squest-multinode-worker2          # Ready=False, "cni plugin not initialized"
kubectl get ds -n kube-system                             # kindnet DESIRED 2, three nodes
kubectl get ds kindnet -n kube-system -o jsonpath='{.spec.template.spec.nodeSelector}'
kubectl label node k8squest-multinode-worker2 k8squest.io/cni=true
```

The DaemonSet controller starts a kindnet pod on the node, kindnet writes the CNI configuration, and the node turns Ready.

## 🎯 Key Takeaways

1. Read the **message** of the Ready condition, not just the word NotReady. "Kubelet stopped posting node status" and "cni plugin not initialized" are different faults with different fixes.
2. A DaemonSet's DESIRED count should equal the number of nodes it is meant to run on. When it does not, look at its `nodeSelector` / `affinity` and at the node's labels and taints.
3. The CNI plugin is a per-node agent plus configuration in `/etc/cni/net.d`. Without a configuration in that directory the container runtime reports the network as not ready.
4. This is an easy fault to cause on purpose in a lab and a hard one to find in production: a label removed from a node silently takes a system DaemonSet off it.
5. Fix the cluster, not the workload. Un-pinning `edge-cache` would have hidden the broken node.

## 📚 Official Docs

- [DaemonSet: running Pods on select Nodes](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/#running-pods-on-select-nodes)
- [Network Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/)
- [Nodes: condition](https://kubernetes.io/docs/concepts/architecture/nodes/#condition)
- [Troubleshooting kubeadm](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/troubleshooting-kubeadm/)

## 🚀 Next

**Level 68:** the cluster works, but `kubectl top` shows nothing.
