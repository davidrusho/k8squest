Paste this from the docs into nano, then trim:
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 500Mi
With a WaitForFirstConsumer class the PVC stays Pending until a pod uses it.
