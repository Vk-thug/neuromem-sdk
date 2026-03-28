"""
Memory relationship graph for NeuroMem.

Maintains explicit relationships between memories,
like Obsidian's knowledge graph but for AI agent memory.
Supports bidirectional links, BFS traversal, cluster detection,
and entity-based retrieval (HippoRAG-style).
"""

import re
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set
from neuromem.core.types import MemoryLink
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


# ── Lightweight entity extraction (no LLM, no spaCy dependency) ──
# Extracts proper nouns from text using capitalization heuristics.
# This runs during observe() so must be fast (<1ms).

_STOP_ENTITIES = {
    "I", "The", "A", "An", "My", "We", "Our", "He", "She", "They", "It",
    "This", "That", "What", "Who", "Where", "When", "How", "Why", "Do",
    "Does", "Did", "Is", "Are", "Was", "Were", "Has", "Have", "Had",
    "Can", "Could", "Would", "Should", "Will", "May", "Might",
    "Yes", "No", "Not", "Also", "But", "And", "Or", "If", "Then",
    "User", "Assistant", "Memory", "Session", "Unknown",
}

# Pattern: capitalized word not at sentence start, or two+ consecutive capitalized words
_PROPER_NOUN_RE = re.compile(
    r"(?<=[.!?\n] )([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"  # After sentence boundary
    r"|(?<=: )([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"        # After colon (Speaker: Name)
    r"|(?<=\] )([A-Z][a-z]+)"                            # After ] bracket
)


def extract_entities(text: str) -> List[str]:
    """
    Extract likely named entities from text using capitalization heuristics.

    Fast (<1ms), no dependencies. Finds proper nouns like person names,
    place names, and organization names.

    Returns deduplicated list of entity strings.
    """
    entities: Set[str] = set()

    # Strategy 1: Find capitalized words that aren't at absolute start of text
    # and aren't common stop words
    words = text.split()
    for i, word in enumerate(words):
        # Skip first word of text and words after sentence-ending punctuation
        clean = word.strip(",.!?:;\"'()[]")
        if not clean or len(clean) < 2:
            continue
        if clean[0].isupper() and clean not in _STOP_ENTITIES:
            # Check if previous word ended a sentence or is a delimiter
            if i > 0:
                prev = words[i - 1]
                # After sentence boundary, colon, or bracket — likely a name
                if prev.endswith((".", "!", "?", ":", "]", "\n")) or prev in ("Session", "User:", "Assistant:"):
                    entities.add(clean)
                # Two consecutive capitalized words — likely a name
                elif prev.strip(",.!?:;\"'()[]") not in _STOP_ENTITIES and prev[0:1].isupper():
                    # Merge multi-word name
                    prev_clean = prev.strip(",.!?:;\"'()[]")
                    if prev_clean and prev_clean[0].isupper():
                        entities.add(f"{prev_clean} {clean}")
                        entities.add(clean)  # Also add individual
                        entities.add(prev_clean)
                else:
                    # Mid-sentence capitalized word — strong signal for proper noun
                    entities.add(clean)

    # Strategy 2: Pattern-based extraction for "[Session N] Speaker:" format
    speaker_match = re.findall(r"\] ([A-Z][a-z]+):", text)
    for name in speaker_match:
        if name not in _STOP_ENTITIES:
            entities.add(name)

    # Remove any that are actually stop entities
    entities = {e for e in entities if e not in _STOP_ENTITIES and len(e) > 1}

    return list(entities)


class MemoryGraph:
    """
    Knowledge graph over memories.

    Tracks explicit relationships between memories:
    - derived_from: semantic memory created from episodic sources
    - contradicts: two memories conflict
    - reinforces: one memory strengthens another
    - related: similar content detected
    - supersedes: newer memory replaces older one
    """

    def __init__(self):
        # Forward adjacency: source_id -> [MemoryLink, ...]
        self._forward: Dict[str, List[MemoryLink]] = defaultdict(list)
        # Reverse adjacency: target_id -> [MemoryLink, ...]
        self._reverse: Dict[str, List[MemoryLink]] = defaultdict(list)
        # Entity index: entity_name (lowercased) -> set of memory IDs
        # Enables O(1) entity-to-memory lookup for graph-augmented retrieval
        self._entity_index: Dict[str, Set[str]] = defaultdict(set)

    def add_link(self, link: MemoryLink) -> None:
        """
        Add a link between two memories.

        Args:
            link: MemoryLink describing the relationship
        """
        # Prevent duplicate links
        for existing in self._forward[link.source_id]:
            if existing.target_id == link.target_id and existing.link_type == link.link_type:
                existing.strength = max(existing.strength, link.strength)
                return

        self._forward[link.source_id].append(link)
        self._reverse[link.target_id].append(link)

    def remove_link(self, source_id: str, target_id: str) -> bool:
        """Remove a specific link. Returns True if found and removed."""
        removed = False

        original = self._forward[source_id]
        self._forward[source_id] = [l for l in original if l.target_id != target_id]
        if len(self._forward[source_id]) < len(original):
            removed = True

        original_rev = self._reverse[target_id]
        self._reverse[target_id] = [l for l in original_rev if l.source_id != source_id]

        return removed

    def remove_all_links(self, memory_id: str) -> int:
        """Remove all links involving a memory (both directions). Returns count removed."""
        count = 0

        # Remove forward links from this memory
        if memory_id in self._forward:
            for link in self._forward[memory_id]:
                self._reverse[link.target_id] = [
                    l for l in self._reverse[link.target_id] if l.source_id != memory_id
                ]
                count += 1
            del self._forward[memory_id]

        # Remove reverse links to this memory
        if memory_id in self._reverse:
            for link in self._reverse[memory_id]:
                self._forward[link.source_id] = [
                    l for l in self._forward[link.source_id] if l.target_id != memory_id
                ]
                count += 1
            del self._reverse[memory_id]

        return count

    def get_links(self, memory_id: str, link_type: Optional[str] = None) -> List[MemoryLink]:
        """Get all outgoing links from a memory, optionally filtered by type."""
        links = list(self._forward.get(memory_id, []))
        if link_type:
            links = [l for l in links if l.link_type == link_type]
        return links

    def get_backlinks(self, memory_id: str, link_type: Optional[str] = None) -> List[MemoryLink]:
        """Get all incoming links to a memory (like Obsidian backlinks)."""
        links = list(self._reverse.get(memory_id, []))
        if link_type:
            links = [l for l in links if l.link_type == link_type]
        return links

    def get_related(self, memory_id: str, depth: int = 1) -> List[str]:
        """
        BFS traversal to find related memory IDs up to N hops.

        Like Obsidian's local graph view.

        Args:
            memory_id: Starting memory
            depth: Maximum traversal depth

        Returns:
            List of related memory IDs (excluding the starting memory)
        """
        visited: Set[str] = {memory_id}
        queue: deque = deque([(memory_id, 0)])
        related: List[str] = []

        while queue:
            current_id, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            # Traverse forward links
            for link in self._forward.get(current_id, []):
                if link.target_id not in visited:
                    visited.add(link.target_id)
                    related.append(link.target_id)
                    queue.append((link.target_id, current_depth + 1))

            # Traverse reverse links (bidirectional)
            for link in self._reverse.get(current_id, []):
                if link.source_id not in visited:
                    visited.add(link.source_id)
                    related.append(link.source_id)
                    queue.append((link.source_id, current_depth + 1))

        return related

    def get_clusters(self) -> List[List[str]]:
        """
        Find connected components (topic clusters) using Union-Find.

        Returns:
            List of clusters, each cluster is a list of memory IDs
        """
        # Collect all nodes
        all_nodes: Set[str] = set()
        for source_id, links in self._forward.items():
            all_nodes.add(source_id)
            for link in links:
                all_nodes.add(link.target_id)

        if not all_nodes:
            return []

        # Union-Find
        parent: Dict[str, str] = {n: n for n in all_nodes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for source_id, links in self._forward.items():
            for link in links:
                union(source_id, link.target_id)

        # Group by root
        clusters: Dict[str, List[str]] = defaultdict(list)
        for node in all_nodes:
            clusters[find(node)].append(node)

        return list(clusters.values())

    def get_bridge_memories(self) -> List[str]:
        """
        Find memories that connect otherwise disconnected clusters.

        These are high-value "bridge" memories that link different topics.
        Simple heuristic: memories with links to multiple clusters.
        """
        clusters = self.get_clusters()
        if len(clusters) <= 1:
            return []

        # Map each node to its cluster index
        node_cluster: Dict[str, int] = {}
        for idx, cluster in enumerate(clusters):
            for node_id in cluster:
                node_cluster[node_id] = idx

        bridges: List[str] = []
        for source_id, links in self._forward.items():
            connected_clusters = set()
            connected_clusters.add(node_cluster.get(source_id, -1))
            for link in links:
                connected_clusters.add(node_cluster.get(link.target_id, -1))
            if len(connected_clusters) > 1:
                bridges.append(source_id)

        return bridges

    # ----------------------------------------------------------------
    # ENTITY INDEX — HippoRAG-style entity-to-memory mapping
    # ----------------------------------------------------------------

    def register_entities(self, memory_id: str, entities: List[str]) -> None:
        """
        Register entities found in a memory.

        Called during observe() to build the entity index that powers
        graph-augmented retrieval.
        """
        for entity in entities:
            key = entity.lower().strip()
            if key:
                self._entity_index[key].add(memory_id)

    def find_memories_by_entity(self, entity: str) -> Set[str]:
        """Find all memory IDs associated with an entity."""
        return self._entity_index.get(entity.lower().strip(), set())

    def find_memories_by_entities(self, entities: List[str]) -> Dict[str, Set[str]]:
        """Find memories for multiple entities. Returns entity -> memory_ids mapping."""
        result: Dict[str, Set[str]] = {}
        for entity in entities:
            key = entity.lower().strip()
            if key and key in self._entity_index:
                result[key] = self._entity_index[key]
        return result

    def get_entity_connected_memories(
        self, query_entities: List[str], depth: int = 1, max_per_entity: int = 10
    ) -> List[str]:
        """
        Find memories connected to query entities via the entity index + graph traversal.

        This is the core of graph-augmented retrieval:
        1. Find memories directly mentioning query entities
        2. Traverse graph links from those memories to find related context

        Based on HippoRAG (Gutierrez et al., 2024): entity-based retrieval
        with graph expansion achieves 20% improvement on multi-hop QA.
        """
        direct_memories: Set[str] = set()
        for entity in query_entities:
            mem_ids = self.find_memories_by_entity(entity)
            direct_memories.update(list(mem_ids)[:max_per_entity])

        if not direct_memories:
            return []

        # Expand via graph traversal
        all_memories: Set[str] = set(direct_memories)
        if depth > 0:
            for mem_id in direct_memories:
                related = self.get_related(mem_id, depth=depth)
                all_memories.update(related)

        return list(all_memories)

    def export(self) -> Dict:
        """
        Export graph as {nodes: [...], edges: [...]}.

        Compatible with JSON Canvas-style format.
        """
        nodes: Set[str] = set()
        edges: List[dict] = []

        for source_id, links in self._forward.items():
            nodes.add(source_id)
            for link in links:
                nodes.add(link.target_id)
                edges.append(link.to_dict())

        return {
            "nodes": list(nodes),
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    @property
    def node_count(self) -> int:
        """Total unique nodes in the graph."""
        nodes: Set[str] = set()
        for source_id, links in self._forward.items():
            nodes.add(source_id)
            for link in links:
                nodes.add(link.target_id)
        return len(nodes)

    @property
    def edge_count(self) -> int:
        """Total edges in the graph."""
        return sum(len(links) for links in self._forward.values())
