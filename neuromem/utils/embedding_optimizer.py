"""
Embedding optimization utilities for NeuroMem.

Reduces embedding storage through:
- Dimensionality reduction (PCA/UMAP)
- Quantization (float32 -> int8)
- Deduplication
- Clustering
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from sklearn.decomposition import PCA
import struct


class EmbeddingOptimizer:
    """
    Optimizes embedding storage to reduce memory footprint.
    
    Techniques:
    - Dimensionality reduction: 1536 dims -> 512 dims (67% reduction)
    - Quantization: float32 -> int8 (75% reduction)
    - Combined: ~90% storage reduction
    """
    
    def __init__(self, target_dims: int = 512):
        """
        Initialize embedding optimizer.
        
        Args:
            target_dims: Target dimensionality for reduction
        """
        self.target_dims = target_dims
        self.pca_model: Optional[PCA] = None
    
    def reduce_dimensions(
        self, 
        embeddings: List[List[float]],
        fit: bool = True
    ) -> List[List[float]]:
        """
        Reduce embedding dimensionality using PCA.
        
        Args:
            embeddings: List of embedding vectors
            fit: Whether to fit a new PCA model
        
        Returns:
            Reduced-dimension embeddings
        """
        if not embeddings:
            return []
        
        X = np.array(embeddings)
        
        if fit or self.pca_model is None:
            self.pca_model = PCA(n_components=self.target_dims)
            X_reduced = self.pca_model.fit_transform(X)
        else:
            X_reduced = self.pca_model.transform(X)
        
        return X_reduced.tolist()
    
    def quantize_embedding(
        self, 
        embedding: List[float],
        dtype: str = "int8"
    ) -> Tuple[bytes, float, float]:
        """
        Quantize embedding to reduce storage.
        
        Converts float32 to int8, storing scale and offset for reconstruction.
        
        Args:
            embedding: Original embedding vector
            dtype: Target data type ('int8' or 'uint8')
        
        Returns:
            Tuple of (quantized_bytes, scale, offset)
        """
        arr = np.array(embedding, dtype=np.float32)
        
        # Calculate scale and offset
        min_val = arr.min()
        max_val = arr.max()
        
        if dtype == "int8":
            # Map to [-128, 127]
            scale = (max_val - min_val) / 255.0
            offset = min_val
            quantized = np.round((arr - offset) / scale - 128).astype(np.int8)
        else:  # uint8
            # Map to [0, 255]
            scale = (max_val - min_val) / 255.0
            offset = min_val
            quantized = np.round((arr - offset) / scale).astype(np.uint8)
        
        return quantized.tobytes(), float(scale), float(offset)
    
    def dequantize_embedding(
        self,
        quantized_bytes: bytes,
        scale: float,
        offset: float,
        dtype: str = "int8"
    ) -> List[float]:
        """
        Reconstruct embedding from quantized representation.
        
        Args:
            quantized_bytes: Quantized embedding bytes
            scale: Scale factor
            offset: Offset value
            dtype: Original quantization type
        
        Returns:
            Reconstructed embedding vector
        """
        if dtype == "int8":
            quantized = np.frombuffer(quantized_bytes, dtype=np.int8)
            arr = (quantized.astype(np.float32) + 128) * scale + offset
        else:  # uint8
            quantized = np.frombuffer(quantized_bytes, dtype=np.uint8)
            arr = quantized.astype(np.float32) * scale + offset
        
        return arr.tolist()
    
    def find_similar_embeddings(
        self,
        embeddings: List[Tuple[str, List[float]]],
        similarity_threshold: float = 0.95
    ) -> List[List[str]]:
        """
        Find groups of similar embeddings for deduplication.
        
        Args:
            embeddings: List of (id, embedding) tuples
            similarity_threshold: Cosine similarity threshold
        
        Returns:
            List of groups of similar embedding IDs
        """
        if len(embeddings) < 2:
            return []
        
        # Convert to numpy array
        ids = [e[0] for e in embeddings]
        vectors = np.array([e[1] for e in embeddings])
        
        # Normalize vectors
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors_normalized = vectors / (norms + 1e-8)
        
        # Compute cosine similarity matrix
        similarity_matrix = np.dot(vectors_normalized, vectors_normalized.T)
        
        # Find similar pairs
        groups = []
        processed = set()
        
        for i in range(len(ids)):
            if ids[i] in processed:
                continue
            
            # Find all similar to i
            similar_indices = np.where(similarity_matrix[i] >= similarity_threshold)[0]
            similar_ids = [ids[j] for j in similar_indices if j != i]
            
            if similar_ids:
                group = [ids[i]] + similar_ids
                groups.append(group)
                processed.update(group)
        
        return groups
    
    def calculate_storage_savings(
        self,
        original_dims: int,
        target_dims: int,
        quantize: bool = True
    ) -> Dict[str, float]:
        """
        Calculate storage savings from optimization.
        
        Args:
            original_dims: Original embedding dimensions
            target_dims: Target dimensions after reduction
            quantize: Whether quantization is applied
        
        Returns:
            Dict with storage metrics
        """
        # Original size: float32 (4 bytes per dim)
        original_size = original_dims * 4
        
        # After dimensionality reduction
        reduced_size = target_dims * 4
        dim_reduction_pct = (1 - reduced_size / original_size) * 100
        
        # After quantization (int8 = 1 byte per dim)
        if quantize:
            quantized_size = target_dims * 1
            total_reduction_pct = (1 - quantized_size / original_size) * 100
        else:
            quantized_size = reduced_size
            total_reduction_pct = dim_reduction_pct
        
        return {
            "original_bytes": original_size,
            "optimized_bytes": quantized_size,
            "dim_reduction_pct": dim_reduction_pct,
            "total_reduction_pct": total_reduction_pct,
            "savings_ratio": original_size / quantized_size
        }
    
    def optimize_batch(
        self,
        embeddings: List[Tuple[str, List[float]]],
        reduce_dims: bool = True,
        quantize: bool = True,
        deduplicate: bool = True
    ) -> Dict[str, Any]:
        """
        Apply all optimizations to a batch of embeddings.
        
        Args:
            embeddings: List of (id, embedding) tuples
            reduce_dims: Apply dimensionality reduction
            quantize: Apply quantization
            deduplicate: Find and merge duplicates
        
        Returns:
            Optimization results
        """
        results = {
            "optimized_embeddings": [],
            "duplicate_groups": [],
            "stats": {}
        }
        
        ids = [e[0] for e in embeddings]
        vectors = [e[1] for e in embeddings]
        
        # Dimensionality reduction
        if reduce_dims:
            vectors = self.reduce_dimensions(vectors, fit=True)
        
        # Quantization
        if quantize:
            optimized = []
            for i, vec in enumerate(vectors):
                q_bytes, scale, offset = self.quantize_embedding(vec)
                optimized.append({
                    "id": ids[i],
                    "quantized_bytes": q_bytes,
                    "scale": scale,
                    "offset": offset,
                    "dimension": len(vec)
                })
            results["optimized_embeddings"] = optimized
        else:
            results["optimized_embeddings"] = [
                {"id": ids[i], "vector": vec}
                for i, vec in enumerate(vectors)
            ]
        
        # Deduplication
        if deduplicate:
            groups = self.find_similar_embeddings(list(zip(ids, vectors)))
            results["duplicate_groups"] = groups
        
        # Calculate savings
        original_dims = len(embeddings[0][1]) if embeddings else 1536
        target_dims = len(vectors[0]) if vectors else self.target_dims
        results["stats"] = self.calculate_storage_savings(
            original_dims, 
            target_dims, 
            quantize
        )
        
        return results
