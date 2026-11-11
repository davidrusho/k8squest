In nano: under the container (same indent as image:/name:) add
    volumeMounts:
    - name: creds
      mountPath: /etc/creds
Then at the spec level (same indent as containers:) add
  volumes:
  - name: creds
    secret:
      secretName: db-creds
