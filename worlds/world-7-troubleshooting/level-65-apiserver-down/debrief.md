# 🎓 LEVEL 65 DEBRIEF: The API Server Stopped Answering

**Congratulations!** You repaired the API server with no `kubectl` at all, working from the node and the container runtime.

---

## 📊 What Happened

The `kube-apiserver` manifest had `--etcd-servers=https://127.0.0.1:2397`, but etcd listens on port 2379. The API server process started and kept retrying a port nobody listens on, so it never became ready and every request timed out. Without the API server `kubectl` has nothing to talk to, which also rules out `kubectl logs` and `kubectl describe`. The `status-page` pods kept running throughout: containers on a node need the kubelet and the container runtime, not the control plane.

## 🔧 The Fix

```bash
docker exec -it k8squest-multinode-control-plane bash
crictl ps -a --name kube-apiserver
crictl logs <container-id> 2>&1 | tail     # grpc: ... failed to connect to {Addr: "127.0.0.1:2397" ...}
grep -E 'etcd-servers' /etc/kubernetes/manifests/kube-apiserver.yaml
grep -E 'listen-client-urls' /etc/kubernetes/manifests/etcd.yaml
vi /etc/kubernetes/manifests/kube-apiserver.yaml     # --etcd-servers=https://127.0.0.1:2379
```

## 🎯 Key Takeaways

1. When `kubectl` is dead, go one layer down: `crictl ps -a` and `crictl logs` talk to the container runtime directly, and `journalctl -u kubelet` shows what the kubelet is doing with the static pods.
2. The API server is the only component that talks to etcd. If it cannot reach its store it cannot serve requests, so read the `--etcd-servers` flag.
3. `crictl` needs no cluster, only the runtime socket. It is the exam-friendly replacement for `docker ps` on a containerd node.
4. A change to a static pod manifest restarts the pod; there is no `kubectl rollout` for it.
5. Know the order of dependencies: etcd -> API server -> everything else. Fix them in that order.
6. Keep a copy of a manifest before you edit it. This world's setup keeps pristine copies in `/root/k8squest-pristine/` on each node for exactly this reason.

## 📚 Official Docs

- [Debugging Kubernetes nodes with crictl](https://kubernetes.io/docs/tasks/debug/debug-cluster/crictl/)
- [Troubleshooting kubeadm](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/troubleshooting-kubeadm/)
- [Operating etcd clusters for Kubernetes](https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/)
- [Create static Pods](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/)

## 🚀 Next

**Level 66:** the control plane is fine, but names inside the cluster stop resolving.
