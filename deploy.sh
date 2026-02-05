#!/bin/bash
# Quiz Machine - Deployment script for mikr.us VPS
# Usage: SSH_HOST=user@host SSH_PORT=port ./deploy.sh

set -e

SSH_HOST="${SSH_HOST:?Set SSH_HOST (e.g. user@host)}"
SSH_PORT="${SSH_PORT:-22}"
APP_DIR="/opt/quiz-machine"
APP_USER="www-data"

echo "=== Deploying Quiz Machine to ${SSH_HOST} ==="

# Install dependencies on server
ssh -p "$SSH_PORT" "$SSH_HOST" << 'REMOTE'
set -e
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx

mkdir -p /opt/quiz-machine
REMOTE

# Copy application files
echo "Copying files..."
rsync -avz --exclude '__pycache__' --exclude '*.db' --exclude '.env' --exclude 'venv' \
    -e "ssh -p $SSH_PORT" \
    ./ "${SSH_HOST}:${APP_DIR}/"

# Set up virtualenv, systemd, and nginx on remote
ssh -p "$SSH_PORT" "$SSH_HOST" << REMOTE
set -e

cd ${APP_DIR}

# Create virtualenv and install deps
python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate a random secret key
    SECRET=\$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/your-secret-key-here/\${SECRET}/" .env
    echo "Created .env — edit TEACHER_PASSWORD before use!"
fi

# Ensure DB directory is writable
chown -R ${APP_USER}:${APP_USER} ${APP_DIR}

# Create systemd service
cat > /etc/systemd/system/quiz-machine.service << 'EOF'
[Unit]
Description=Quiz Machine
After=network.target

[Service]
User=${APP_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 wsgi:app
Restart=always
EnvironmentFile=${APP_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF

# Create nginx config
cat > /etc/nginx/sites-available/quiz-machine << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias ${APP_DIR}/static/;
        expires 1d;
    }
}
EOF

ln -sf /etc/nginx/sites-available/quiz-machine /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl enable quiz-machine
systemctl restart quiz-machine
systemctl restart nginx

echo "=== Deployment complete! ==="
REMOTE
