#!/usr/bin/env python3
"""
sync_users.py

Sync authorized_users from Firestore and download their face images
using the Cloud Storage SDK.
"""

import os
import json
from urllib.parse import urlparse
from google.cloud import firestore, storage

#  CONFIGURATION 

# If not set externally, uncomment and set your service account path:
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/raspberrypi/Projects/service-account.json"

# Local storage paths
DATA_DIR   = "/home/raspberrypi/Projects/data"
IMAGE_DIR  = os.path.join(DATA_DIR, "images")
USERS_FILE = os.path.join(DATA_DIR, "authorized_users.json")

#  SETUP 

def setup_directories():
    """Ensure data and image directories exist."""
    os.makedirs(IMAGE_DIR, exist_ok=True)

#  SYNC FUNCTION 

def sync_authorized_users():
    """Fetch users from Firestore and download images via Cloud Storage SDK."""
    # Initialize clients
    db = firestore.Client()
    storage_client = storage.Client()

    print("[*] Starting Firestore sync...")
    users = []

    for doc in db.collection("authorized_users").stream():
        user = doc.to_dict()
        user_id = doc.id
        user["id"] = user_id

        image_id = user.get("image_id")
        if not image_id:
            print(f"[!] No image_id for user {user_id}")
            users.append(user)
            continue

        local_path = os.path.join(IMAGE_DIR, f"{user_id}.jpg")

        try:
            # 1) Handle storage.cloud.google.com URLs
            if image_id.startswith("https://storage.cloud.google.com/"):
                parsed = urlparse(image_id)
                # parsed.path: '/bucket-name/path/to/blob'
                path = parsed.path.lstrip('/')
                bucket_name, blob_name = path.split('/', 1)

                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.download_to_filename(local_path)
                print(f"[+] GCS ↓ {bucket_name}/{blob_name} → {local_path}")

            # 2) Handle gs:// URIs
            elif image_id.startswith("gs://"):
                _, rest = image_id.split("gs://", 1)
                bucket_name, blob_name = rest.split('/', 1)

                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.download_to_filename(local_path)
                print(f"[+] GCS ↓ {bucket_name}/{blob_name} → {local_path}")

            # 3) Assume a public HTTPS URL (e.g., storage.googleapis.com)
            else:
                import requests
                resp = requests.get(image_id, timeout=10)
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                print(f"[+] HTTP ↓ {image_id} → {local_path}")

            # Attach local path once downloaded
            user["local_image_path"] = local_path

        except Exception as e:
            print(f"[!] Download failed for {user_id} ({image_id}): {e}")

        users.append(user)

    # Write out the JSON file
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

    print(f"[*] Sync complete: {len(users)} users saved to {USERS_FILE}")

#  MAIN 

if __name__ == "__main__":
    setup_directories()
    sync_authorized_users()


