#!/usr/bin/env python3
"""
Utility script to hash passwords for admin.json
Usage: python3 hash_password.py
"""

import hashlib
import json

def hash_password(password):
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def main():
    print("Password Hasher for admin.json")
    print("=" * 40)
    
    username = input("Enter username: ").strip()
    password = input("Enter password: ").strip()
    
    if not username or not password:
        print("Error: Username and password cannot be empty")
        return
    
    hashed_password = hash_password(password)
    
    admin_data = {
        "username": username,
        "password": hashed_password
    }
    
    print("\nGenerated admin.json content:")
    print(json.dumps(admin_data, indent=2))
    
    save = input("\nSave to admin.json? (y/n): ").strip().lower()
    if save == 'y':
        with open('admin.json', 'w') as f:
            json.dump(admin_data, f, indent=2)
        print("Saved to admin.json")
    else:
        print("Not saved. Copy the JSON above manually.")

if __name__ == "__main__":
    main()