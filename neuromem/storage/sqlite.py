"""
SQLite storage backend for NeuroMem.

Lightweight storage option for development and small deployments.
"""

import json
import sqlite3
from typing import List, Dict, Any, Tuple
from datetime import datetime
import numpy as np
from neuromem.core.types import MemoryItem, MemoryType


class SQLiteBackend:
    """
    SQLite storage backend.
    
    Simpler alternative to PostgreSQL for development and small deployments.
    Uses numpy for vector similarity calculations.
    """
    
    def __init__(self, db_path: str = "neuromem.db"):
        """
        Initialize SQLite backend.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Ensure the database schema exists."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT,
                memory_type TEXT,
                salience REAL,
                confidence REAL,
                created_at TEXT,
                last_accessed TEXT,
                decay_rate REAL,
                reinforcement INTEGER,
                inferred INTEGER,
                editable INTEGER,
                tags TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_user 
            ON memory_items(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_type 
            ON memory_items(memory_type)
        """)
        
        self.conn.commit()
    
    def upsert(self, item: MemoryItem) -> None:
        """Insert or update a memory item."""
        cursor = self.conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT reinforcement FROM memory_items WHERE id = ?", (item.id,))
        existing = cursor.fetchone()
        
        reinforcement = item.reinforcement
        if existing:
            reinforcement = existing[0] + 1
        
        cursor.execute("""
            INSERT OR REPLACE INTO memory_items
            (id, user_id, content, embedding, memory_type, salience, confidence,
             created_at, last_accessed, decay_rate, reinforcement, inferred, editable, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.id,
            item.user_id,
            item.content,
            json.dumps(item.embedding),
            item.memory_type.value if isinstance(item.memory_type, MemoryType) else item.memory_type,
            item.salience,
            item.confidence,
            item.created_at.isoformat(),
            item.last_accessed.isoformat(),
            item.decay_rate,
            reinforcement,
            1 if item.inferred else 0,
            1 if item.editable else 0,
            json.dumps(item.tags)
        ))
        
        self.conn.commit()
    
    def query(
        self,
        embedding: List[float],
        filters: Dict[str, Any],
        k: int
    ) -> Tuple[List[MemoryItem], List[float]]:
        """Query for similar memories using cosine similarity."""
        cursor = self.conn.cursor()
        
        # Build query
        where_clauses = []
        params = []
        
        if "user_id" in filters:
            where_clauses.append("user_id = ?")
            params.append(filters["user_id"])
        
        if "memory_type" in filters:
            types = filters["memory_type"]
            if isinstance(types, str):
                types = [types]
            placeholders = ','.join(['?'] * len(types))
            where_clauses.append(f"memory_type IN ({placeholders})")
            params.extend(types)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        cursor.execute(f"""
            SELECT * FROM memory_items
            WHERE {where_sql}
        """, params)
        
        rows = cursor.fetchall()
        
        if not rows:
            return [], []
        
        # Calculate similarities
        query_vec = np.array(embedding)
        items = []
        similarities = []
        
        for row in rows:
            item = self._row_to_item(row)
            item_vec = np.array(item.embedding)
            similarity = self._cosine_similarity(query_vec, item_vec)
            
            items.append(item)
            similarities.append(similarity)
        
        # Sort by similarity
        sorted_pairs = sorted(
            zip(items, similarities),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Take top k
        top_k = sorted_pairs[:k]
        
        if not top_k:
            return [], []
        
        items, sims = zip(*top_k)
        return list(items), list(sims)
    
    def get_by_id(self, item_id: str) -> MemoryItem | None:
        """Get a memory by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return self._row_to_item(row)
    
    def update(self, item: MemoryItem) -> None:
        """Update an existing memory item."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memory_items
            SET content = ?,
                embedding = ?,
                last_accessed = ?,
                confidence = ?,
                salience = ?
            WHERE id = ?
        """, (
            item.content,
            json.dumps(item.embedding),
            item.last_accessed.isoformat(),
            item.confidence,
            item.salience,
            item.id
        ))
        self.conn.commit()
    
    def delete(self, item_id: str) -> bool:
        """Delete a memory item."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memory_items WHERE id = ?", (item_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def list_all(
        self,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 100
    ) -> List[MemoryItem]:
        """List all memories for a user."""
        cursor = self.conn.cursor()
        
        if memory_type:
            cursor.execute("""
                SELECT * FROM memory_items
                WHERE user_id = ? AND memory_type = ?
                ORDER BY last_accessed DESC
                LIMIT ?
            """, (user_id, memory_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM memory_items
                WHERE user_id = ?
                ORDER BY last_accessed DESC
                LIMIT ?
            """, (user_id, limit))
        
        rows = cursor.fetchall()
        return [self._row_to_item(row) for row in rows]
    
    def _row_to_item(self, row: sqlite3.Row) -> MemoryItem:
        """Convert a database row to a MemoryItem."""
        return MemoryItem(
            id=row['id'],
            user_id=row['user_id'],
            content=row['content'],
            embedding=json.loads(row['embedding']),
            memory_type=MemoryType(row['memory_type']),
            salience=row['salience'],
            confidence=row['confidence'],
            created_at=datetime.fromisoformat(row['created_at']),
            last_accessed=datetime.fromisoformat(row['last_accessed']),
            decay_rate=row['decay_rate'],
            reinforcement=row['reinforcement'],
            inferred=bool(row['inferred']),
            editable=bool(row['editable']),
            tags=json.loads(row['tags']) if row['tags'] else []
        )
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def close(self):
        """Close the database connection."""
        self.conn.close()
