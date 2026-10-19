# 🎓 LEVEL 63 DEBRIEF: Pods That Nobody Schedules

**Congratulations!** You recognised a missing scheduler from the shape of the symptoms and repaired its static pod.

---

## 📊 What Happened

The `kube-scheduler` static pod was started with `--kubeconfig=/etc/kubernetes/scheduler.cof`, a file that does not exist. The scheduler exited on start-up and went into CrashLoopBackOff. The `checkout` pods were created, but nothing assigned them to a node. That is why they were `Pending` with `<none>` in the NODE column and **no events**: when the scheduler can see a pod and cannot place it, the pod gets a `FailedScheduling` event. With no scheduler running there is nobody to write one.

## 🔧 The Fix

```bash
kubectl logs -n kube-system kube-scheduler-k8squest-multinode-control-plane
#   "command failed" err="stat /etc/kubernetes/scheduler.cof: no such file or directory"
docker exec -it k8squest-multinode-control-plane bash
vi /etc/kubernetes/manifests/kube-scheduler.yaml     # --kubeconfig=/etc/kubernetes/scheduler.conf
```

No restart command is needed. The kubelet periodically scans the manifests directory and recreates the pod when the file changes. The kubelet's crash back-off may add some seconds before the new container is running.

## 🎯 Key Takeaways

1. Pending with no node and no events: look at the scheduler. Pending with a `FailedScheduling` event: the scheduler works and the event says why it could not place the pod.
2. The scheduler "watches for newly created pods with no assigned node, and selects a node for them to run on."
3. Control-plane components on a kubeadm-style cluster are static pods. Their manifests live in `/etc/kubernetes/manifests` on the control-plane node, and `kubectl` shows read-only mirror pods of them. Deleting the mirror pod does not change anything; edit the file.
4. `kubectl logs -n kube-system <component pod>` works for a component that crashes after starting, as long as the API server is up (level 65 is what you do when it is not).
5. Setting `spec.nodeName` by hand bypasses the scheduler. It would make these pods run, and it hides the real fault.

## 📚 Official Docs

- [Kubernetes components](https://kubernetes.io/docs/concepts/overview/components/)
- [Create static Pods](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/)
- [kubeadm implementation details: static Pod manifests for control plane components](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/)
- [Troubleshooting Pods (debug Pods)](https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/)

## 🚀 Next

**Level 64:** a Deployment that creates no ReplicaSet and no pods at all.
