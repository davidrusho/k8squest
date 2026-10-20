# 🎓 LEVEL 74 DEBRIEF: One Minor Version Up

**Congratulations!** You upgraded a two-node kubeadm cluster from Kubernetes v1.36.5 to v1.37.1 in the documented order, and the workload never noticed.

---

## 📊 What Happened

A kubeadm upgrade is two jobs that happen in two different places: kubeadm upgrades the **cluster's** components, and the package manager upgrades the **machine's** programs.

1. **The package repository.** pkgs.k8s.io has one repository per minor release. Until `/etc/apt/sources.list.d/kubernetes.list` pointed at `v1.37`, apt could not see any 1.37 package. That is only needed for a minor upgrade; a patch upgrade stays inside the same repository.
2. **kubeadm first.** The new kubeadm knows how to upgrade the cluster to its own version. `kubeadm upgrade plan` shows what it would change; `kubeadm upgrade apply v1.37.1` replaced the API server, controller manager, scheduler and etcd static pod manifests, and updated kube-proxy and CoreDNS. The kubelet on the control plane was still v1.36.5 at this point, which is allowed: the kubelet may be older than the API server, never newer.
3. **Drain, kubelet, restart, uncordon.** The kubelet is a program on the machine, so it is upgraded with apt, then restarted. The documentation: "If you are performing a **minor** version upgrade for any kubelet, you **must** first drain the node (or nodes) that you are upgrading", and it adds that all containers are restarted after an upgrade.
4. **The worker.** The same, with one difference: `kubeadm upgrade node` instead of `apply`. A worker has no control-plane components to upgrade; it only needs its kubelet configuration brought up to date. The drain runs from the control plane, because that is where kubectl works.

While the worker was drained the `orders` pods waited in `Pending`: the control-plane node carries its `NoSchedule` taint, so a two-node cluster has nowhere else to put them. They started when you uncordoned. In a real cluster that is the reason to upgrade workers one at a time, with spare capacity.

## 🔧 The Fix

```bash
# both machines
sudo sed -i 's|stable:/v1.36/|stable:/v1.37/|' /etc/apt/sources.list.d/kubernetes.list

# k8squest-cp
sudo apt-mark unhold kubeadm && sudo apt-get update && sudo apt-get install -y kubeadm='1.37.1-*' && sudo apt-mark hold kubeadm
sudo kubeadm upgrade plan
sudo kubeadm upgrade apply v1.37.1
kubectl drain lima-k8squest-cp --ignore-daemonsets
sudo apt-mark unhold kubelet kubectl && sudo apt-get install -y kubelet='1.37.1-*' kubectl='1.37.1-*' && sudo apt-mark hold kubelet kubectl
sudo systemctl daemon-reload && sudo systemctl restart kubelet
kubectl uncordon lima-k8squest-cp

# k8squest-worker
sudo apt-mark unhold kubeadm kubectl && sudo apt-get update && sudo apt-get install -y kubeadm='1.37.1-*' kubectl='1.37.1-*' && sudo apt-mark hold kubeadm kubectl
sudo kubeadm upgrade node
# k8squest-cp:      kubectl drain lima-k8squest-worker --ignore-daemonsets
sudo apt-mark unhold kubelet && sudo apt-get install -y kubelet='1.37.1-*' && sudo apt-mark hold kubelet
sudo systemctl daemon-reload && sudo systemctl restart kubelet
# k8squest-cp:      kubectl uncordon lima-k8squest-worker
```

## 🎯 Key Takeaways

1. Upgrade one minor version at a time, control plane before workers. The kubelet must never be newer than the API server.
2. The packages are held (`apt-mark hold`) on purpose, so a routine `apt upgrade` cannot move a cluster component by surprise. You unhold, upgrade and hold again.
3. `kubeadm upgrade apply` is for the first control-plane node; `kubeadm upgrade node` is for every other node, workers included.
4. The kubeadm documentation says to upgrade your CNI provider separately if it needs it; Flannel runs as a DaemonSet, so it is not touched by `kubeadm upgrade`.
5. `kubeadm upgrade` also renews the certificates it manages on the node, and writes backups of the etcd data and the manifests under `/etc/kubernetes/tmp`.
6. In this lab, right after the control-plane static pods restart (the kubelet upgrade does that), the API server answered "forbidden" to the admin credentials for a few seconds before it served normally again. Wait and retry before concluding something is wrong.

## 📚 Official Docs

- [Upgrading kubeadm clusters](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/)
- [Changing the Kubernetes package repository](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/change-package-repository/)
- [Upgrade Linux nodes](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/upgrading-linux-nodes/)
- [Version skew policy](https://kubernetes.io/releases/version-skew-policy/)
- [Safely drain a node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)

## 🚀 Next

**Level 75:** the cluster runs, and nobody has a backup of its data. Take one, lose something, and get it back.
