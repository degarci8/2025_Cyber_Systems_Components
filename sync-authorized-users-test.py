#!/usr/bin/env python3
"""
sync_users.py

Sync authorized_users from Firestore and download their face images using the Cloud Storage SDK.
"""

import os
import json
from google.cloud import firestore, storage

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────

# (Optional) Hard-code this if you don't export the env var:
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/raspberrypi/Projects/service-account.json"

# Your GCS bucket name
BUCKET_NAME = "your-bucket-name"

# Paths for local storage
DATA_DIR   = "/home/raspberrypi/Projects/data"
IMAGE_DIR  = os.path.join(DATA_DIR, "images")
USERS_FILE = os.path.join(DATA_DIR, "authorized_users.json")

#  SETUP 

def setup_directories():
    """Ensure data and image directories exist."""
    os.makedirs(IMAGE_DIR, exist_ok=True)

#  SYNC FUNCTION 

def sync_authorized_users():
    """Fetch users from Firestore and download images via GCS SDK."""
    # Initialize clients
    db = firestore.Client()
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)

    print("[*] Starting Firestore sync...")
    users = []

    for doc in db.collection("authorized_users").stream():
        user = doc.to_dict()
        user_id = doc.id
        user["id"] = user_id

        image_id = user.get("image_id")
        if image_id:
            local_path = os.path.join(IMAGE_DIR, f"{user_id}.jpg")
            try:
                # Download directly from GCS
                blob = bucket.blob(image_id)
                blob.download_to_filename(local_path)
                user["local_image_path"] = local_path
                print(f"[+] Downloaded {image_id} → {local_path}")
            except Exception as e:
                print(f"[!] Error downloading {image_id} for {user_id}: {e}")
        else:
            print(f"[!] No image_id for user {user_id}")

        users.append(user)

    # Write out the JSON file
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    print(f"[*] Sync complete: {len(users)} users saved to {USERS_FILE}")

#  MAIN 

if __name__ == "__main__":
    setup_directories()
    sync_authorized_users()


