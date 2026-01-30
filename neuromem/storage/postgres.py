"""
PostgreSQL + pgvector storage backend for NeuroMem.

Production-ready storage with vector similarity search.
"""

import json
from typing import List, Dict, Any, Tuple
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from neuromem.core.types import MemoryItem, MemoryType


class PostgresBackend:
    """
    PostgreSQL storage backend with pgvector extension.
    
    Requires:
    - PostgreSQL with pgvector extension
    - Database schema created (see schema.sql)
    """
    
    def __init__(self, conn_str: str):
        """
        Initialize PostgreSQL backend.
        
        Args:
            conn_str: PostgreSQL connection string
                     (e.g., "postgresql://user:pass@localhost:5432/neuromem")
        """
        self.conn = psycopg2.connect(conn_str)
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Ensure the database schema exists."""
        with self.conn.cursor() as cur:
            # Create extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_items (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL,
                    content TEXT NOT NULL,
                    embedding VECTOR(1536),
                    memory_type TEXT,
                    salience FLOAT,
                    confidence FLOAT,
                    created_at TIMESTAMP,
                    last_accessed TIMESTAMP,
                    decay_rate FLOAT,
                    reinforcement INT,
                    inferred BOOLEAN,
                    editable BOOLEAN,
                    tags TEXT[]
                );
            """)
            
            # Create indexes
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_user 
                ON memory_items(user_id);
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_type 
                ON memory_items(memory_type);
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_embedding 
                ON memory_items USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            
            self.conn.commit()
    
    def upsert(self, item: MemoryItem) -> None:
        """Insert or update a memory item."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO memory_items 
                (id, user_id, content, embedding, memory_type, salience, confidence,
                 created_at, last_accessed, decay_rate, reinforcement, inferred, editable, tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    last_accessed = EXCLUDED.last_accessed,
                    reinforcement = memory_items.reinforcement + 1,
                    confidence = EXCLUDED.confidence,
                    salience = EXCLUDED.salience
            """, (
                item.id,
                item.user_id,
                item.content,
                json.dumps(item.embedding),
                item.memory_type.value if isinstance(item.memory_type, MemoryType) else item.memory_type,
                item.salience,
                item.confidence,
                item.created_at,
                item.last_accessed,
                item.decay_rate,
                item.reinforcement,
                item.inferred,
                item.editable,
                item.tags
            ))
            self.conn.commit()
    
    def query(
        self,
        embedding: List[float],
        filters: Dict[str, Any],
        k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """Query for similar memories using pgvector."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Build query
            where_clauses = []
            params = [json.dumps(embedding), k]
            
            if "user_id" in filters:
                where_clauses.append("user_id = %s")
                params.insert(0, filters["user_id"])
            
            if "memory_type" in filters:
                types = filters["memory_type"]
                if isinstance(types, str):
                    types = [types]
                placeholders = ','.join(['%s'] * len(types))
                where_clauses.append(f"memory_type IN ({placeholders})")
                for t in types:
                    params.insert(-1, t)
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            
            # Execute query
            cur.execute(f"""
                SELECT *,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM memory_items
                WHERE {where_sql}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, params)
            
            rows = cur.fetchall()
            
            if not rows:
                return [], []
            
            items = []
            similarities = []
            
            for row in rows:
                item = MemoryItem(
                    id=row['id'],
                    user_id=row['user_id'],
                    content=row['content'],
                    embedding=json.loads(row['embedding']) if isinstance(row['embedding'], str) else row['embedding'],
                    memory_type=MemoryType(row['memory_type']),
                    salience=row['salience'],
                    confidence=row['confidence'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    decay_rate=row['decay_rate'],
                    reinforcement=row['reinforcement'],
                    inferred=row['inferred'],
                    editable=row['editable'],
                    tags=row['tags'] or []
                )
                items.append(item)
                similarities.append(row['similarity'])
            
            return items, similarities
    
    def get_by_id(self, item_id: str) -> MemoryItem | None:
        """Get a memory by ID."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM memory_items WHERE id = %s", (item_id,))
            row = cur.fetchone()
            
            if not row:
                return None
            
            return MemoryItem(
                id=row['id'],
                user_id=row['user_id'],
                content=row['content'],
                embedding=json.loads(row['embedding']) if isinstance(row['embedding'], str) else row['embedding'],
                memory_type=MemoryType(row['memory_type']),
                salience=row['salience'],
                confidence=row['confidence'],
                created_at=row['created_at'],
                last_accessed=row['last_accessed'],
                decay_rate=row['decay_rate'],
                reinforcement=row['reinforcement'],
                inferred=row['inferred'],
                editable=row['editable'],
                tags=row['tags'] or []
            )
    
    def update(self, item: MemoryItem) -> None:
        """Update an existing memory item."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE memory_items
                SET content = %s,
                    embedding = %s,
                    last_accessed = %s,
                    confidence = %s,
                    salience = %s
                WHERE id = %s
            """, (
                item.content,
                json.dumps(item.embedding),
                item.last_accessed,
                item.confidence,
                item.salience,
                item.id
            ))
            self.conn.commit()
    
    def delete(self, item_id: str) -> bool:
        """Delete a memory item."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM memory_items WHERE id = %s", (item_id,))
            self.conn.commit()
            return cur.rowcount > 0
    
    def list_all(
        self,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 100
    ) -> List[MemoryItem]:
        """List all memories for a user."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if memory_type:
                cur.execute("""
                    SELECT * FROM memory_items
                    WHERE user_id = %s AND memory_type = %s
                    ORDER BY last_accessed DESC
                    LIMIT %s
                """, (user_id, memory_type, limit))
            else:
                cur.execute("""
                    SELECT * FROM memory_items
                    WHERE user_id = %s
                    ORDER BY last_accessed DESC
                    LIMIT %s
                """, (user_id, limit))
            
            rows = cur.fetchall()
            
            return [
                MemoryItem(
                    id=row['id'],
                    user_id=row['user_id'],
                    content=row['content'],
                    embedding=json.loads(row['embedding']) if isinstance(row['embedding'], str) else row['embedding'],
                    memory_type=MemoryType(row['memory_type']),
                    salience=row['salience'],
                    confidence=row['confidence'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    decay_rate=row['decay_rate'],
                    reinforcement=row['reinforcement'],
                    inferred=row['inferred'],
                    editable=row['editable'],
                    tags=row['tags'] or []
                )
                for row in rows
            ]
    
    def close(self):
        """Close the database connection."""
        self.conn.close()
