#!/bin/bash
# Runs on the box. Installs a small boot-time sync that keeps the box's secrets in step with Parameter Store.
#   sync-env.service      fetches the .env file before Docker starts (the API container mounts it)
#   sync-k8s.service      rebuilds the Kubernetes secret the Fission function reads, once k3s is up
# Safe to re-run.
set -e

sudo tee /usr/local/bin/buddy-sync-secrets >/dev/null <<'SCRIPT'
#!/bin/bash
set -e
PARAM=/upskilling-p2/onboarding-buddy/env
REGION=ap-southeast-2
APP=/home/ec2-user/app
case "$1" in
  env)
    mkdir -p $APP
    for i in 1 2 3 4 5 6; do
      aws ssm get-parameter --region $REGION --name $PARAM --with-decryption --query Parameter.Value --output text > $APP/.env.new && [ -s $APP/.env.new ] && break
      sleep 5
    done
    [ -s $APP/.env.new ] || { echo "could not fetch $PARAM, keeping the old .env"; exit 1; }
    chmod 600 $APP/.env.new && mv -f $APP/.env.new $APP/.env
    echo "wrote $APP/.env from Parameter Store"
    ;;
  k8s)
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    for i in $(seq 1 60); do kubectl get nodes 2>/dev/null | grep -q ' Ready' && break; sleep 4; done
    TMP=$(mktemp)
    # the function only gets the three values it needs, not the whole .env
    tr -d '\r' < $APP/.env | grep -E '^(API_KEY|GROQ_API_KEY|GROQ_FREE_MODEL)=' > $TMP
    kubectl create secret generic app-env --from-env-file=$TMP --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    rm -f $TMP
    echo "updated Kubernetes secret app-env"
    ;;
  *) echo "usage: buddy-sync-secrets env|k8s"; exit 2 ;;
esac
SCRIPT
sudo chmod 755 /usr/local/bin/buddy-sync-secrets

sudo tee /etc/systemd/system/sync-env.service >/dev/null <<'UNIT'
[Unit]
Description=Fetch Onboarding Buddy .env from Parameter Store
After=network-online.target
Wants=network-online.target
Before=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/buddy-sync-secrets env

[Install]
WantedBy=multi-user.target
UNIT

sudo tee /etc/systemd/system/sync-k8s.service >/dev/null <<'UNIT'
[Unit]
Description=Update the Fission function secret from the .env file
After=k3s.service sync-env.service
Wants=sync-env.service

[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=400
ExecStart=/usr/local/bin/buddy-sync-secrets k8s

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable sync-env.service sync-k8s.service >/dev/null 2>&1
sudo /usr/local/bin/buddy-sync-secrets env
