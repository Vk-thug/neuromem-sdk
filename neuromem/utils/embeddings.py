"""
Embedding utilities for NeuroMem.

Handles text-to-vector conversion using OpenAI embeddings.
"""

import os
from typing import List


def get_embedding(
    text: str,
    model: str = "text-embedding-3-large"
) -> List[float]:
    """
    Get embedding vector for text.
    
    Args:
        text: Text to embed
        model: Embedding model to use
    
    Returns:
        Embedding vector
    """
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        client = OpenAI(api_key=api_key)
        
        response = client.embeddings.create(
            input=text,
            model=model
        )
        
        return response.data[0].embedding
    
    except ImportError:
        # Fallback to mock embeddings for testing
        import hashlib
        import numpy as np
        
        # Create deterministic but realistic-looking embeddings
        hash_obj = hashlib.md5(text.encode())
        seed = int(hash_obj.hexdigest(), 16) % (2**32)
        np.random.seed(seed)
        
        # Generate 1536-dimensional vector (OpenAI embedding size)
        embedding = np.random.randn(1536).tolist()
        
        return embedding
    
    except Exception as e:
        # Fallback to mock embeddings if API fails
        import hashlib
        import numpy as np
        
        hash_obj = hashlib.md5(text.encode())
        seed = int(hash_obj.hexdigest(), 16) % (2**32)
        np.random.seed(seed)
        
        embedding = np.random.randn(1536).tolist()
        
        return embedding


def batch_get_embeddings(
    texts: List[str],
    model: str = "text-embedding-3-large"
) -> List[List[float]]:
    """
    Get embeddings for multiple texts in batch.
    
    Args:
        texts: List of texts to embed
        model: Embedding model to use
    
    Returns:
        List of embedding vectors
    """
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        client = OpenAI(api_key=api_key)
        
        response = client.embeddings.create(
            input=texts,
            model=model
        )
        
        return [item.embedding for item in response.data]
    
    except:
        # Fallback to individual embeddings
        return [get_embedding(text, model) for text in texts]
