#!/usr/bin/env python3
"""
sync_users.py

Sync authorized_users from Firestore and download their face images.
"""

import os
import json
import requests
from google.cloud import firestore

#  CONFIGURATION 

# If you want to hard-code the service account path instead of exporting
# GOOGLE_APPLICATION_CREDENTIALS in your shell, uncomment and set this:
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/your_project/service-account.json"

# Local storage paths
DATA_DIR    = "/home/raspberrypi/Projects/data"
IMAGE_DIR   = os.path.join(DATA_DIR, "images")
USERS_FILE  = os.path.join(DATA_DIR, "authorized_users.json")

#  SETUP 

def setup_directories():
    """Create data/images folders if they don't exist."""
    os.makedirs(IMAGE_DIR, exist_ok=True)

#  SYNC FUNCTION 

def sync_authorized_users():
    """Fetch all users from Firestore and download their images locally."""
    db = firestore.Client()
    print("[*] Starting Firestore sync...")

    users = []
    for doc in db.collection("authorized_users").stream():
        user = doc.to_dict()
        user["id"] = doc.id

        # Download image via the image_id field
        image_id = user.get("image_id")
        if image_id:
            local_path = os.path.join(IMAGE_DIR, f"{doc.id}.jpg")
            try:
                resp = requests.get(image_id)
                resp.raise_for_status()
                with open(local_path, "wb") as img:
                    img.write(resp.content)
                user["local_image_path"] = local_path
                print(f"[+] Image downloaded for {doc.id}")
            except Exception as e:
                print(f"[!] Failed to download image for {doc.id}: {e}")
        else:
            print(f"[!] No image_id found for {doc.id}")

        users.append(user)

    # Write out the JSON file
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

    print(f"[*] Sync complete: {len(users)} users saved to {USERS_FILE}")

#  MAIN 

def main():
    setup_directories()
    sync_authorized_users()

if __name__ == "__main__":
    main()

