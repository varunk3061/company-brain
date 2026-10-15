from getpass import getpass

from models.user_model import UserCreate
from services.admin_service import create_admin_service


def main():
    print("Create the first Company Brain admin")

    name = input("Admin name: ").strip()
    email = input("Admin email: ").strip()
    department = input("Department [IT]: ").strip() or "IT"

    password = getpass("Password (minimum 12 characters): ")
    confirm_password = getpass("Confirm password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    try:
        admin = UserCreate(
            name=name,
            email=email,
            password=password,
            department=department,
        )

        result = create_admin_service(admin)

        print("\nAdmin created successfully!")
        print("UUID:", result["admin_uuid"])
        print("Name:", result["name"])
        print("Email:", result["email"])
        print("Role:", result["role"])

    except ValueError as error:
        print("Error:", error)
    except Exception as error:
        print("Could not create admin:", error)


if __name__ == "__main__":
    main()