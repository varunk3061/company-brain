# from database.neo4j_connection import (
#     get_neo4j_driver,
#     NEO4J_DATABASE,
# )

# #---------------------------------------------------------------------------------------------------------------------------------------

# def initialize_graph():
#     """Create constraints to prevent duplicate graph nodes."""

#     driver = get_neo4j_driver()

#     queries = [
#         """
#         CREATE CONSTRAINT document_uuid_unique IF NOT EXISTS
#         FOR (d:Document)
#         REQUIRE d.document_uuid IS UNIQUE
#         """,
#         """
#         CREATE CONSTRAINT chunk_uuid_unique IF NOT EXISTS
#         FOR (c:Chunk)
#         REQUIRE c.chunk_uuid IS UNIQUE
#         """,
#     ]

#     with driver.session(database=NEO4J_DATABASE) as session:
#         for query in queries:
#             session.run(query).consume()

# #---------------------------------------------------------------------------------------------------------------------------------------

# def sync_document_to_graph(document, chunk_records):
#     """
#     Synchronize one document and its chunks to Neo4j.

#     MongoDB remains the primary store for document data.
#     Neo4j stores the graph relationships and searchable properties.
#     """

#     driver = get_neo4j_driver()

#     # Extract access lists from the nested dictionary.
#     # Neo4j properties cannot contain nested dictionaries.

#     def get_access_fields(record):
#         """Read permissions from either supported document format."""
#         access = record.get("access")

#          # The access field must be a dictionary.
#         if not isinstance(access, dict):
#             access = {}

#         allowed_departments = record.get("allowed_departments") or []
#         allowed_roles = record.get("allowed_roles") or []
#         allowed_users = record.get("allowed_users") or []

#         return {
#             "access_departments": (
#                 access.get("departments")
#                 or allowed_departments
#             ),
#             "access_roles": (
#                 access.get("roles")
#                 or allowed_roles
#             ),
#             "access_users": (
#                 access.get("users")
#                 or allowed_users
#             ),
#         }

#     def write_graph(tx):
#         document_access = get_access_fields(document)

#         # 1. Create or update the document node.
#         tx.run(
#             """
#             MERGE (d:Document {
#                 document_uuid: $document_uuid
#             })
#             SET d.document_name = $document_name,
#                 d.file_hash = $file_hash,
#                 d.department_code = $department_code,
#                 d.classification = $classification,
#                 d.access_departments = $access_departments,
#                 d.access_roles = $access_roles,
#                 d.access_users = $access_users
#             """,
#             document_uuid=document["document_uuid"],
#             document_name=document["document_name"],
#             file_hash=document.get("file_hash"),
#             department_code=document.get("department_code"),
#             classification=document.get(
#                 "classification", "restricted"
#             ),
#             **document_access,
#         ).consume()

#         # 2. Remove old chunks and their relationships.
#         # Re-ingestion will create the current chunks again.
#         tx.run(
#             """
#             MATCH (d:Document {
#                 document_uuid: $document_uuid
#             })-[:HAS_CHUNK]->(c:Chunk)
#             DETACH DELETE c
#             """,
#             document_uuid=document["document_uuid"],
#         ).consume()

#         # 3. Create the current chunks and connect them to the document.
#         for chunk in chunk_records:
#             chunk_access = get_access_fields(chunk)

#             tx.run(
#                 """
#                 MATCH (d:Document {
#                     document_uuid: $document_uuid
#                 })
#                 MERGE (c:Chunk {
#                     chunk_uuid: $chunk_uuid
#                 })
#                 SET c.text = $text,
#                     c.source = $source,
#                     c.page = $page,
#                     c.file_hash = $file_hash,
#                     c.department_code = $department_code,
#                     c.classification = $classification,
#                     c.access_departments = $access_departments,
#                     c.access_roles = $access_roles,
#                     c.access_users = $access_users
#                 MERGE (d)-[:HAS_CHUNK]->(c)
#                 """,
#                 document_uuid=chunk["document_uuid"],
#                 chunk_uuid=chunk["chunk_uuid"],
#                 text=chunk["text"],
#                 source=chunk["source"],
#                 page=chunk["page"],
#                 file_hash=chunk.get("file_hash"),
#                 department_code=chunk.get("department_code"),
#                 classification=chunk.get(
#                     "classification", "restricted"
#                 ),
#                 **chunk_access,
#             ).consume()

#     # 4. Execute the graph update as one transaction.
#     with driver.session(database=NEO4J_DATABASE) as session:
#         session.execute_write(write_graph)

# #---------------------------------------------------------------------------------------------------------------------------------------

# # This service stores Document and Chunk nodes and connects them
# # using HAS_CHUNK. MongoDB remains the primary data store.


from database.neo4j_connection import (
    get_neo4j_driver,
    NEO4J_DATABASE,
)


# A topic is detected when one or more of its keywords
# appears in the document's chunk text.
TOPIC_RULES = [
    {
        "name": "Employee Leave",
        "keywords": [
            "leave", "pto", "sick leave", "vacation",
            "parental leave", "maternity", "paternity",
            "casual leave", "funeral leave", "holiday",
        ],
        "description": "Employee leave types, allocations, and rules.",
    },
    {
        "name": "Health Benefits",
        "keywords": [
            "health benefits", "health insurance", "medical",
            "dental", "vision insurance", "flexible spending",
        ],
        "description": "Employee healthcare and benefit programs.",
    },
    {
        "name": "Equal Employment",
        "keywords": [
            "equal employment", "equal opportunity",
            "non-discrimination", "discrimination",
            "anti-harassment", "harassment",
        ],
        "description": "Equal opportunity and anti-discrimination policies.",
    },
    {
        "name": "Dress Code",
        "keywords": [
            "dress code", "professional attire", "casual wear",
        ],
        "description": "Workplace dress and attire requirements.",
    },
    {
        "name": "Workplace Safety",
        "keywords": [
            "workplace safety", "workplace injury", "hazard",
            "emergency procedures", "evacuation routes",
        ],
        "description": "Workplace safety, hazards, and emergency procedures.",
    },
    {
        "name": "Workplace Security",
        "keywords": [
            "workplace security", "firearms", "visitors",
            "data security", "system credentials",
        ],
        "description": "Physical workplace and information security.",
    },
    {
        "name": "Compensation and Pay",
        "keywords": [
            "compensation", "pay period", "pay stub",
            "overtime", "incentive compensation",
        ],
        "description": "Employee pay and compensation rules.",
    },
    {
        "name": "Business Expenses and Financial Controls",
        "keywords": [
            "expense reimbursement", "unbudgeted expense",
            "variance reports", "travel costs",
            "contractor costs", "business expense",
        ],
        "description": "Expense reporting, approvals, and cost controls.",
    },
    {
        "name": "Financial Performance and Forecasting",
        "keywords": [
            "operating profit", "operating expenses",
            "cash reserve", "revenue forecast",
            "quarter-over-quarter", "financial forecast",
        ],
        "description": "Financial results, reserves, and revenue forecasts.",
    },
    {
        "name": "Tuition Reimbursement",
        "keywords": [
            "tuition reimbursement", "tuition",
        ],
        "description": "Employee education and tuition reimbursement.",
    },
]


def initialize_graph():
    """Create constraints that prevent duplicate graph nodes."""

    driver = get_neo4j_driver()

    queries = [
        """
        CREATE CONSTRAINT document_uuid_unique IF NOT EXISTS
        FOR (d:Document)
        REQUIRE d.document_uuid IS UNIQUE
        """,
        """
        CREATE CONSTRAINT chunk_uuid_unique IF NOT EXISTS
        FOR (c:Chunk)
        REQUIRE c.chunk_uuid IS UNIQUE
        """,
        """
        CREATE CONSTRAINT topic_name_unique IF NOT EXISTS
        FOR (t:Topic)
        REQUIRE t.name IS UNIQUE
        """,
    ]

    with driver.session(database=NEO4J_DATABASE) as session:
        for query in queries:
            session.run(query).consume()


def get_access_fields(record):
    """Convert access settings to Neo4j-compatible properties."""

    access = record.get("access")

    if not isinstance(access, dict):
        access = {}

    return {
        "access_departments": (
            access.get("departments")
            or record.get("allowed_departments")
            or []
        ),
        "access_roles": (
            access.get("roles")
            or record.get("allowed_roles")
            or []
        ),
        "access_users": (
            access.get("users")
            or record.get("allowed_users")
            or []
        ),
    }


def detect_topics(chunk_records):
    """Find topics supported by the document's actual chunk text."""

    text = " ".join(
        str(chunk.get("text", ""))
        for chunk in chunk_records
    ).lower()

    matched_topics = []

    for rule in TOPIC_RULES:
        if any(keyword in text for keyword in rule["keywords"]):
            matched_topics.append({
                "name": rule["name"],
                "description": rule["description"],
            })

    return matched_topics


def sync_document_to_graph(document, chunk_records):
    """
    Synchronize a document, its chunks, and its topic links to Neo4j.

    MongoDB remains the primary store for document content.
    Neo4j stores graph relationships and searchable properties.
    """

    driver = get_neo4j_driver()
    topics = detect_topics(chunk_records)

    def write_graph(tx):
        document_access = get_access_fields(document)

        # 1. Create or update the document node.
        tx.run(
            """
            MERGE (d:Document {document_uuid: $document_uuid})
            SET d.document_name = $document_name,
                d.file_hash = $file_hash,
                d.department_code = $department_code,
                d.classification = $classification,
                d.access_departments = $access_departments,
                d.access_roles = $access_roles,
                d.access_users = $access_users
            """,
            document_uuid=document["document_uuid"],
            document_name=document["document_name"],
            file_hash=document.get("file_hash"),
            department_code=document.get("department_code"),
            classification=document.get(
                "classification", "restricted"
            ),
            **document_access,
        ).consume()

        # 2. Remove the old chunks before replacing them.
        tx.run(
            """
            MATCH (d:Document {document_uuid: $document_uuid})
                  -[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE c
            """,
            document_uuid=document["document_uuid"],
        ).consume()

        # 3. Remove this document's old topic links.
        # Shared Topic nodes are preserved.
        tx.run(
            """
            MATCH (d:Document {document_uuid: $document_uuid})
                  -[r:HAS_TOPIC]->(:Topic)
            DELETE r
            """,
            document_uuid=document["document_uuid"],
        ).consume()

        # 4. Create the current chunks and HAS_CHUNK links.
        for chunk in chunk_records:
            chunk_access = get_access_fields(chunk)

            tx.run(
                """
                MATCH (d:Document {document_uuid: $document_uuid})
                MERGE (c:Chunk {chunk_uuid: $chunk_uuid})
                SET c.text = $text,
                    c.source = $source,
                    c.page = $page,
                    c.file_hash = $file_hash,
                    c.department_code = $department_code,
                    c.classification = $classification,
                    c.access_departments = $access_departments,
                    c.access_roles = $access_roles,
                    c.access_users = $access_users
                MERGE (d)-[:HAS_CHUNK]->(c)
                """,
                document_uuid=document["document_uuid"],
                chunk_uuid=chunk["chunk_uuid"],
                text=chunk["text"],
                source=chunk["source"],
                page=chunk["page"],
                file_hash=chunk.get("file_hash"),
                department_code=chunk.get("department_code"),
                classification=chunk.get(
                    "classification", "restricted"
                ),
                **chunk_access,
            ).consume()

        # 5. Create or reuse shared Topic nodes.
        for topic in topics:
            tx.run(
                """
                MATCH (d:Document {document_uuid: $document_uuid})
                MERGE (t:Topic {name: $topic_name})
                SET t.description = $description
                MERGE (d)-[:HAS_TOPIC]->(t)
                """,
                document_uuid=document["document_uuid"],
                topic_name=topic["name"],
                description=topic["description"],
            ).consume()

    # Apply the document update as one transaction.
    with driver.session(database=NEO4J_DATABASE) as session:
        session.execute_write(write_graph)
