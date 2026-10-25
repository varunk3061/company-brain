import os

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

# Load environment from backend/.env
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI is missing from .env")

if not DATABASE_NAME:
    raise ValueError("DATABASE_NAME is missing from .env")

if MONGODB_URI.startswith("mongomock://"):
    # In-memory fake used only by the test-suite (requirements-dev.txt).
    import mongomock
    client = mongomock.MongoClient()
else:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)

db = client[DATABASE_NAME]

# Org structure and accounts
departments_collection = db["departments"]
roles_collection = db["roles"]
users_collection = db["users"]

# Documents and change history
documents_collection = db["documents"]
documents_chunk_collection = db["documents_chunk"]  # text chunks + embeddings, each with a copy of its document's access fields
audit_log_collection = db["audit_log"]

# Legacy collections: read only by scripts/migrate_users.py and the startup bootstrap guard.
employees_collection = db["employee"]
admins_collection = db["admins"]

#----------------------------------------------------------------------------------------------------

def create_indexes():
    """Create the unique and lookup indexes the access model relies on."""

    departments_collection.create_index([("code", ASCENDING)], unique=True, name="unique_department_code")
    roles_collection.create_index([("code", ASCENDING)], unique=True, name="unique_role_code")
    roles_collection.create_index([("department_code", ASCENDING)], name="role_department")

    users_collection.create_index([("user_uuid", ASCENDING)], unique=True, name="unique_user_uuid")
    users_collection.create_index([("email", ASCENDING)], unique=True, name="unique_user_email")
    users_collection.create_index(
        [("department_code", ASCENDING), ("role_code", ASCENDING)], name="user_department_role"
    )

    documents_collection.create_index(
        [("department_code", ASCENDING), ("classification", ASCENDING)], name="document_dept_class"
    )
    audit_log_collection.create_index([("ts", -1)], name="audit_ts")

    documents_chunk_collection.create_index([("chunk_uuid", ASCENDING)], unique=True, name="unique_chunk_uuid")
    documents_chunk_collection.create_index([("document_uuid", ASCENDING)], name="document_uuid_index")

#----------------------------------------------------------------------------------------------------

def check_database_connection():
    """Check whether MongoDB is reachable, then make sure indexes exist."""

    try:
        client.admin.command("ping")
        create_indexes()
        print("MongoDB connected successfully.")

    except PyMongoError as error:
        raise RuntimeError(
            f"Could not connect to MongoDB {error}"
        ) from error
