kubectl patch pv pv1 -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
