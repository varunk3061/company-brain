# Fills the database with starting departments and roles for your sample company, Nexora.

from datetime import datetime, timezone
from uuid import uuid4

from database.connection import departments_collection, roles_collection

#-------------------------------------------------------------------------------------

# Source: Documents/orgChart.docx (Nexora Technologies). (code, name)
DEPARTMENTS = [
    ("EXEC", "Company Leadership / Administration"),
    ("HR", "Human Resources"),
    ("IT", "Information Technology"),
    ("SALES", "Sales"),
    ("FIN", "Finance"),
    ("LEGAL", "Legal & Compliance"),
]

ADMIN_PERMS = ["users.manage", "org.manage", "documents.manage", "audit.read"]
APPROVER = ["documents.approve"]

# (code, name, department_code, clearance, permissions)
ROLES = [
    ("CEO", "CEO", "EXEC", "restricted", ["documents.approve", "audit.read"]),
    ("SYSTEM_ADMIN", "System Administrator", "EXEC", "internal", ADMIN_PERMS),
    ("TALENT_ACQUISITION", "Talent Acquisition Specialist", "HR", "internal", []),
    ("HR_GENERALIST", "HR Generalist", "HR", "internal", []),
    ("HR_OPERATIONS", "HR Operations Specialist", "HR", "confidential", ["sensitive.pii.read"]),
    ("HR_BUSINESS_PARTNER", "HR Business Partner", "HR", "confidential", APPROVER + ["sensitive.pii.read", "sensitive.compensation.read"]),
    ("DEVELOPER", "Developer", "IT", "internal", []),
    ("IT_MANAGER", "IT Manager", "IT", "confidential", APPROVER),  # not in the org chart; added for the existing IT manager
    ("QA_ENGINEER", "QA Engineer", "IT", "internal", []),
    ("DEVOPS_ENGINEER", "DevOps Engineer", "IT", "internal", []),
    ("SALES_MANAGER", "Sales Manager", "SALES", "confidential", APPROVER),
    ("SALES_DEV_REP", "Sales Development Representative", "SALES", "internal", []),
    ("RELATIONSHIP_MANAGER", "Relationship Manager", "SALES", "internal", []),
    ("ACCOUNTING_MANAGER", "Accounting Manager", "FIN", "confidential", APPROVER + ["sensitive.financial.read"]),
    ("FINANCIAL_ANALYST", "Financial Analyst", "FIN", "confidential", ["sensitive.financial.read"]),
    ("PAYROLL_SPECIALIST", "Payroll Specialist", "FIN", "confidential", ["sensitive.pii.read", "sensitive.compensation.read", "sensitive.financial.read"]),
    ("HEAD_OF_LEGAL", "Head of Legal", "LEGAL", "restricted", APPROVER + ["sensitive.legal.read"]),
    ("LEGAL_COUNSEL", "Legal Counsel / Contracts Specialist", "LEGAL", "confidential", ["sensitive.legal.read"]),
    ("COMPLIANCE_ANALYST", "Compliance Analyst", "LEGAL", "confidential", []),
]

#-------------------------------------------------------------------------------------

def seed_org() -> None:
    """Insert missing departments and roles. Never overwrites existing rows (admins may have edited them)."""

    now = datetime.now(timezone.utc)

    for code, name in DEPARTMENTS:
        departments_collection.update_one(
            {"code": code},
            {"$setOnInsert": {
                "department_uuid": str(uuid4()), "code": code, "name": name,
                "status": "active", "created_at": now, "updated_at": now,
            }},
            upsert=True,
        )

    for code, name, department_code, clearance, permissions in ROLES:
        roles_collection.update_one(
            {"code": code},
            {"$setOnInsert": {
                "role_uuid": str(uuid4()), "code": code, "name": name,
                "department_code": department_code, "clearance": clearance,
                "permissions": list(permissions), "status": "active",
                "created_at": now, "updated_at": now,
            }},
            upsert=True,
        )
