# 🎓 LEVEL 76 DEBRIEF: FINALE - Maintenance Window on the Worker

**Congratulations!** You took a node out of service, did not drop the application below its budget, and put the node back.

---

## 📊 What Happened

`kubectl drain` is two operations: it **cordons** the node (marks it unschedulable, so no new pods arrive) and then **evicts** the pods that run there. A plain `kubectl drain lima-k8squest-worker` cordoned the node and then refused, in one error that named two kinds of pods:

- **DaemonSet pods.** Flannel and kube-proxy run on every node. A DaemonSet's replacement pod would be created on the same node straight away, and the DaemonSet controller makes its pods ignore the unschedulable taint. The documentation: `--ignore-daemonsets` "skips them so that drain can complete; the Pods continue to run while you perform maintenance".
- **Local storage.** The `web` pods have an `emptyDir` volume, and its contents are lost when the pod is evicted. drain asks you to say you accept that with `--delete-emptydir-data`.

Then the **PodDisruptionBudget** paced the eviction. `web-pdb` requires 3 of the 4 replicas to be available, so drain could evict one pod, then had to wait ("Cannot evict pod as it would violate the pod's disruption budget") until the Deployment's replacement was Ready on the control plane. That retry is the feature working. Drain uses the Eviction API, which respects the budget; deleting a pod does not.

`kubectl uncordon` removed the unschedulable flag, and that is all it does. The evicted pods now live on the control plane and stay there: the scheduler places new pods, it does not rebalance running ones.

## 🔧 The Fix

```bash
kubectl drain lima-k8squest-worker                       # cordons, then refuses: local storage AND DaemonSet-managed Pods
kubectl drain lima-k8squest-worker --ignore-daemonsets   # refuses: Pods with local storage
kubectl drain lima-k8squest-worker --ignore-daemonsets --delete-emptydir-data
kubectl get nodes                                        # Ready,SchedulingDisabled: do the maintenance now
kubectl uncordon lima-k8squest-worker
kubectl get pods -n k8squest -o wide
```

## 🎯 Key Takeaways

1. Cordon stops new pods; drain also evicts the old ones. A cordoned node keeps running what it has.
2. `--ignore-daemonsets` and `--delete-emptydir-data` are consent flags: you read the refusal, you decide the consequence is fine. `--force` (for pods without a controller) deserves the same pause, because those pods are not recreated.
3. A PodDisruptionBudget only constrains voluntary disruptions such as drain. It does not protect against a node dying.
4. The documentation also recommends setting `unhealthyPodEvictionPolicy: AlwaysAllow` on budgets so that a crashing application cannot block a drain forever.
5. Do not give pods a toleration for `node.kubernetes.io/unschedulable` unless they are DaemonSet pods: they would land on the node you are draining.
6. Pods set directly to a node with `nodeName` bypass the scheduler and ignore a cordon.

## 🏁 World 8 Complete

You prepared machines for Kubernetes, bootstrapped a control plane, joined a worker, upgraded the cluster one minor version, recovered it from an etcd snapshot, and drained a node for maintenance, all with kubeadm on real virtual machines.

## 📚 Official Docs

- [Safely drain a node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)
- [Specifying a Disruption Budget for your Application](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)
- [Disruptions](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
- [kubectl drain](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_drain/)
- [Control plane node isolation](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/#control-plane-node-isolation)

## 🚀 What's Next

That is every world K8sQuest has today. To play World 8 again from the start, replay level 71: it resets both machines. To remove the machines when you are done: `limactl delete -f k8squest-cp k8squest-worker`.
