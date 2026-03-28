#!/usr/bin/env bash
# VPS Initial Setup Script — run once as root on a fresh Ubuntu 22.04 VPS
set -euo pipefail

APP_USER="ojik"
APP_DIR="/opt/ojik-bms"
REPO_URL="https://github.com/Speeditidious/OJIK-BMS.git"

echo "=== [1/6] System update ==="
apt-get update -y && apt-get upgrade -y
apt-get install -y curl git ufw fail2ban unattended-upgrades

echo "=== [2/6] Install Docker ==="
curl -fsSL https://get.docker.com | sh
systemctl enable docker

echo "=== [3/6] Create app user ==="
if ! id "$APP_USER" &>/dev/null; then
    adduser --disabled-password --gecos "" "$APP_USER"
    usermod -aG docker "$APP_USER"
fi

# Copy root's authorized_keys to the new user so SSH key login works
if [ -f /root/.ssh/authorized_keys ]; then
    mkdir -p /home/$APP_USER/.ssh
    cp /root/.ssh/authorized_keys /home/$APP_USER/.ssh/
    chown -R $APP_USER:$APP_USER /home/$APP_USER/.ssh
    chmod 700 /home/$APP_USER/.ssh
    chmod 600 /home/$APP_USER/.ssh/authorized_keys
fi

echo "=== [4/6] Clone repository ==="
mkdir -p "$APP_DIR"
git clone "$REPO_URL" "$APP_DIR" || (cd "$APP_DIR" && git pull)
chown -R $APP_USER:$APP_USER "$APP_DIR"

echo "=== [5/6] Install Miniconda & create ojik_bms environment ==="
MINICONDA_PATH="/opt/miniconda3"
if [ ! -d "$MINICONDA_PATH" ]; then
    curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p "$MINICONDA_PATH"
    rm /tmp/miniconda.sh
fi
export PATH="$MINICONDA_PATH/bin:$PATH"
"$MINICONDA_PATH/bin/conda" init bash
"$MINICONDA_PATH/bin/conda" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
"$MINICONDA_PATH/bin/conda" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
"$MINICONDA_PATH/bin/conda" create -n ojik_bms python=3.11 -y
"$MINICONDA_PATH/bin/conda" run -n ojik_bms pip install -r "$APP_DIR/api/requirements.txt"

echo "=== [6/7] Firewall (UFW) ==="
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw --force enable

echo "=== [7/8] fail2ban ==="
systemctl enable fail2ban
systemctl start fail2ban

echo "=== [8/8] SSH hardening — disable password login ==="
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl reload sshd

echo "=== [opt] Unattended security upgrades ==="
dpkg-reconfigure -f noninteractive unattended-upgrades

echo ""
echo "=== VPS setup complete ==="
echo "Next steps:"
echo "  1. Create .env.prod from .env.prod.example and fill in secrets:"
echo "     sudo -u $APP_USER cp $APP_DIR/.env.prod.example $APP_DIR/.env.prod"
echo "     sudo -u $APP_USER nano $APP_DIR/.env.prod"
echo "  2. Place Cloudflare Origin Certificate files:"
echo "     mkdir -p /etc/ssl/cloudflare"
echo "     # paste cert → /etc/ssl/cloudflare/cert.pem"
echo "     # paste key  → /etc/ssl/cloudflare/key.pem"
echo "  3. Start services:"
echo "     cd $APP_DIR && sudo -u $APP_USER docker compose -f docker-compose.prod.yml up -d"
echo "  4. Run DB migrations:"
echo "     docker compose -f docker-compose.prod.yml exec api alembic upgrade head"
