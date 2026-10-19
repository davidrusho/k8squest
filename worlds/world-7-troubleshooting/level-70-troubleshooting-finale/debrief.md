# 🎓 LEVEL 70 DEBRIEF: FINALE - The Maintenance Window

**Congratulations!** You backed up the cluster's data store, verified the backup, and took a dead node out of service without waiting on it.

---

## 📊 What Happened

**Part 1: the snapshot.** etcd holds all cluster data. Its image contains `etcdctl` (a client that talks to a running member) and `etcdutl` (an administration tool that works on files), and the node does not, so you ran them with `kubectl exec` in the `etcd-<node>` static pod. etcd requires TLS client authentication, so `snapshot save` needs the endpoint and three paths, which you read from the etcd pod's own manifest. The pod can write to only two host directories, `/var/lib/etcd` and the certificate directory, so the snapshot has to be saved under one of them to exist on the node afterwards. `etcdutl snapshot status` then confirmed the file is a snapshot with keys in it, and the `maintenance-marker` ConfigMap proved it came from this cluster.

**Part 2: the lost worker.** The kubelet on `k8squest-multinode-worker` was down. `kubectl cordon` marked the node unschedulable. `kubectl drain` then asked the API server to evict the pods, but an eviction finishes only when the kubelet confirms the pod is gone, and this kubelet could not. Drain timed out. That was not a failure of the workload: the ReplicaSet does not count pods that are Terminating, so it had already created replacements, and the scheduler put them on `worker2`, the only schedulable worker.

## 🔧 The Fix

```bash
kubectl -n kube-system exec etcd-k8squest-multinode-control-plane -- etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key snapshot save /var/lib/etcd/k8squest-snapshot.db
kubectl -n kube-system exec etcd-k8squest-multinode-control-plane -- \
  etcdutl snapshot status /var/lib/etcd/k8squest-snapshot.db -w table

kubectl cordon k8squest-multinode-worker
kubectl drain k8squest-multinode-worker --ignore-daemonsets --delete-emptydir-data --force --timeout=30s
kubectl get pods -n k8squest -o wide
```

## 🎯 Key Takeaways

1. Take the backup first, before you change anything else. The Kubernetes documentation says the certificate and key paths "can be obtained from the description of the etcd Pod".
2. `etcdctl snapshot status` is deprecated; `etcdutl snapshot status` is the tool for checking a snapshot file.
3. A snapshot is only as good as the proof you tested it. Restoring is a separate, riskier procedure (World 8 on kubeadm VMs); this world only takes and verifies one.
4. `cordon` stops new pods arriving, `drain` also evicts what is there. On a node that cannot answer, drain waits and times out; the replacements are created regardless.
5. Pods on an unreachable node are not deleted automatically; they sit in Terminating or Unknown. A force delete removes the API object without any confirmation from the kubelet. Use it only when you know the node is not running that workload, because the same pod could still be running on the node that is only cut off from the network.
6. This cluster has a single control plane node, so there is no HA failover to practice. What you practised is the worker-loss half of it. Losing the control-plane node needs the snapshot you just took, and a restore.

## 📚 Official Docs

- [Operating etcd clusters for Kubernetes: backing up an etcd cluster](https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/#backing-up-an-etcd-cluster)
- [Safely Drain a Node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)
- [Force Delete StatefulSet Pods](https://kubernetes.io/docs/tasks/run-application/force-delete-stateful-set-pod/)
- [Nodes](https://kubernetes.io/docs/concepts/architecture/nodes/)

## 🏁 World 7 Complete

You diagnosed nodes, every control-plane component, DNS, the pod network, the metrics pipeline and container output on a three-node cluster.

## 🚀 What's Next

**World 8** (cluster lifecycle on kubeadm VMs, including etcd restore) is in progress.
