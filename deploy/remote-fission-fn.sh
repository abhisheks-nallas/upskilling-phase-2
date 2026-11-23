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

# the function only gets the three values it needs, not the whole .env
# tr/sed drop Windows line endings and a byte-order mark, which would otherwise end up inside the key names
tr -d '\r' < app/.env | sed '1s/^\xEF\xBB\xBF//' | grep -E '^(API_KEY|GROQ_API_KEY|GROQ_FREE_MODEL)=' > /tmp/fn.env
kubectl create secret generic app-env --from-env-file=/tmp/fn.env --dry-run=client -o yaml | kubectl apply -f - >/dev/null
rm /tmp/fn.env

fission env get --name python >/dev/null 2>&1 || fission env create --name python --image ghcr.io/fission/python-env --poolsize 1
fission httptrigger delete --name welcome >/dev/null 2>&1 || true
fission fn delete --name welcome >/dev/null 2>&1 || true
fission fn create --name welcome --env python --code welcome.py --secret app-env
fission httptrigger create --name welcome --url /welcome --method POST --function welcome
echo "Fission function ready: POST http://<box>:31314/welcome"
