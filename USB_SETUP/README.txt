================================================================================
                    FILTOUR KIOSK - USB INSTALL GUIDE
================================================================================

WHAT'S ON THIS USB:
-------------------
The ENTIRE kiosk project is on this USB. Everything you need is here.


USB STRUCTURE:
--------------
  USB Drive\
    tour kiosk project\        <-- The complete kiosk
      app.py
      templates\
      static\
        tour_images\           <-- All tour images included
        b_roll\                <-- Background video included
        audio\                 <-- Welcome audio included
      USB_SETUP\               <-- Setup scripts
        install_kiosk.bat      <-- Step 1
        FIRST_TIME_SETUP.bat   <-- Step 2
        README.txt             <-- This file
        python-3.12.x.exe      <-- Python installer (optional)
        Git-2.x.x.exe          <-- Git installer (optional)


================================================================================
                         INSTALLATION STEPS
================================================================================

STEP 1: Install Python (if not already installed)
-------------------------------------------------
   Double-click: python-3.12.x-amd64.exe
   
   IMPORTANT - Check these boxes:
   [X] Add Python to PATH
   [X] Install for all users
   
   Click "Install Now"


STEP 2: Install the Kiosk
-------------------------
   Double-click: install_kiosk.bat
   
   Click "Yes" when Windows asks for permission.
   
   This copies everything from USB to C:\filtour
   and installs all required packages.
   
   When asked "Start kiosk now?" - type: y


STEP 3: Create Your Account
---------------------------
   With the kiosk running, open a web browser:
   
   http://localhost:5000/admin/register
   
   Fill in:
   - Username (e.g., "myshopname")
   - Email
   - Password
   
   Click "Create Account"


STEP 4: Link Device to Account
------------------------------
   Close the kiosk (Ctrl+C in the black window)
   
   Double-click: FIRST_TIME_SETUP.bat
   
   Enter your username when asked.
   
   Choose whether to auto-start on boot.


STEP 5: Configure Your Tours
----------------------------
   Start the kiosk and go to:
   
   http://localhost:5000/admin/login
   
   - Enable the tours you want to sell
   - Add booking links to each tour


================================================================================
                         AUTO-UPDATES
================================================================================

If Git is installed, the kiosk will automatically check for updates!

When updates are pushed from the main computer, this kiosk will:
1. Detect the update
2. Pull the changes
3. Restart automatically

To install Git (for auto-updates):
   Double-click: Git-2.x.x-64-bit.exe
   Use default settings


================================================================================
                         DAILY USE
================================================================================

Start the kiosk:
   Double-click: C:\filtour\start_kiosk.bat

Stop the kiosk:
   Press Ctrl+C in the black window

Admin dashboard:
   http://localhost:5000/admin/login


================================================================================
                         TROUBLESHOOTING
================================================================================

"Python not found"
   - Reinstall Python with "Add to PATH" checked

"Tours not showing"  
   - Run FIRST_TIME_SETUP.bat
   - Make sure you entered the correct username

"No background video"
   - The video should already be copied
   - Check C:\filtour\static\b_roll\ has 0124.mp4

"App crashes on start"
   - Open Command Prompt
   - cd C:\filtour
   - python app.py
   - Look at the error message


================================================================================
