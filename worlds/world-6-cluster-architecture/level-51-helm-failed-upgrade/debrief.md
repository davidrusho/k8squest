# 🎓 LEVEL 51 DEBRIEF: Helm - The Failed Upgrade

**Congratulations!** You recovered a release by working with its revision history.

---

## 📊 What Happened

Revision 2 set `image.tag` to `1.27-alpin`, a tag that does not exist. Helm applied
the manifests and returned (no `--wait`), so the release showed as `deployed` while
the new pods sat in `ImagePullBackOff`. The Deployment's rolling update kept the old
pods running, which is why the app still answered requests.

## 🔧 The Fix

```bash
helm history webapp -n k8squest        # find the last good revision
helm rollback webapp 1 -n k8squest     # creates revision 3 with revision 1's contents
```

or a corrected `helm upgrade ... --reset-values --set image.tag=1.27-alpine` from the working copy of the chart.

## 🎯 Key Takeaways

1. A Helm release is a numbered history of revisions, stored as Secrets in the release namespace.
2. `helm rollback` does not delete the bad revision; it adds a new one.
3. Fix the release, not the object: a `kubectl edit` is overwritten by the next `helm upgrade`.
4. `helm upgrade --rollback-on-failure` rolls the release back to the previous successful revision when an upgrade fails ("if set, Helm will rollback the upgrade to previous success release upon failure").
5. `--reuse-values` keeps the last release's values; `--reset-values` goes back to the chart's defaults.

## 📚 Official Docs

- [helm rollback](https://helm.sh/docs/helm/helm_rollback/)
- [helm history](https://helm.sh/docs/helm/helm_history/)
- [helm upgrade](https://helm.sh/docs/helm/helm_upgrade/)

## 🚀 Next

**Level 52:** Kustomize overlays.
