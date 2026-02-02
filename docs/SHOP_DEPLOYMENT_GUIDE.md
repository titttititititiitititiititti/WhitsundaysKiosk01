# Filtour Shop Deployment Guide

This guide explains how to set up Filtour on a shop's kiosk computer with automatic updates from GitHub.

## Overview

Each shop gets their own:
1. **GitHub Repository** - A copy of the main Filtour repo that you can push updates to
2. **Kiosk Computer** - Runs the Flask app and auto-updates from the repo
3. **Account Config** - Shop-specific settings (logo, tours, promotions)

## Part 1: Create the Shop's GitHub Repository

### Option A: Fork Method (Easiest)
1. Create a new GitHub account for the shop (or use yours)
2. Fork the main Filtour repository
3. Make it private if needed (GitHub settings)

### Option B: Template/Copy Method
```bash
# On your development machine
git clone https://github.com/your-username/filtour.git filtour-shopname
cd filtour-shopname

# Remove the old origin and add the new repo
git remote remove origin
git remote add origin https://github.com/your-username/filtour-shopname.git

# Push to the new repo
git push -u origin main
```

## Part 2: Set Up the Shop's Computer

### Requirements
- Windows 10/11 (or Linux/macOS)
- Python 3.9 or higher
- Git
- Internet connection

### Step 1: Install Python
1. Download Python from https://www.python.org/downloads/
2. During installation, **CHECK "Add Python to PATH"**
3. Open Command Prompt and verify: `python --version`

### Step 2: Install Git
1. Download Git from https://git-scm.com/downloads
2. Install with default options
3. Verify: `git --version`

### Step 3: Clone the Repository
```bash
# Open Command Prompt or PowerShell
cd C:\
git clone https://github.com/your-username/filtour-shopname.git filtour
cd filtour
```

### Step 4: Set Up Git Credentials
For automatic pulls, set up credential storage:
```bash
git config --global credential.helper store

# The first time you pull, enter your GitHub credentials
# They'll be saved for future pulls
git pull
```

**For GitHub with 2FA enabled:**
1. Go to GitHub → Settings → Developer Settings → Personal Access Tokens
2. Generate a new token with `repo` scope
3. Use the token as your password when prompted

### Step 5: Install Dependencies
```bash
cd C:\filtour
python -m pip install -r requirements.txt
```

### Step 6: Configure the Kiosk
Create `config/instance.json`:
```json
{
  "shop_name": "Airlie Beach Tourism",
  "custom_logo": "/static/logos/shopname/logo.png",
  "default_language": "en"
}
```

### Step 7: Test the App
```bash
python app.py
```
Visit `http://localhost:5000` - it should work!

## Part 3: Set Up Auto-Start and Auto-Update

### Windows Task Scheduler (Recommended)

1. **Open Task Scheduler**
   - Press Win+R, type `taskschd.msc`, press Enter

2. **Create Basic Task**
   - Name: "Filtour Kiosk"
   - Trigger: "When the computer starts"
   - Action: "Start a program"
   - Program: `C:\filtour\scripts\start_kiosk.bat`
   - Start in: `C:\filtour`

3. **Configure Settings**
   - Check "Run with highest privileges"
   - Configure for: "Windows 10"

### Alternative: Windows Startup Folder
1. Press Win+R, type `shell:startup`, press Enter
2. Create a shortcut to `C:\filtour\scripts\start_kiosk.bat`

## Part 4: Pushing Updates to the Shop

### From Your Development Machine
```bash
# Make changes to the code
git add .
git commit -m "Updated feature X"

# Push to the shop's repository
git push origin main
```

### What Happens Automatically
1. The shop's kiosk checks for updates every 5 minutes
2. If updates are found, it pulls them automatically
3. The Flask app restarts with the new code
4. No manual intervention needed!

## Part 5: Shop-Specific Configuration

### Setting Up the Shop's Account

1. **Create Shop Account**
   - Go to `http://localhost:5000/admin/register`
   - Create account with shop's email

2. **Complete Onboarding**
   - Select which tours the shop sells
   - Tours they don't select go to "Unavailable Tours"

3. **Upload Shop Logo**
   - Go to Kiosk Settings
   - Upload the shop's logo (PNG or SVG recommended)
   - The logo replaces Filtour branding throughout

4. **Configure Tours**
   - Add booking links for each tour
   - Set promotions (Popular, Featured, Best Value)
   - Add Hero/Rezdy widgets if applicable

### Important Files Per Shop

```
config/
├── instance.json          # Kiosk-specific settings (logo, etc.)
├── users.json             # User accounts
└── accounts/
    └── shopusername/
        └── settings.json  # Shop's tours, promotions, settings
```

## Part 6: Multiple Shops from One Development Machine

### Repository Structure
```
GitHub Repositories:
├── filtour-main           # Your development/master copy
├── filtour-airlie-tourism # Shop 1's repo
├── filtour-reef-tours     # Shop 2's repo
└── filtour-island-travel  # Shop 3's repo
```

### Pushing Updates to All Shops
```bash
# In your main development folder
cd filtour-main

# Add all shop remotes
git remote add airlie https://github.com/you/filtour-airlie-tourism.git
git remote add reef https://github.com/you/filtour-reef-tours.git
git remote add island https://github.com/you/filtour-island-travel.git

# Push to all shops at once
git push airlie main
git push reef main
git push island main

# Or push to all at once with a script
```

### Push to All Script (`push_all.bat`)
```batch
@echo off
echo Pushing to all shop repositories...
git push airlie main
git push reef main
git push island main
echo Done!
```

## Troubleshooting

### Kiosk Won't Start
```bash
# Check Python
python --version

# Check dependencies
python -m pip install -r requirements.txt

# Run manually to see errors
python app.py
```

### Updates Not Pulling
```bash
# Check Git status
cd C:\filtour
git status
git fetch
git log --oneline -5

# Manual pull
git pull origin main
```

### Logo Not Showing
1. Check the file exists in `static/logos/`
2. Check `config/instance.json` has the correct path
3. Clear browser cache

### Port Already in Use
```bash
# Find what's using port 5000
netstat -ano | findstr :5000

# Kill the process
taskkill /PID <pid> /F
```

## Security Notes

1. **Don't commit sensitive data** - Use `.gitignore` for API keys
2. **Use HTTPS** for production deployments
3. **Keep Python and dependencies updated**
4. **Use strong passwords** for admin accounts

## Support

For issues, contact the Filtour development team or check the main repository's issues page.

