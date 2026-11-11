Generate with $do first, then in nano add the block directly under the top-level `spec:` line (same indent as `containers:`, two spaces).
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 1
        preference:
          matchExpressions:
          - key: disk
            operator: In
            values:
            - ssd
