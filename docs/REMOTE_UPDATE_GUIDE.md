# Remote Update System Guide

## Overview
The Tour Kiosk app includes a built-in remote update system that allows you to push code changes from GitHub to any installed kiosk.

## How It Works

1. **Development**: Make changes on your development machine
2. **Push to GitHub**: `git push origin main`
3. **Update Kiosks**: Login to each kiosk's Agent Dashboard and click "Check for Updates"

## Key Files

### Backend (`app.py`)
Location: Lines ~910-1010

```python
# Key routes:
/health                          # Health check endpoint
/admin/agent/api/check-updates   # Checks GitHub for new commits
/admin/agent/api/apply-update    # Pulls changes and restarts app
```

### Frontend (`templates/agent_dashboard.html`)
Location: Sidebar "System" section + JavaScript functions at bottom

- `checkForUpdates()` - Fetches update status from backend
- `applyUpdate()` - Triggers git pull and restart
- `checkServerRestart()` - Polls until server is back online

### Version Tracking (`app.py`)
```python
APP_VERSION = "1.0.0"  # Update this when releasing new versions
```

## Kiosk Installation Steps

### 1. Initial Setup
```bash
# Clone the repository
git clone https://github.com/YOUR-USERNAME/tour-kiosk.git
cd tour-kiosk

# Install dependencies
pip install -r requirements.txt

# Create local config (optional - for agent settings)
mkdir config
```

### 2. Configure Git (One-time)
```bash
# Set up git credentials so pulls don't require password
git config --global credential.helper store

# Do one manual pull to cache credentials
git pull origin main
# Enter username and Personal Access Token when prompted
```

### 3. Run the App
```bash
python app.py
```

### 4. Future Updates
1. Go to `http://localhost:5000/admin/agent`
2. Login with agent credentials
3. Click "🔄 Check for Updates" in the sidebar
4. If updates available, click "Update" to apply

## Auto-Update on Startup (Optional)

To automatically update when the kiosk boots, create a startup script:

### Windows (`start_kiosk.bat`)
```batch
@echo off
cd /d "C:\path\to\tour-kiosk"
git pull origin main
python app.py
```

### Linux/Mac (`start_kiosk.sh`)
```bash
#!/bin/bash
cd /path/to/tour-kiosk
git pull origin main
python app.py
```

Then add this script to your system's startup programs.

## Troubleshooting

### "Authentication failed"
- Create a Personal Access Token on GitHub
- Use it as password when git prompts
- It will be cached for future pulls

### "Merge conflicts"
- Local changes will prevent updates
- SSH into kiosk and run: `git reset --hard origin/main`

### "Server not restarting"
- Check if another Python process is running
- Manually restart: `taskkill /F /IM python.exe` then `python app.py`

## Security Notes

- The update system only works from the Agent Dashboard (requires login)
- Updates only pull from the configured remote (origin)
- No arbitrary code execution - only git pull

## Version History

- 1.0.0 - Initial production release with remote update system

