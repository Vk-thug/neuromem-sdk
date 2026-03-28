"""
NeuroMem MCP Server -- exposes the brain-inspired memory system via Model Context Protocol.

Provides 12 tools, 3 resources, and 2 prompts for use by any MCP-compatible AI client.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP, Context

from neuromem.mcp.types import serialize_memory, serialize_memory_list
from neuromem.utils.logging import get_logger

logger = get_logger(__name__)

INSTRUCTIONS = (
    "NeuroMem is a brain-inspired memory system for AI agents. It stores memories across "
    "episodic (experiences), semantic (stable facts), and procedural (user preferences) layers. "
    "Memories naturally decay via Ebbinghaus forgetting curves and strengthen with reinforcement. "
    "Use the tools to store, search, retrieve, update, and manage memories. "
    "Use search_memories for semantic search and search_advanced for structured query syntax."
)


def _get_memory(ctx: Context) -> Any:
    """Extract the NeuroMem instance from the lifespan context."""
    return ctx.request_context.lifespan_context["memory"]


@asynccontextmanager
async def neuromem_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize NeuroMem on server start, cleanup on stop."""
    from neuromem import NeuroMem

    config_path = os.environ.get("NEUROMEM_CONFIG", "neuromem.yaml")
    user_id = os.environ.get("NEUROMEM_USER_ID", "default")

    logger.info(f"Starting NeuroMem MCP server (user={user_id}, config={config_path})")
    memory = NeuroMem.from_config(config_path, user_id)
    try:
        yield {"memory": memory, "user_id": user_id}
    finally:
        memory.close()
        logger.info("NeuroMem MCP server stopped")


def create_server() -> FastMCP:
    """Create and configure the NeuroMem MCP server."""
    mcp = FastMCP(
        "neuromem",
        instructions=INSTRUCTIONS,
        lifespan=neuromem_lifespan,
    )

    _register_tools(mcp)
    _register_resources(mcp)
    _register_prompts(mcp)

    return mcp


# ------------------------------------------------------------------
# TOOLS (12)
# ------------------------------------------------------------------


def _register_tools(mcp: FastMCP) -> None:
    """Register all 12 MCP tools."""

    @mcp.tool()
    async def store_memory(
        content: str,
        assistant_response: str = "Acknowledged",
        template: Optional[str] = None,
        ctx: Context = None,
    ) -> dict:
        """Store a memory from a user-assistant interaction.

        NeuroMem automatically detects memory type, extracts entities,
        and indexes for retrieval.

        Args:
            content: The user's input to remember.
            assistant_response: The assistant's response (default: "Acknowledged").
            template: Optional template name (decision/preference/fact/goal/feedback).
        """
        memory = _get_memory(ctx)
        try:
            await asyncio.to_thread(
                memory.observe,
                user_input=content,
                assistant_output=assistant_response,
                template=template,
            )
            return {"status": "stored", "turn_count": memory._turn_count}
        except Exception as e:
            logger.error(f"store_memory failed: {e}")
            return {"error": str(e), "tool": "store_memory"}

    @mcp.tool()
    async def search_memories(
        query: str,
        task_type: str = "chat",
        k: int = 8,
        ctx: Context = None,
    ) -> list:
        """Semantic search across all memory layers.

        Uses multi-hop query decomposition, graph-augmented retrieval,
        and brain-inspired ranking (similarity + salience + recency + reinforcement).

        Args:
            query: The search query.
            task_type: Type of task (chat, system_design, code_review, etc.).
            k: Number of results to return.
        """
        memory = _get_memory(ctx)
        try:
            results = await asyncio.to_thread(
                memory.retrieve, query=query, task_type=task_type, k=k
            )
            return serialize_memory_list(results)
        except Exception as e:
            logger.error(f"search_memories failed: {e}")
            return {"error": str(e), "tool": "search_memories"}

    @mcp.tool()
    async def search_advanced(
        query_string: str,
        k: int = 10,
        ctx: Context = None,
    ) -> list:
        """Advanced search with structured query syntax.

        Supports: type:semantic tag:preference confidence:>0.8
        after:2024-01-01 before:2024-12-31 'exact phrase'

        Args:
            query_string: Structured query string.
            k: Maximum number of results.
        """
        memory = _get_memory(ctx)
        try:
            results = await asyncio.to_thread(
                memory.search, query_string=query_string, k=k
            )
            return serialize_memory_list(results)
        except Exception as e:
            logger.error(f"search_advanced failed: {e}")
            return {"error": str(e), "tool": "search_advanced"}

    @mcp.tool()
    async def get_context(
        query: str,
        task_type: str = "chat",
        k: int = 8,
        ctx: Context = None,
    ) -> list:
        """Retrieve memories with automatic graph-based context expansion.

        Related memories are attached as expanded context
        (like Obsidian transclusion).

        Args:
            query: The search query.
            task_type: Type of task.
            k: Number of results.
        """
        memory = _get_memory(ctx)
        try:
            results = await asyncio.to_thread(
                memory.retrieve_with_context, query=query, task_type=task_type, k=k
            )
            return serialize_memory_list(results)
        except Exception as e:
            logger.error(f"get_context failed: {e}")
            return {"error": str(e), "tool": "get_context"}

    @mcp.tool()
    async def get_memory(memory_id: str, ctx: Context = None) -> dict:
        """Get a specific memory by its ID.

        Args:
            memory_id: The unique memory identifier.
        """
        mem = _get_memory(ctx)
        try:
            item = await asyncio.to_thread(
                mem.controller._find_memory_by_id, memory_id
            )
            if item is None:
                return {"error": f"Memory {memory_id} not found", "tool": "get_memory"}
            return serialize_memory(item)
        except Exception as e:
            logger.error(f"get_memory failed: {e}")
            return {"error": str(e), "tool": "get_memory"}

    @mcp.tool()
    async def list_memories(
        memory_type: Optional[str] = None,
        limit: int = 50,
        ctx: Context = None,
    ) -> list:
        """List all memories, optionally filtered by type.

        Args:
            memory_type: Filter by type (episodic/semantic/procedural). None for all.
            limit: Maximum number of memories to return.
        """
        memory = _get_memory(ctx)
        try:
            results = await asyncio.to_thread(
                memory.list, memory_type=memory_type, limit=limit
            )
            return serialize_memory_list(results)
        except Exception as e:
            logger.error(f"list_memories failed: {e}")
            return {"error": str(e), "tool": "list_memories"}

    @mcp.tool()
    async def update_memory(
        memory_id: str,
        content: str,
        ctx: Context = None,
    ) -> dict:
        """Update the content of an existing memory.

        Args:
            memory_id: ID of the memory to update.
            content: New content for the memory.
        """
        memory = _get_memory(ctx)
        try:
            await asyncio.to_thread(
                memory.update, memory_id=memory_id, content=content
            )
            return {"status": "updated", "memory_id": memory_id}
        except Exception as e:
            logger.error(f"update_memory failed: {e}")
            return {"error": str(e), "tool": "update_memory"}

    @mcp.tool()
    async def delete_memory(memory_id: str, ctx: Context = None) -> dict:
        """Permanently delete a memory.

        Args:
            memory_id: ID of the memory to delete.
        """
        memory = _get_memory(ctx)
        try:
            await asyncio.to_thread(memory.forget, memory_id=memory_id)
            return {"status": "deleted", "memory_id": memory_id}
        except Exception as e:
            logger.error(f"delete_memory failed: {e}")
            return {"error": str(e), "tool": "delete_memory"}

    @mcp.tool()
    async def consolidate(ctx: Context = None) -> dict:
        """Trigger memory consolidation.

        Promotes recurring episodic patterns into stable semantic knowledge,
        applies forgetting curves, and merges similar facts.
        """
        memory = _get_memory(ctx)
        try:
            await asyncio.to_thread(memory.consolidate)
            return {"status": "completed", "message": "Consolidation finished successfully."}
        except Exception as e:
            logger.error(f"consolidate failed: {e}")
            return {"error": str(e), "tool": "consolidate"}

    @mcp.tool()
    async def get_stats(ctx: Context = None) -> dict:
        """Get memory system statistics and health status.

        Returns total memory count, breakdown by type, user ID,
        and storage backend information.
        """
        memory = _get_memory(ctx)
        try:
            all_memories = await asyncio.to_thread(memory.list, limit=10000)
            by_type: Dict[str, int] = {"episodic": 0, "semantic": 0, "procedural": 0}
            for m in all_memories:
                mt = m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type)
                if mt in by_type:
                    by_type[mt] += 1

            storage_type = "unknown"
            try:
                storage_config = memory.config.storage()
                vs_config = storage_config.get("vector_store", {})
                storage_type = vs_config.get("type") or storage_config.get(
                    "database", {}
                ).get("type", "memory")
            except Exception:
                pass

            return {
                "total_memories": len(all_memories),
                "by_type": by_type,
                "user_id": memory.user_id,
                "storage_backend": storage_type,
            }
        except Exception as e:
            logger.error(f"get_stats failed: {e}")
            return {"error": str(e), "tool": "get_stats"}

    @mcp.tool()
    async def find_by_tags(
        tag_prefix: str,
        limit: int = 50,
        ctx: Context = None,
    ) -> list:
        """Find memories by hierarchical tag prefix.

        Examples: 'topic:ai' matches topic:ai, topic:ai/memory, etc.

        Args:
            tag_prefix: Tag prefix to match.
            limit: Maximum number of results.
        """
        memory = _get_memory(ctx)
        try:
            results = await asyncio.to_thread(
                memory.find_by_tags, tag_prefix=tag_prefix, limit=limit
            )
            return serialize_memory_list(results)
        except Exception as e:
            logger.error(f"find_by_tags failed: {e}")
            return {"error": str(e), "tool": "find_by_tags"}

    @mcp.tool()
    async def get_graph(ctx: Context = None) -> dict:
        """Export the memory relationship graph showing entities and their connections.

        Returns nodes (entities) and edges (relationships) as JSON.
        """
        memory = _get_memory(ctx)
        try:
            return await asyncio.to_thread(memory.get_graph)
        except Exception as e:
            logger.error(f"get_graph failed: {e}")
            return {"error": str(e), "tool": "get_graph"}


# ------------------------------------------------------------------
# RESOURCES (3)
# ------------------------------------------------------------------


def _register_resources(mcp: FastMCP) -> None:
    """Register all 3 MCP resources."""

    @mcp.resource("neuromem://memories/recent")
    async def recent_memories(ctx: Context = None) -> str:
        """Last 20 memories across all types."""
        memory = _get_memory(ctx)
        try:
            items = await asyncio.to_thread(memory.list, limit=20)
            if not items:
                return "No memories stored yet."
            lines = []
            for m in items:
                mt = m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type)
                ts = m.created_at.isoformat() if m.created_at else "unknown"
                lines.append(f"[{mt}] ({ts}) {m.content}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error retrieving recent memories: {e}"

    @mcp.resource("neuromem://memories/stats")
    async def memory_stats(ctx: Context = None) -> str:
        """Memory counts by type and total."""
        memory = _get_memory(ctx)
        try:
            all_memories = await asyncio.to_thread(memory.list, limit=10000)
            by_type: Dict[str, int] = {"episodic": 0, "semantic": 0, "procedural": 0}
            for m in all_memories:
                mt = m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type)
                if mt in by_type:
                    by_type[mt] += 1
            lines = [
                f"Total memories: {len(all_memories)}",
                f"User: {memory.user_id}",
                "",
                "By type:",
            ]
            for t, count in by_type.items():
                lines.append(f"  {t}: {count}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @mcp.resource("neuromem://config")
    async def config_resource(ctx: Context = None) -> str:
        """Current NeuroMem configuration summary."""
        memory = _get_memory(ctx)
        try:
            cfg = memory.config
            model_cfg = cfg.model()
            storage_cfg = cfg.storage()
            memory_cfg = cfg.memory()
            retrieval_cfg = cfg.retrieval()

            storage_type = "memory"
            vs = storage_cfg.get("vector_store", {})
            if vs.get("type"):
                storage_type = vs["type"]
            else:
                storage_type = storage_cfg.get("database", {}).get("type", "memory")

            lines = [
                "NeuroMem Configuration",
                "=" * 30,
                f"Embedding model: {model_cfg.get('embedding', 'unknown')}",
                f"Consolidation LLM: {model_cfg.get('consolidation_llm', 'unknown')}",
                f"Storage backend: {storage_type}",
                f"Decay enabled: {memory_cfg.get('decay_enabled', True)}",
                f"Consolidation interval: {memory_cfg.get('consolidation_interval', 10)} turns",
                f"Hybrid retrieval: {retrieval_cfg.get('hybrid_enabled', True)}",
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Error reading config: {e}"


# ------------------------------------------------------------------
# PROMPTS (2)
# ------------------------------------------------------------------


def _register_prompts(mcp: FastMCP) -> None:
    """Register all 2 MCP prompts."""

    @mcp.prompt()
    async def memory_context(query: str, ctx: Context = None) -> str:
        """Retrieve relevant memories and format them as context for the LLM.

        Args:
            query: The query to find relevant memories for.
        """
        memory = _get_memory(ctx)
        try:
            results = await asyncio.to_thread(memory.retrieve, query=query, k=8)
            if not results:
                return "No relevant memories found for this query."
            formatted = []
            for i, m in enumerate(results, 1):
                mt = m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type)
                formatted.append(f"{i}. [{mt}] {m.content}")
            memories_text = "\n".join(formatted)
            return (
                f"Based on stored memories:\n\n{memories_text}\n\n"
                "Use this context to inform your response."
            )
        except Exception as e:
            return f"Error retrieving memory context: {e}"

    @mcp.prompt()
    async def memory_summary(topic: Optional[str] = None, ctx: Context = None) -> str:
        """Provide a summary of the memory system or a specific topic.

        Args:
            topic: Optional topic to summarize. If None, provides overall summary.
        """
        memory = _get_memory(ctx)
        try:
            if topic:
                results = await asyncio.to_thread(memory.retrieve, query=topic, k=10)
                if not results:
                    return f"No memories found related to '{topic}'."
                lines = [f"Memory Summary for '{topic}'", "=" * 40, ""]
                for m in results:
                    mt = (
                        m.memory_type.value
                        if hasattr(m.memory_type, "value")
                        else str(m.memory_type)
                    )
                    lines.append(f"- [{mt}] {m.content}")
                return "\n".join(lines)
            else:
                all_memories = await asyncio.to_thread(memory.list, limit=10000)
                by_type: Dict[str, int] = {"episodic": 0, "semantic": 0, "procedural": 0}
                for m in all_memories:
                    mt = (
                        m.memory_type.value
                        if hasattr(m.memory_type, "value")
                        else str(m.memory_type)
                    )
                    if mt in by_type:
                        by_type[mt] += 1
                lines = [
                    "NeuroMem System Summary",
                    "=" * 40,
                    f"Total memories: {len(all_memories)}",
                    f"User: {memory.user_id}",
                    "",
                    "Breakdown:",
                    f"  Episodic (experiences): {by_type['episodic']}",
                    f"  Semantic (facts): {by_type['semantic']}",
                    f"  Procedural (preferences): {by_type['procedural']}",
                ]
                if all_memories:
                    recent = sorted(all_memories, key=lambda x: x.created_at, reverse=True)[:5]
                    lines.append("")
                    lines.append("Recent memories:")
                    for m in recent:
                        lines.append(f"  - {m.content[:80]}...")
                return "\n".join(lines)
        except Exception as e:
            return f"Error generating summary: {e}"
