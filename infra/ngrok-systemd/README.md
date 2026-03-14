# Stable ngrok Setup (Hobbyist Plan)

Fixed ngrok-branded domain setup for CDP_Merged Operator Shell with automatic recovery.

## What This Gives You

- **Fixed public URL**: `https://kbocdpagent.ngrok.app` (never changes)
- **Operator Shell**: Next.js app on port 3000
- **Auto-restart**: Services restart after crashes, logout, or reboot
- **Health monitoring**: Checks operator shell and public tunnel every minute
- **Self-healing**: Restarts services when unhealthy
- **Zero extra cost**: Uses ngrok Hobbyist plan features

## Prerequisites

- ngrok Hobbyist plan active (~$5/month)
- Reserved domain: `kbocdpagent.ngrok.app` in your ngrok dashboard
- Node.js installed for operator shell

## Quick Start

### 1. Reserve Your Fixed Domain (One-time)

In ngrok dashboard: https://dashboard.ngrok.com/domains

1. Click **"New Domain"**
2. Enter: `kbocdpagent.ngrok.app`
3. Click **"Reserve"**

### 2. Install & Run

```bash
cd /var/home/ff/Documents/CDP_Merged/infra/ngrok-systemd
./install.sh

# Start everything
systemctl --user daemon-reload
systemctl --user start cdp-operator-shell.service
systemctl --user start ngrok-cdp.service
systemctl --user start ngrok-cdp-watchdog.timer
```

### 3. Verify

```bash
./status.sh

# Test the public URL
curl https://kbocdpagent.ngrok.app
```

## Files

| File | Purpose |
|------|---------|
| `ngrok.yml` | ngrok config with fixed domain |
| `cdp-operator-shell.service` | systemd service for Next.js operator shell |
| `ngrok-cdp.service` | systemd service for ngrok tunnel |
| `ngrok-cdp-watchdog.service` | systemd service for health checks |
| `ngrok-cdp-watchdog.timer` | Runs watchdog every minute |
| `check-ngrok-cdp.sh` | Health check script |
| `install.sh` | Automated installer |
| `status.sh` | Quick status checker |

## Service Commands

```bash
# Check status
systemctl --user status ngrok-cdp.service
systemctl --user status cdp-operator-shell.service

# View logs
journalctl --user -u ngrok-cdp.service -f
journalctl --user -u cdp-operator-shell.service -f

# Restart services
systemctl --user restart ngrok-cdp.service
systemctl --user restart cdp-operator-shell.service

# Stop everything
systemctl --user stop ngrok-cdp.service cdp-operator-shell.service ngrok-cdp-watchdog.timer
```

## Troubleshooting

### "Domain not reserved" error
Reserve `kbocdpagent.ngrok.app` at https://dashboard.ngrok.com/domains

### "connection refused" on port 3000
Make sure operator shell dependencies are installed:
```bash
cd /var/home/ff/Documents/CDP_Merged/apps/operator-shell
npm install
```

### Services won't start
```bash
systemctl --user daemon-reload
journalctl --user -xe
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Public Internet                          │
│                   https://kbocdpagent.ngrok.app                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                          ngrok Cloud                             │
│              (reserved domain: kbocdpagent.ngrok.app)           │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Your Machine                             │
│  ┌─────────────────┐         ┌─────────────────────────────────┐│
│  │ ngrok-cdp       │────────▶│ http://127.0.0.1:3000           ││
│  │ (systemd)       │  tunnel │                                  ││
│  └─────────────────┘         │  ┌───────────────────────────┐   ││
│                              │  │ cdp-operator-shell        │   ││
│  ┌─────────────────┐         │  │ (Next.js npm run dev)     │   ││
│  │ ngrok-cdp-      │◀────────┘  └───────────────────────────┘   ││
│  │ watchdog.timer  │  health checks (every minute)              ││
│  │ (systemd)       │                                          ││
│  └─────────────────┘                                          ││
└─────────────────────────────────────────────────────────────────┘
```

## Cost

- **ngrok Hobbyist**: ~$5/month
- **No additional costs**: Uses ngrok-branded domain

## Verification Checklist

- [ ] ngrok Hobbyist plan active
- [ ] Domain `kbocdpagent.ngrok.app` reserved in dashboard
- [ ] `~/.config/ngrok/ngrok.yml` has your authtoken
- [ ] `systemctl --user status ngrok-cdp.service` shows "active (running)"
- [ ] `curl https://kbocdpagent.ngrok.app` returns 200
- [ ] After `systemctl --user restart ngrok-cdp.service`, URL stays the same
