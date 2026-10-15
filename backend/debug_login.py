"""
Debug - tests password verification directly against the stored hash.
Run: python debug_login.py
"""
import sys
import os

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

from database.connection import users_collection
from utils.security import verify_password, hash_password

email = "coco@gmail.com"

doc = users_collection.find_one({"email": email})

if not doc:
    print(f"No document found for {email}")
    sys.exit(1)

print(f"Document found: email={doc['email']}, role={doc['role']}, isActive={doc['isActive']}")
print(f"Password hash : {doc['password']}")

# Test a few passwords — add yours here
test_passwords = ["coco1234", "password", "admin123", "coco"]

print("\n--- Password Tests ---")
for pw in test_passwords:
    result = verify_password(pw, doc["password"])
    print(f"  '{pw}' -> {result}")

# Also confirm query works
q = users_collection.find_one({"email": email, "role": "admin", "isActive": True})
print(f"\nFull login query match: {q is not None}")
