"""
PostgreSQL + pgvector storage backend for NeuroMem.

Provides persistent storage for user memories with vector support.
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
    
    Serves as the persistent storage for user-facing memory management (CRUD).
    
    Requires:
    - PostgreSQL with pgvector extension
    """
    
    def __init__(self, conn_str: str):
        """
        Initialize PostgreSQL backend with connection pool.
        
        Args:
            conn_str: PostgreSQL connection string
        """
        from psycopg2.pool import ThreadedConnectionPool
        self.pool = ThreadedConnectionPool(1, 10, conn_str)
        self._ensure_schema()
    
    def _get_conn(self):
        """Get a connection from the pool."""
        return self.pool.getconn()
    
    def _put_conn(self, conn):
        """Return a connection to the pool."""
        self.pool.putconn(conn)
    
    def _ensure_schema(self):
        """Ensure the database schema exists."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                # Create extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                
                # Create table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_memories (
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
                    ON user_memories(user_id);
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memory_type 
                    ON user_memories(memory_type);
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memory_embedding 
                    ON user_memories USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                """)
                
                conn.commit()
        finally:
            self._put_conn(conn)
            
    def upsert(self, item: MemoryItem) -> None:
        """Insert or update a memory item."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_memories 
                    (id, user_id, content, embedding, memory_type, salience, confidence,
                     created_at, last_accessed, decay_rate, reinforcement, inferred, editable, tags)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        last_accessed = EXCLUDED.last_accessed,
                        reinforcement = user_memories.reinforcement + 1,
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
                conn.commit()
        finally:
            self._put_conn(conn)
    
    def query(
        self,
        embedding: List[float],
        filters: Dict[str, Any],
        k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """Query for similar memories using pgvector."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build query
                where_clauses = []
                query_params = []
                
                # 1. First placeholder: embedding for similarity calculation
                query_params.append(json.dumps(embedding))
                
                # 2. Middle placeholders: WHERE clause
                if "user_id" in filters:
                    where_clauses.append("user_id = %s")
                    query_params.append(filters["user_id"])
                
                if "memory_type" in filters:
                    types = filters["memory_type"]
                    if isinstance(types, str):
                        types = [types]
                    placeholders = ','.join(['%s'] * len(types))
                    where_clauses.append(f"memory_type IN ({placeholders})")
                    query_params.extend(types)
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
                
                # 3. Third placeholder: embedding for ORDER BY
                query_params.append(json.dumps(embedding))
                
                # 4. Fourth placeholder: LIMIT
                query_params.append(k)
                
                # Execute query
                cur.execute(f"""
                    SELECT *,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM user_memories
                    WHERE {where_sql}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, query_params)
                
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
        finally:
            self._put_conn(conn)
    
    def get_by_id(self, item_id: str) -> MemoryItem | None:
        """Get a memory by ID."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM user_memories WHERE id = %s", (item_id,))
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
        finally:
            self._put_conn(conn)
    
    def update(self, item: MemoryItem) -> None:
        """Update an existing memory item."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE user_memories
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
                conn.commit()
        finally:
            self._put_conn(conn)
    
    def delete(self, item_id: str) -> bool:
        """Delete a memory item."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_memories WHERE id = %s", (item_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            self._put_conn(conn)
    
    def list_all(
        self,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 100
    ) -> List[MemoryItem]:
        """List all memories for a user."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if memory_type:
                    cur.execute("""
                        SELECT * FROM user_memories
                        WHERE user_id = %s AND memory_type = %s
                        ORDER BY last_accessed DESC
                        LIMIT %s
                    """, (user_id, memory_type, limit))
                else:
                    cur.execute("""
                        SELECT * FROM user_memories
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
        finally:
            self._put_conn(conn)
    
    def close(self):
        """Close the database connection pool."""
        self.pool.closeall()
