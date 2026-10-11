#!/bin/bash
cat << 'EOF' | sudo tee /etc/systemd/system/dt_futbol.service
[Unit]
Description=DT Futbol Statistics Telegram Bot
After=network.target

[Service]
Type=simple
User=motoc
WorkingDirectory=/home/motoc/dt_futbol_statistics
ExecStart=/home/motoc/dt_futbol_statistics/venv/bin/python3 /home/motoc/dt_futbol_statistics/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable dt_futbol
sudo systemctl restart dt_futbol
sudo systemctl status dt_futbol --no-pager
