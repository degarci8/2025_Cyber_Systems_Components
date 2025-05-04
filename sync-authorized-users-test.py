#!/usr/bin/env python3
"""
sync_users.py

Sync authorized_users from Firestore and download their face images from Cloud Storage.
"""

import os
import json
from google.cloud import firestore, storage

#  CONFIGURATION 

# Path to your service account JSON (if not using env var)
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/raspberrypi/Projects/service-account.json"

# GCS bucket where images are stored
BUCKET_NAME = "authorized-users-bucket"

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
    """Fetch all users from Firestore and download their images locally via GCS."""
    # Initialize clients
    db = firestore.Client()
    storage_client = storage.Client()

    print("[*] Starting Firestore sync...")
    users = []

    for doc in db.collection("authorized_users").stream():
        user = doc.to_dict()
        user["id"] = doc.id

        image_id = user.get("image_id")
        if image_id:
            local_path = os.path.join(IMAGE_DIR, f"{doc.id}.jpg")
            try:
                bucket = storage_client.bucket(BUCKET_NAME)
                blob = bucket.blob(image_id)
                blob.download_to_filename(local_path)
                user["local_image_path"] = local_path
                print(f"[+] Downloaded image for {doc.id} to {local_path}")
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

if __name__ == "__main__":
    setup_directories()
    sync_authorized_users()

