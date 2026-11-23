#!/bin/bash
# Runs on the box. Adds swap, installs Docker, pulls the API image from ECR and starts it.
set -e
REGION=ap-southeast-2
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
IMAGE="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/upskilling-p2/onboarding-buddy:latest"

if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

sudo dnf install -y -q docker
sudo systemctl enable --now docker
mkdir -p app && mv api.env app/.env && chmod 600 app/.env
aws ecr get-login-password --region $REGION | sudo docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com" >/dev/null
sudo docker pull -q "$IMAGE"
sudo docker rm -f buddy 2>/dev/null || true
sudo docker run -d --restart unless-stopped --name buddy -p 8000:8000 -v /home/ec2-user/app/.env:/app/.env:ro "$IMAGE" >/dev/null
echo "API container started"
