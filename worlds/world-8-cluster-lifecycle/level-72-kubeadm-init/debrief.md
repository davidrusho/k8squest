# 🎓 LEVEL 72 DEBRIEF: Bootstrap a Control Plane

**Congratulations!** You created a Kubernetes control plane with `kubeadm init`, and gave it the pod network it needs to be useful.

---

## 📊 What Happened

`kubeadm init` ran its pre-flight checks, generated the cluster's certificates and kubeconfig files, wrote the static pod manifests for the API server, controller manager, scheduler and etcd into `/etc/kubernetes/manifests`, and let the kubelet start them. That part needs no pod network: static pods use the node's own network.

Then you looked at `kubectl get nodes` and saw `NotReady`, and at `kubectl get pods -A` and saw CoreDNS `Pending`. Nothing was broken. kubeadm deliberately does not install a pod network: it is "CNI agnostic". Until a CNI add-on writes a configuration into `/etc/cni/net.d`, the kubelet reports the node's network as not ready and CoreDNS cannot be given a pod IP. Applying the Flannel manifest fixed both.

The one thing you had to know before `init` was `--pod-network-cidr=10.244.0.0/16`. Flannel allocates a slice of that range to each node, which only works if the controller manager assigned the node a `podCIDR`, and it only does that when the cluster was initialised with a pod CIDR.

## 🔧 The Fix

```bash
sudo kubeadm init --pod-network-cidr=10.244.0.0/16
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

kubectl get nodes                      # NotReady
kubectl apply -f https://github.com/flannel-io/flannel/releases/download/v0.28.9/kube-flannel.yml
kubectl get nodes                      # Ready
kubectl get pods -A                    # coredns Running, kube-flannel Running
```

## 🎯 Key Takeaways

1. The kubeadm documentation: "You must deploy a Container Network Interface (CNI) based Pod network add-on so that your Pods can communicate with each other. Cluster DNS (CoreDNS) will not start up before a network is installed."
2. Read the add-on's requirements before `kubeadm init`. The pod CIDR is an argument to `init` (or a field in its configuration file), and changing it later is not a small edit.
3. `/etc/kubernetes/admin.conf` is the cluster administrator's credential. Copying it to `$HOME/.kube/config` is the documented way to get a working kubectl on the control plane, and it should not be shared.
4. You can install only one pod network per cluster, and its CIDR must not overlap the machines' own networks (these two machines use 192.168.104.0/24).
5. If `kubeadm init` fails half way, `kubeadm reset` is how you start over. The cluster cannot be created on top of the debris.

## 📚 Official Docs

- [Creating a cluster with kubeadm: initializing the control-plane node, installing a Pod network add-on](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/)
- [Flannel: deploying with kubectl and kubeadm](https://github.com/flannel-io/flannel#deploying-flannel-manually)
- [kubeadm init](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-init/)

## 🚀 Next

**Level 73:** the control plane is Ready, but the cluster has one node. Make the worker join it.
