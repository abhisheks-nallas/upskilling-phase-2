#!/bin/bash
# Runs on the box after k3s + Fission are installed. Deploys the welcome function with an HTTP trigger. Safe to re-run.
set -e
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
VERSION=v1.27.0

if ! command -v fission >/dev/null; then
  curl -sSL -o fission "https://github.com/fission/fission/releases/download/$VERSION/fission-$VERSION-linux-amd64"
  chmod +x fission && sudo mv fission /usr/local/bin/
fi

# buildermgr crash-looped before the CRDs existed; restart it so it stops backing off
kubectl delete pod -n fission -l svc=buildermgr --ignore-not-found >/dev/null

# the secret comes from the same Parameter Store sync that runs at every boot
sudo /usr/local/bin/buddy-sync-secrets k8s

fission env get --name python >/dev/null 2>&1 || fission env create --name python --image ghcr.io/fission/python-env --poolsize 1
fission httptrigger delete --name welcome >/dev/null 2>&1 || true
fission fn delete --name welcome >/dev/null 2>&1 || true
fission fn create --name welcome --env python --code welcome.py --secret app-env
fission httptrigger create --name welcome --url /welcome --method POST --function welcome
echo "Fission function ready: POST http://<box>:31314/welcome"
