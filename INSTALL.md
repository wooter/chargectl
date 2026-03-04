# Installing chargectl on a Raspberry Pi

## Prerequisites

- Raspberry Pi running Raspbian/Raspberry Pi OS (64-bit recommended)
- Python 3.11 or later
- USB-to-RS-485 adapter connected (shows up as `/dev/ttyUSB0`)
- Mosquitto MQTT broker running (locally or on network)
- Power measurement data being published to MQTT

## 1. Install Python and pip

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

## 2. Install chargectl

```bash
cd /home/wouter
git clone https://github.com/wooter/chargectl.git
cd chargectl
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

## 3. Configure

```bash
sudo mkdir -p /etc/chargectl
sudo cp config.example.yaml /etc/chargectl/config.yaml
sudo nano /etc/chargectl/config.yaml
```

Edit the config for your setup:

- `mqtt.broker` — IP of your MQTT broker (use `localhost` if running on the same Pi)
- `rs485.port` — usually `/dev/ttyUSB0`, check with `ls /dev/ttyUSB*`
- `grid.max_amps_per_phase` — your main fuse rating (e.g., 20)
- `grid.margin_amps` — safety margin (3 recommended)
- `power_source.topics` — match the MQTT topics your power meter publishes

## 4. Test manually

```bash
source /home/wouter/chargectl/.venv/bin/activate
chargectl --config /etc/chargectl/config.yaml
```

You should see:
- `RS-485 opened on /dev/ttyUSB0 at 9600 baud`
- `MQTT connecting to ...`
- `Discovered TWC slave XXXX` (within ~10 seconds if TWCs are powered on)

Press Ctrl+C to stop. chargectl will set all chargers to 0A before exiting.

## 5. Set up serial port permissions

```bash
sudo usermod -a -G dialout wouter
newgrp dialout
```

## 6. Install as systemd service

```bash
sudo tee /etc/systemd/system/chargectl.service << 'EOF'
[Unit]
Description=chargectl - EV charger controller
After=network.target mosquitto.service

[Service]
Type=simple
User=wouter
ExecStart=/home/wouter/chargectl/.venv/bin/chargectl --config /etc/chargectl/config.yaml
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable chargectl
sudo systemctl start chargectl
```

## 7. Check it's running

```bash
journalctl -u chargectl -f
systemctl status chargectl
```

## 8. TWC hardware setup

1. Set each TWC Gen 2 rotary switch to position **F** (slave mode)
2. Connect RS-485 wiring: D+ to D+, D- to D- between the USB adapter and TWC terminals
3. If you have 2 TWCs, daisy-chain them on the same RS-485 bus

## Migrating from TWCManager

1. Stop TWCManager: `sudo systemctl stop twcmanager && sudo systemctl disable twcmanager`
2. Start chargectl: `sudo systemctl start chargectl`
3. If something goes wrong: `sudo systemctl stop chargectl && sudo systemctl enable twcmanager && sudo systemctl start twcmanager`

TWCManager and chargectl cannot run simultaneously (they'd both try to be the RS-485 master).

## Updating

```bash
cd /home/wouter/chargectl
git pull
source .venv/bin/activate
pip install .
sudo systemctl restart chargectl
```

## Troubleshooting

**No TWC slaves discovered:**
- Check RS-485 wiring (D+/D- not swapped)
- Check TWC rotary switch is on F
- Check serial port: `ls -la /dev/ttyUSB0`
- Run with `logging.level: debug` to see raw RS-485 frames

**Fuse still trips:**
- Increase `grid.margin_amps` (try 4 or 5)
- Check that power measurement topics are correct and data is flowing
- Run with debug logging to see the modulation decisions

**MQTT connection fails:**
- Check broker is running: `systemctl status mosquitto`
- Check broker IP in config
- Test manually: `mosquitto_sub -h localhost -t '#' -v`
