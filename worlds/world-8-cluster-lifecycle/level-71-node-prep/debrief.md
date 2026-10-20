# 🎓 LEVEL 71 DEBRIEF: Nodes That Are Not Ready for Kubernetes

**Congratulations!** You took a plain Ubuntu machine with the Kubernetes packages on it and made it a machine `kubeadm init` can use, and every change survives a reboot.

---

## 📊 What Happened

`k8squest-cp` had kubeadm, kubelet, kubectl and the containerd package, but nobody had prepared it. Four things were missing, and kubeadm only noticed some of them:

- **Swap was on.** By default the kubelet refuses to start when it finds swap. `swapoff -a` turns swap off until the next boot; the line in `/etc/fstab` turns it back on, so that has to go too. (kubeadm 1.37 only prints a warning for swap on cgroup v2; the kubelet is what fails.)
- **IPv4 forwarding was off.** `net.ipv4.ip_forward` was `0`, and kubeadm stops at this one with `[ERROR FileContent--proc-sys-net-ipv4-ip_forward]`.
- **`br_netfilter` was not loaded, and nothing loaded it at boot.** kubeadm does not check for it any more, so `kubeadm init` would have passed. The pod network you install in level 72, Flannel, needs it, and would have failed to start on a cluster that otherwise looked healthy. `overlay` is the module containerd's default snapshotter uses; containerd loads it itself, but a file in `/etc/modules-load.d/` makes the intent explicit.
- **containerd had no configuration.** The package ships without `/etc/containerd/config.toml`, so containerd ran on built-in defaults, with `SystemdCgroup = false`. The Kubernetes documentation recommends the `systemd` cgroup driver when the machine uses cgroup v2.

## 🔧 The Fix

```bash
limactl shell k8squest-cp

sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

printf 'overlay\nbr_netfilter\n' | sudo tee /etc/modules-load.d/k8s.conf
sudo modprobe overlay
sudo modprobe br_netfilter

echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/k8s.conf
sudo sysctl --system

sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd

sudo kubeadm init phase preflight        # no [ERROR ...] lines
```

## 🎯 Key Takeaways

1. A temporary fix and a persistent one are different things. `swapoff`, `modprobe` and `sysctl -w` change the running kernel; `/etc/fstab`, `/etc/modules-load.d/` and `/etc/sysctl.d/` are what a reboot reads.
2. kubeadm's pre-flight checks are a floor, not a checklist. The Flannel project says it directly: it "requires the br_netfilter module to start and from version 1.30 kubeadm doesn't check if the module is installed".
3. `kubeadm init phase preflight` runs only the checks, so you can see what kubeadm thinks of a node before you commit to `init`.
4. A containerd package can come with the CRI plugin disabled or with no configuration at all. `containerd config default` writes the full default configuration, and the cgroup driver setting lives under the `runc` runtime options.
5. With containerd 2.x the kubelet asks the runtime which cgroup driver it uses, so a mismatch is less likely to bite than it once was. The documentation notes that containerd 1.x does not answer that question and that "in Kubernetes 1.38, this fallback behavior will be dropped". Set the driver explicitly anyway.

## 📚 Official Docs

- [Installing kubeadm: swap configuration](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/#swap-configuration)
- [Container runtimes: IPv4 forwarding and the systemd cgroup driver for containerd](https://kubernetes.io/docs/setup/production-environment/container-runtimes/)
- [Flannel README: the br_netfilter requirement](https://github.com/flannel-io/flannel#deploying-flannel-manually)
- [containerd: customizing the configuration](https://github.com/containerd/containerd/blob/main/docs/getting-started.md#customizing-containerd)

## 🚀 Next

**Level 72:** both machines are ready. Turn one of them into a control plane, and find out why a brand-new node is NotReady.
