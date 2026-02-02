#!/usr/bin/env python3
"""
Filtour Kiosk Setup Script
==========================
Run this ONCE when setting up a new shop's kiosk to link it to their account.

Usage:
    python scripts/setup_kiosk.py airliebeachtourism
    
This creates/updates config/instance.json with the account name.
"""

import os
import sys
import json
from datetime import datetime

def setup_kiosk(account_name):
    """Link this kiosk instance to a specific account"""
    
    config_dir = 'config'
    instance_file = os.path.join(config_dir, 'instance.json')
    
    # Ensure config directory exists
    os.makedirs(config_dir, exist_ok=True)
    
    # Load existing config or create new
    if os.path.exists(instance_file):
        with open(instance_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"Existing config found. Previous account: {config.get('active_account', 'none')}")
    else:
        config = {}
        print("Creating new instance config...")
    
    # Update the active account
    config['active_account'] = account_name
    config['setup_date'] = datetime.now().isoformat()
    config['setup_note'] = f'This kiosk is linked to the {account_name} account'
    
    # Save the config
    with open(instance_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n[OK] Kiosk linked to account: {account_name}")
    print(f"     Config saved to: {instance_file}")
    print(f"\nNext steps:")
    print(f"   1. Make sure the account '{account_name}' exists (register at /admin/register)")
    print(f"   2. Complete onboarding to select which tours to show")
    print(f"   3. Upload your logo in Kiosk Settings")
    print(f"   4. Commit this config to your repo:")
    print(f"      git add config/instance.json")
    print(f"      git commit -m 'Link kiosk to {account_name}'")
    print(f"   5. Push to your shop's repo: git push")

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_kiosk.py <account_name>")
        print("\nExample: python scripts/setup_kiosk.py airliebeachtourism")
        print("\nThis links this kiosk to a specific account so it shows")
        print("only that account's tours, logo, and settings.")
        sys.exit(1)
    
    account_name = sys.argv[1].strip().lower()
    
    if not account_name:
        print("Error: Account name cannot be empty")
        sys.exit(1)
    
    setup_kiosk(account_name)

if __name__ == '__main__':
    main()

