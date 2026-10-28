import logging

from database.neo4j_connection import (
    get_neo4j_driver,
    NEO4J_DATABASE,
)

from services.entity_service import extract_from_chunks

logger = logging.getLogger(__name__)

# Full-text index on entity keys, used to find entity names in a question.
ENTITY_FULLTEXT_INDEX = "entity_key_fulltext"

#------------------------------------------------------------------------------------------------------------------------------

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

#------------------------------------------------------------------------------------------------------------------------------

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
        # One node per entity, e.g. only one "finance dept".
        """
        CREATE CONSTRAINT entity_key_unique IF NOT EXISTS
        FOR (e:Entity)
        REQUIRE e.key IS UNIQUE
        """,
        # Fast clean-up of a document's relations on delete or re-upload.
        """
        CREATE INDEX related_to_document IF NOT EXISTS
        FOR ()-[r:RELATED_TO]-()
        ON (r.document_uuid)
        """,
    ]

    with driver.session(database=NEO4J_DATABASE) as session:
        for query in queries:
            session.run(query).consume()

    # Optional: retrieval falls back to scanning all entity keys without it,
    # so a Neo4j edition/version that rejects it must not stop startup.
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            session.run(
                f"""
                CREATE FULLTEXT INDEX {ENTITY_FULLTEXT_INDEX} IF NOT EXISTS
                FOR (e:Entity) ON EACH [e.key]
                """
            ).consume()
    except Exception as exc:
        logger.warning("Could not create the entity full-text index: %s: %s", type(exc).__name__, exc)


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

#------------------------------------------------------------------------------------------------------------------------------

def _load_saved_entities(document_uuid, file_hash):
    """
    Reuse entities already in Neo4j when the PDF has not changed,
    so re-ingesting does not call Groq again. Returns None if nothing is saved.
    """

    if not file_hash:
        return None

    driver = get_neo4j_driver()

    with driver.session(database=NEO4J_DATABASE) as session:
        entities = session.run(
            """
            MATCH (d:Document {document_uuid: $document_uuid, file_hash: $file_hash})
                  -[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
            RETURN e.key AS key, e.name AS name, e.type AS type, c.chunk_uuid AS chunk_uuid
            """,
            document_uuid=document_uuid,
            file_hash=file_hash,
        ).data()

        if not entities:
            return None

        relations = session.run(
            """
            MATCH (a:Entity)-[r:RELATED_TO {document_uuid: $document_uuid}]->(b:Entity)
            RETURN a.key AS from_key, b.key AS to_key, r.type AS type, r.chunk_uuid AS chunk_uuid
            """,
            document_uuid=document_uuid,
        ).data()

    return {"entities": entities, "relations": relations}

#------------------------------------------------------------------------------------------------------------------------------

def sync_document_to_graph(document, chunk_records):
    """
    Synchronize a document, its chunks, and its topic links to Neo4j.

    MongoDB remains the primary store for document content.
    Neo4j stores graph relationships and searchable properties.
    """

    driver = get_neo4j_driver()
    topics = detect_topics(chunk_records)

    # LLM calls happen here, OUTSIDE the Neo4j transaction (they are slow).
    graph_data = _load_saved_entities(document["document_uuid"], document.get("file_hash"))
    if graph_data is None:
        graph_data = extract_from_chunks(chunk_records)

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

        # 3b. Remove this document's old entity relations.
        # (Old MENTIONS links are already gone: step 2 deleted the old chunks.)
        tx.run(
            """
            MATCH ()-[r:RELATED_TO {document_uuid: $document_uuid}]->()
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

                # 6. Entities: Chunk -[:MENTIONS]-> Entity (one shared node per entity key).
        tx.run(
            """
            UNWIND $entities AS ent
            MATCH (c:Chunk {chunk_uuid: ent.chunk_uuid})
            MERGE (e:Entity {key: ent.key})
              ON CREATE SET e.name = ent.name, e.type = ent.type
            MERGE (c)-[:MENTIONS]->(e)
            """,
            entities=graph_data["entities"],
        ).consume()

        # 7. Relations: Entity -[:RELATED_TO {type}]-> Entity, with the chunk/document as evidence.
        tx.run(
            """
            UNWIND $relations AS rel
            MATCH (a:Entity {key: rel.from_key})
            MATCH (b:Entity {key: rel.to_key})
            MERGE (a)-[r:RELATED_TO {type: rel.type, chunk_uuid: rel.chunk_uuid}]->(b)
            SET r.document_uuid = $document_uuid
            """,
            relations=graph_data["relations"],
            document_uuid=document["document_uuid"],
        ).consume()

        # 8. Remove entities no chunk mentions any more (left over from older versions).
        tx.run(
            """
            MATCH (e:Entity)
            WHERE NOT (e)<-[:MENTIONS]-(:Chunk)
            DETACH DELETE e
            """
        ).consume()

    # Apply the document update as one transaction.
    with driver.session(database=NEO4J_DATABASE) as session:
        session.execute_write(write_graph)

#---------------------------------------------------------------------------------------------------------------

def delete_document_from_graph(document_uuid):
    """Remove a document and its chunk from neo4j. Shared topic nodes are kept. """

    driver = get_neo4j_driver()

    def delete_graph(tx):
        # 1. Remove relations whose evidence came from this document.
        tx.run(
            """
            MATCH ()-[r:RELATED_TO {document_uuid: $document_uuid}]->()
            DELETE r
            """,
            document_uuid=document_uuid,
        ).consume()

        # 2. Remove document and its chunks (MENTIONS links go with the chunks).
        tx.run(
            """
            MATCH (d:Document {document_uuid: $document_uuid})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE c, d
            """,
            document_uuid=document_uuid,
        ).consume()

        # 3. Remove entities no remaining chunk mentions. Shared ones are kept
        tx.run(
            """
            MATCH (e:Entity)
            WHERE NOT (e)<-[:MENTIONS]-(:Chunk)
            DETACH DELETE e
            """
        ).consume()

    # All three steps succeed or fail together.
    with driver.session(database=NEO4J_DATABASE) as session:
        session.execute_write(delete_graph)

#---------------------------------------------------------------------------------------------------------------

def update_document_access_in_graph(document_uuid, department_code, classification, access):
    """Copy a document's new access rules onto its Document and chunk nodes."""

    driver = get_neo4j_driver()
    access = access or {}

    with driver.session(database=NEO4J_DATABASE) as session:
        session.run(
            """
            MATCH (d:Document {document_uuid: $document_uuid})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            with collect(d) + collect(c) as nodes
            UNWIND nodes as n
            SET n.department_code = $department_code,
                   n.classification = $classification,
                   n.access_departments = $access_departments,
                   n.access_roles = $access_roles,
                   n.access_users = $access_users
            """,
            document_uuid = document_uuid,
            department_code = department_code,
            classification = classification,
            access_departments = access.get("departments", []),
            access_roles = access.get("roles", []),
            access_users = access.get("users", [],)
        ).consume()

#------------------------------------------------------------------------------------------------------------------------------