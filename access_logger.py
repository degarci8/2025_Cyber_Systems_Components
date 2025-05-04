import json
import datetime
from google.cloud import pubsub_v1

# Replace with your Pub/Sub topic details
PROJECT_ID = "your-project-id"
TOPIC_ID = "your-topic-id"

# Set path to your service account key
SERVICE_ACCOUNT_PATH = "/home/pi/key.json"

# Setup Pub/Sub publisher
publisher = pubsub_v1.PublisherClient.from_service_account_file(SERVICE_ACCOUNT_PATH)
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def log_access(user_id, access_status, reason=""):
    timestamp = datetime.datetime.now().isoformat()

    log_entry = {
        "timestamp": timestamp,
        "user_id": user_id,
        "access_status": access_status,  # "granted" or "denied"
        "reason": reason,
        "device": "RaspberryPi_01"
    }

    message_json = json.dumps(log_entry)
    message_bytes = message_json.encode("utf-8")

    future = publisher.publish(topic_path, data=message_bytes)
    print(f"Published log: {message_json}")
