import os
import sys
import yaml
import json
from qdrant_client import QdrantClient
from qdrant_client.http import models
import psycopg2
from psycopg2.extras import RealDictCursor

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "neuromem.yaml")
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def inspect_qdrant(config):
    print("\n" + "="*50)
    print("INSPECTION: QDRANT VECTOR STORE")
    print("="*50)
    try:
        q_config = config['neuromem']['storage']['vector_store']['config']
        path = q_config.get('path')
        collection_name = q_config.get('collection_name')
        
        if path:
            client = QdrantClient(path=path)
            print(f"✅ Connected to local Qdrant at: {path}")
        else:
            print("⚠️  Using non-local Qdrant (skipping detailed inspection for simplicity)")
            return

        # Check collection
        collections = client.get_collections().collections
        found = any(c.name == collection_name for c in collections)
        
        if not found:
            print(f"❌ Collection '{collection_name}' not found.")
            return
            
        info = client.get_collection(collection_name)
        print(f"ℹ️  Collection: {collection_name}")
        print(f"📊 Points count: {info.points_count}")
        print(f"   Status: {info.status}")

        # List recent items
        print("\n[Recent Memories]")
        result = client.scroll(
            collection_name=collection_name,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        points = result[0]
        
        if not points:
            print("   (No memories found)")
        
        for p in points:
            payload = p.payload
            m_type = payload.get('memory_type', 'UNKNOWN')
            content = payload.get('content', '')
            # Truncate content for display
            display_content = (content[:75] + '..') if len(content) > 75 else content
            print(f"   • [{m_type.upper()}] {display_content}")
            
    except Exception as e:
        print(f"❌ Failed to inspect Qdrant: {e}")

def inspect_postgres(config):
    print("\n" + "="*50)
    print("INSPECTION: POSTGRESQL HISTORY STORE")
    print("="*50)
    try:
        p_config = config['neuromem']['storage']['history_store']['config']
        url = p_config.get('url')
        
        if not url:
            print("⚠️  No PostgreSQL URL configured.")
            return
            
        print(f"Connecting to Postgres...")
        # Mask password for display
        safe_url = url.split('@')[1] if '@' in url else '...'
        print(f"Target: ...@{safe_url}")
        
        conn = psycopg2.connect(url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print(f"✅ Connected successfully.")
        
        # List tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()
        table_names = [t['table_name'] for t in tables]
        
        if not table_names:
            print("⚠️  No tables found in public schema.")
            print("   (This is expected if SessionMemory is running in-memory mode and not writing to DB)")
        else:
            print(f"found tables: {table_names}")
            # If we had a table, we'd query it here.
        
        conn.close()

    except Exception as e:
        print(f"❌ Failed to inspect PostgreSQL: {e}")

if __name__ == "__main__":
    try:
        c = load_config()
        inspect_qdrant(c)
        inspect_postgres(c)
    except Exception as e:
        print(f"Error loading config or script: {e}")
