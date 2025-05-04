from google.cloud import storage
import os

# Verify correct service account is being used
print("Using credentials from:", os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))

client = storage.Client()
bucket = client.bucket("your-bucket-name")

# List all blobs in the folder
print("Available blobs:")
for blob in bucket.list_blobs(prefix="images/"):
    print(" -", blob.name)

# Now try to download a known blob
blob = bucket.blob("images/user_001.jpeg")
blob.download_to_filename("/tmp/test.jpeg")
print("Downloaded image successfully to /tmp/test.jpeg")

