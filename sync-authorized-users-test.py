#!/usr/bin/env python3
"""
sync_users.py

Downloads user images from Firestore (image_id = GCS URL).
"""

import os
import json
from urllib.parse import urlparse
from google.cloud import firestore, storage

# CONFIG
DATA_DIR    = "/home/raspberrypi/Projects/data"
IMAGE_DIR   = os.path.join(DATA_DIR, "images")
USERS_FILE  = os.path.join(DATA_DIR, "authorized_users.json")

def setup_directories():
    os.makedirs(IMAGE_DIR, exist_ok=True)

def sync_authorized_users():
    db = firestore.Client()
    storage_client = storage.Client()

    users = []
    for doc in db.collection("authorized_users").stream():
        user = doc.to_dict()
        user_id = doc.id
        user["id"] = user_id

        image_url = user.get("image_id")
        if not image_url:
            print(f"[!] No image_id for {user_id}")
            users.append(user)
            continue

        try:
            parsed = urlparse(image_url)
            path_parts = parsed.path.lstrip("/").split("/", 1)
            bucket_name = path_parts[0]
            blob_name = path_parts[1]

            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)

            local_path = os.path.join(IMAGE_DIR, f"{user_id}.jpg")
            blob.download_to_filename(local_path)
            user["local_image_path"] = local_path
            print(f"[+] Downloaded {blob_name} from {bucket_name} → {local_path}")
        except Exception as e:
            print(f"[!] Failed to download for {user_id}: {e}")

        users.append(user)

    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

    print(f"[*] Sync complete: {len(users)} users")

if __name__ == "__main__":
    setup_directories()
    sync_authorized_users()
