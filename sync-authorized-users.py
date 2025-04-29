# Filename: sync_authorized_users.py

from google.cloud import firestore
import os
import json

def sync_authorized_users():
    # Set the path to your service account key JSON
    # (replace with your actual path if needed)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path/to/your/service-account-key.json"

    # Initialize Firestore client
    db = firestore.Client()

    # Reference the 'authorized_users' collection
    users_ref = db.collection('authorized_users')

    # Get all documents in the collection
    docs = users_ref.stream()

    authorized_users = []

    for doc in docs:
        user_data = doc.to_dict()
        authorized_users.append(user_data)

    # (Simulate caching: just print or write to file for now)
    print("=== Synced Authorized Users ===")
    print(json.dumps(authorized_users, indent=2))

    # Optionally: save locally as JSON for Pi caching
    with open('authorized_users_cache.json', 'w') as f:
        json.dump(authorized_users, f, indent=2)

if __name__ == "__main__":
    sync_authorized_users()
