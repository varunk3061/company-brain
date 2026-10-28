import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

# Look for .env in the same folder as this script.
env_file = Path(__file__).resolve().parent / ".env"
load_dotenv(env_file)

required = [
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
]
missing = [name for name in required if not os.getenv(name)]

if missing:
    print(f"Missing values: {', '.join(missing)}")
    print(f"Checked: {env_file}")
    raise SystemExit(1)

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)

bucket = os.environ["R2_BUCKET"]
key = "healthcheck.txt"

s3.put_object(Bucket=bucket, Key=key, Body=b"ok")
print("Read result:", s3.get_object(Bucket=bucket, Key=key)["Body"].read())
print("Presigned URL:", s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=60,
))
s3.delete_object(Bucket=bucket, Key=key)
print("Test object deleted.")