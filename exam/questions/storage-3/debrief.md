In nano: under the container (same indent as image:/name:) add
    volumeMounts:
    - name: data
      mountPath: /data
Then at the spec level (same indent as containers:) add
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: data-pvc
