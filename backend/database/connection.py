import os

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

# Load environment from backend/.env
load_dotenv()

# Read MongoDB configuration
MONGODB_URI=os.getenv("MONGODB_URI")
DATABASE_NAME=os.getenv("DATABASE_NAME")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI is missing from .env")

if not DATABASE_NAME:
    raise ValueError("DATABASE_NAME is missing from .env")

# Create MongoDB Connection
client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)

# Select the Configured Database
db = client[DATABASE_NAME]

# Select the employee collection
employees_collection = db["employee"]

admins_collection = db["admins"]

#----------------------------------------------------------------------------------------------------

def create_indexes():
    """Create indexes that enforce unique employee identifiers.
        The purpose of this function is to prevent duplicate employee IDs and email addresses in the database.
    """

    employees_collection.create_index(
        [("employee_uuid", ASCENDING)],
        unique=True,
        name="unique_employee_uuid"
    )

    employees_collection.create_index(
        [("email", ASCENDING)],
        unique=True,
        name="unique_employee_email"
    )

    admins_collection.create_index(
        [("admin_uuid", ASCENDING)],
        unique=True,
        name="unique_admin_uuid"
    )

    admins_collection.create_index(
        [("email", ASCENDING)],
        unique=True,
        name="unique_admin_email"
    )

#----------------------------------------------------------------------------------------------------

def check_database_connection():
    """Check whether MonoDB is reachable."""

    try:
        client.admin.command("ping")
        create_indexes()
        print("MongoDB connected successfully.")

    except PyMongoError as error:
        raise RuntimeError(
            f"Could not connect to MongoDB {error}"
        ) from error

#----------------------------------------------------------------------------------------------------