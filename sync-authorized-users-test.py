#!/usr/bin/env python3
"""
sync_users.py

Sync authorized_users from Firestore and download their face images via public URLs.
"""

import os
import json
import requests
from google.cloud import firestore

#  CONFIGURATION 

DATA_DIR    = "/home/raspberrypi/Projects/data"
IMAGE_DIR   = os.path.join(DATA_DIR, "images")
USERS_FILE  = os.path.join(DATA_DIR, "authorized_users.json")

#  SETUP 

def setup_directories():
    os.makedirs(IMAGE_DIR, exist_ok=True)

#  SYNC FUNCTION 

def sync_authorized_users():
    db = firestore.Client()
    print("[*] Starting Firestore sync...")

    users = []

    for doc in db.collection("authorized_users").stream():
        user = doc.to_dict()
        user_id = doc.id
        user["id"] = user_id

        image_url = user.get("image_id")  # This is a public HTTPS URL now
        if image_url:
            local_path = os.path.join(IMAGE_DIR, f"{user_id}.jpg")
            try:
                resp = requests.get(image_url)
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                user["local_image_path"] = local_path
                print(f"[+] Downloaded: {image_url} → {local_path}")
            except Exception as e:
                print(f"[!] Failed to download {image_url} for {user_id}: {e}")
        else:
            print(f"[!] No image_id for {user_id}")

        users.append(user)

    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

    print(f"[*] Sync complete: {len(users)} users saved to {USERS_FILE}")

#  MAIN 

if __name__ == "__main__":
    setup_directories()
    sync_authorized_users()
