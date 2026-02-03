================================================================================
                    FILTOUR KIOSK USB SETUP GUIDE
================================================================================

This USB contains everything needed to install the Filtour Kiosk on a new computer.


USB FOLDER STRUCTURE:
---------------------

  USB_SETUP/
  |
  |-- install_kiosk.bat        (Step 1: Install the kiosk)
  |-- FIRST_TIME_SETUP.bat     (Step 2: Copy files & link account)  
  |-- README.txt               (This file)
  |
  |-- python-3.12.x-amd64.exe  (Python installer - download from python.org)
  |-- Git-2.x.x-64-bit.exe     (Git installer - download from git-scm.com)
  |
  |-- tour_images/             (Copy from your main computer's static/tour_images/)
  |   |-- company1/
  |   |-- company2/
  |   |-- ...
  |
  |-- b_roll/                  (Copy from your main computer's static/b_roll/)
  |   |-- 0124.mp4             (Background video)
  |
  |-- logos/                   (Optional - custom logos)


STEP-BY-STEP INSTALLATION:
==========================

STEP 1: Install Prerequisites
-----------------------------
   a. Double-click: python-3.12.x-amd64.exe
      [X] Check "Add Python to PATH"
      [X] Check "Install for all users"
      Click "Install Now"
   
   b. Double-click: Git-2.x.x-64-bit.exe
      Use all default settings
      Click "Install"


STEP 2: Install the Kiosk
-------------------------
   a. Double-click: install_kiosk.bat
   b. Click "Yes" when Windows asks for admin permission
   c. Wait for installation (5-10 minutes)
   d. When asked "Start kiosk now?" type: n (we need to set up account first)


STEP 3: Create Account
----------------------
   a. Open Command Prompt
   b. Type: cd C:\filtour
   c. Type: python app.py
   d. Open browser: http://localhost:5000/admin/register
   e. Create your account (remember the username!)
   f. Press Ctrl+C in Command Prompt to stop the server


STEP 4: First Time Setup (IMPORTANT!)
-------------------------------------
   a. Double-click: FIRST_TIME_SETUP.bat
   b. This will:
      - Copy all tour images from USB to kiosk
      - Copy background video from USB to kiosk
      - Link this device to your account
      - Set up automatic updates
      - Optionally set up auto-start on boot


STEP 5: Configure Your Tours
----------------------------
   a. Start kiosk (double-click C:\filtour\start_kiosk.bat)
   b. Go to: http://localhost:5000/admin/login
   c. Log in with your account
   d. Enable the tours you want to sell
   e. Add booking links to each tour


================================================================================
                         AUTO-UPDATE FEATURE
================================================================================

The kiosk automatically checks for updates every 5 minutes!

When you push changes from your main computer:
   git add -A
   git commit -m "Updated tours"
   git push shop main

The shop's kiosk will:
   1. Detect the new update
   2. Pull the changes
   3. Restart automatically

No manual intervention needed!


================================================================================
                         TROUBLESHOOTING
================================================================================

PROBLEM: "Python not found"
SOLUTION: Reinstall Python, make sure to check "Add Python to PATH"

PROBLEM: "Git not found"  
SOLUTION: Reinstall Git with default settings

PROBLEM: Tours not showing
SOLUTION: Run FIRST_TIME_SETUP.bat to link your account

PROBLEM: No background video
SOLUTION: Make sure b_roll/0124.mp4 is on the USB before running setup

PROBLEM: Images not showing
SOLUTION: Make sure tour_images folder is on USB before running setup


================================================================================
                         MANUAL COMMANDS
================================================================================

Start kiosk:
   Double-click: C:\filtour\start_kiosk.bat

Stop kiosk:
   Press Ctrl+C in the kiosk window

Manual update:
   cd C:\filtour
   git pull origin main

Check status:
   cd C:\filtour
   git status


================================================================================
