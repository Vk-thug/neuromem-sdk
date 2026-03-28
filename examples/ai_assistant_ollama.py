#!/usr/bin/env python3
"""
NeuroMem AI Assistant — Real conversation with Ollama + Qdrant + LangChain.

This example builds a real AI assistant that:
1. Uses Ollama (qwen2.5-coder:7b) for chat
2. Uses Ollama (nomic-embed-text) for embeddings
3. Uses Qdrant (localhost:6333) for vector storage
4. Uses NeuroMem for brain-inspired memory (episodic, semantic, procedural)
5. Tests memory across simulated multi-day conversations

Requirements:
    ollama pull qwen2.5-coder:7b
    ollama pull nomic-embed-text
    docker run -p 6333:6333 qdrant/qdrant
    pip install neuromem-sdk[qdrant] langchain-ollama langchain langgraph

Usage:
    python examples/ai_assistant_ollama.py           # Run full validation
    python examples/ai_assistant_ollama.py --chat     # Interactive chat mode
"""

import os
import sys
import uuid
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neuromem import NeuroMem
from neuromem.config import NeuroMemConfig
from neuromem.adapters.langgraph import with_memory

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Annotated, List
from typing_extensions import TypedDict


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

OLLAMA_CHAT_MODEL = "qwen2.5-coder:7b"
OLLAMA_EMBED_MODEL = "nomic-embed-text"
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "neuromem"
USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def create_neuromem() -> NeuroMem:
    """Create NeuroMem with Qdrant backend and Ollama embeddings."""
    import tempfile

    config_yaml = f"""
neuromem:
  model:
    embedding: {OLLAMA_EMBED_MODEL}
    consolidation_llm: gpt-4o-mini
  storage:
    vector_store:
      type: qdrant
      url: "{QDRANT_URL}"
      collection_name: "{QDRANT_COLLECTION}"
      vector_size: 768
  memory:
    decay_enabled: false
    consolidation_interval: 100
  async:
    enabled: false
  retrieval:
    hybrid_enabled: false
"""
    config_path = os.path.join(tempfile.gettempdir(), "neuromem_ollama.yaml")
    with open(config_path, "w") as f:
        f.write(config_yaml)

    return NeuroMem.from_config(config_path, user_id=USER_ID)


def create_agent_graph(llm: ChatOllama, memory: NeuroMem):
    """Create a LangGraph agent with NeuroMem memory."""

    def agent_node(state: dict) -> dict:
        """Agent node: builds prompt with memory context and calls LLM."""
        messages = state.get("messages", [])
        context = state.get("context", [])

        # Get the current user message
        user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

        # Build the prompt with memory context baked directly into the user message
        if context:
            ctx_text = "\n".join([f"- {c}" for c in context[:8]])
            augmented_user_msg = (
                f"[MEMORY CONTEXT - these are facts from our past conversations, use them to answer]\n"
                f"{ctx_text}\n"
                f"[END MEMORY CONTEXT]\n\n"
                f"User question: {user_msg}"
            )
        else:
            augmented_user_msg = user_msg

        llm_messages = [
            SystemMessage(content=(
                "You are a helpful AI assistant with persistent memory. "
                "When MEMORY CONTEXT is provided, you MUST use those facts to answer. "
                "Never say you don't have personal information if memory context is present."
            )),
            HumanMessage(content=augmented_user_msg),
        ]

        response = llm.invoke(llm_messages)

        return {"messages": [response]}

    # State schema with context field
    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]
        context: List[str]

    # Build graph
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)

    graph = builder.compile()

    # Wrap with NeuroMem
    return with_memory(graph, memory, k=8)


def chat_once(agent, user_input: str) -> str:
    """Send one message and get response."""
    result = agent.invoke({"messages": [HumanMessage(content=user_input)], "context": []})
    # Extract last AI message
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return str(result)


def stream_chat(agent, user_input: str) -> str:
    """Stream one message and print tokens in real-time."""
    collected = []
    for chunk in agent.stream(
        {"messages": [HumanMessage(content=user_input)], "context": []},
        stream_mode="messages",
    ):
        if isinstance(chunk, tuple) and len(chunk) == 2:
            msg, metadata = chunk
            if hasattr(msg, "content") and msg.content:
                print(msg.content, end="", flush=True)
                collected.append(msg.content)
    print()
    return "".join(collected)


# ─────────────────────────────────────────────
# Validation: Multi-day conversation simulation
# ─────────────────────────────────────────────

def run_validation():
    """
    Simulate a multi-week conversation to validate long-term memory.

    Week 1: Personal introduction, background, preferences
    Week 2: Project NeuroMem — architecture, decisions, challenges
    Week 3: Project MegaAuth — second project, different stack
    Week 4: Team, process, opinions, debugging sessions
    Week 5: Cross-referencing recall — test memory across all weeks
    Week 6: Deep recall — subtle details, streaming summary
    """
    print("=" * 70)
    print("  NeuroMem Memory Validation — Multi-Week Deep Conversation")
    print("=" * 70)
    print(f"  Chat Model:  {OLLAMA_CHAT_MODEL}")
    print(f"  Embed Model: {OLLAMA_EMBED_MODEL}")
    print(f"  Qdrant:      {QDRANT_URL}")
    print(f"  User ID:     {USER_ID}")
    print("=" * 70)

    memory = create_neuromem()
    llm = ChatOllama(model=OLLAMA_CHAT_MODEL, temperature=0.3)
    agent = create_agent_graph(llm, memory)

    # ────────────────────────────────────────────
    # WEEK 1: Personal introduction
    # ────────────────────────────────────────────
    print("\n📅 WEEK 1 — Personal introduction\n")
    week1 = [
        "Hi! My name is Vikram Venkatesh Kumar. I'm 28 years old.",
        "I work as a senior software engineer at a company called Megadot Services.",
        "I'm based in Chennai, India. I've been living here for 5 years now.",
        "I primarily code in Python and TypeScript. Python for backend and AI, TypeScript for frontend.",
        "I've been coding professionally for about 8 years. Started with Java in college.",
        "My favorite editor is VS Code with the Dracula theme. I always use dark mode.",
        "I'm a morning person. I usually start coding at 6 AM before the office gets busy.",
    ]
    for msg in week1:
        print(f"  👤 {msg}")
        r = chat_once(agent, msg)
        print(f"  🤖 {r[:120]}...\n")

    # ────────────────────────────────────────────
    # WEEK 2: Project NeuroMem
    # ────────────────────────────────────────────
    print("\n📅 WEEK 2 — Project NeuroMem details\n")
    week2 = [
        "I'm building a project called NeuroMem. It's an AI memory SDK for LLM agents.",
        "NeuroMem is inspired by how the human brain works — episodic, semantic, and procedural memory layers.",
        "For NeuroMem's storage, we chose Qdrant as our vector database. It handles cosine similarity really well.",
        "We're using nomic-embed-text for embeddings. It's 768-dimensional and runs locally via Ollama.",
        "The SDK integrates with LangChain and LangGraph. I wrote custom adapters for both frameworks.",
        "One of the hardest challenges was implementing the memory consolidation system. It uses an LLM to extract facts from episodic memories and promote them to semantic memory.",
        "We just released version 0.2.0 of NeuroMem with Inngest workflow support for cron-based consolidation.",
    ]
    for msg in week2:
        print(f"  👤 {msg}")
        r = chat_once(agent, msg)
        print(f"  🤖 {r[:120]}...\n")

    # ────────────────────────────────────────────
    # WEEK 3: Project MegaAuth
    # ────────────────────────────────────────────
    print("\n📅 WEEK 3 — Project MegaAuth (second project)\n")
    week3 = [
        "I'm also working on another project at Megadot called MegaAuth. It's an authentication microservice.",
        "MegaAuth is built with FastAPI and uses Redis for session management.",
        "We chose JWT tokens with refresh token rotation for MegaAuth's auth flow.",
        "MegaAuth handles about 50,000 requests per day in production. We deploy it on AWS ECS.",
        "The MegaAuth database is PostgreSQL. I always prefer PostgreSQL for relational data.",
        "My colleague Arjun is the tech lead on MegaAuth. He's really good with infrastructure and DevOps.",
    ]
    for msg in week3:
        print(f"  👤 {msg}")
        r = chat_once(agent, msg)
        print(f"  🤖 {r[:120]}...\n")

    # ────────────────────────────────────────────
    # WEEK 4: Team, process, opinions
    # ────────────────────────────────────────────
    print("\n📅 WEEK 4 — Team, process, and debugging\n")
    week4 = [
        "My team has 6 people. Besides me and Arjun, there's Priya who handles frontend with React and Next.js.",
        "We follow Git flow for branching. Every PR needs at least two approvals before merging.",
        "Our CI/CD pipeline uses GitHub Actions. We run pytest for Python and Vitest for TypeScript tests.",
        "I had a tough debugging session yesterday. There was a race condition in the NeuroMem worker threads.",
        "The fix was switching from threading.Thread to Inngest durable workflows for the background tasks.",
        "I strongly prefer composition over inheritance in my code. I think deep class hierarchies are an anti-pattern.",
        "For monitoring, we use Grafana dashboards with Prometheus metrics. My Grafana is always in dark mode.",
    ]
    for msg in week4:
        print(f"  👤 {msg}")
        r = chat_once(agent, msg)
        print(f"  🤖 {r[:120]}...\n")

    # ────────────────────────────────────────────
    # WEEK 5: Cross-referencing recall
    # ────────────────────────────────────────────
    print("\n📅 WEEK 5 — Memory recall test (cross-referencing)\n")

    recall_questions = [
        # Personal facts
        ("What is my full name?", ["vikram"]),
        ("How old am I?", ["28"]),
        ("Where do I live?", ["chennai"]),
        ("What company do I work at?", ["megadot"]),
        ("What is my job title?", ["senior", "software engineer"]),
        # Coding preferences
        ("What programming languages do I use?", ["python", "typescript"]),
        ("What editor and theme do I use?", ["vs code", "dracula"]),
        ("Do I prefer dark mode or light mode?", ["dark"]),
        ("What time do I usually start coding?", ["6", "morning"]),
        # Project NeuroMem
        ("What is NeuroMem?", ["memory", "sdk"]),
        ("What vector database does NeuroMem use?", ["qdrant"]),
        ("What embedding model does NeuroMem use?", ["nomic"]),
        ("What frameworks does NeuroMem integrate with?", ["langchain", "langgraph"]),
        ("What version of NeuroMem did we release?", ["0.2"]),
        # Project MegaAuth
        ("What is MegaAuth?", ["auth"]),
        ("What framework is MegaAuth built with?", ["fastapi"]),
        ("What does MegaAuth use for sessions?", ["redis"]),
        ("How many requests does MegaAuth handle daily?", ["50"]),
        ("Where is MegaAuth deployed?", ["aws", "ecs"]),
        # Team
        ("Who is Arjun?", ["tech lead", "megaauth"]),
        ("What does Priya do?", ["frontend", "react"]),
        ("How many people are on my team?", ["6", "six"]),
        # Process
        ("What branching strategy does my team use?", ["git flow"]),
        ("What CI/CD tool do we use?", ["github actions"]),
        # Opinions
        ("What is my preference about database choice?", ["postgres"]),
    ]

    recall_score = 0
    total_checks = len(recall_questions)

    for question, expected_keywords in recall_questions:
        print(f"  👤 {question}")
        response = chat_once(agent, question)
        response_short = response[:150].replace("\n", " ")
        print(f"  🤖 {response_short}...")

        response_lower = response.lower()
        found = [kw for kw in expected_keywords if kw in response_lower]
        if found:
            recall_score += 1
            print(f"     ✅ Recalled: {found}\n")
        else:
            print(f"     ❌ Expected any of: {expected_keywords}\n")

    # ────────────────────────────────────────────
    # WEEK 6: Streaming summary
    # ────────────────────────────────────────────
    print("\n📅 WEEK 6 — Streaming deep summary\n")

    print("  👤 Give me a detailed summary of everything you know about me — my background,")
    print("     projects, team, preferences, and technical decisions.")
    print("  🤖 ", end="")
    summary = stream_chat(
        agent,
        "Give me a detailed summary of everything you know about me — "
        "my background, projects, team, preferences, and technical decisions."
    )

    # ────────────────────────────────────────────
    # Memory statistics
    # ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  📊 Memory Statistics")
    print("=" * 70)

    all_memories = memory.list(limit=200)
    episodic = memory.list(memory_type="episodic", limit=200)
    semantic = memory.list(memory_type="semantic", limit=200)
    procedural = memory.list(memory_type="procedural", limit=200)
    print(f"  Total memories:   {len(all_memories)}")
    print(f"  Episodic:         {len(episodic)}")
    print(f"  Semantic:         {len(semantic)}")
    print(f"  Procedural:       {len(procedural)}")

    tags = memory.get_tag_tree()
    if tags:
        top_tags = dict(sorted(tags.items(), key=lambda x: x[1], reverse=True)[:8])
        print(f"  Top tags:         {top_tags}")

    graph_export = memory.get_graph()
    print(f"  Graph nodes:      {graph_export['node_count']}")
    print(f"  Graph edges:      {graph_export['edge_count']}")

    summary_data = memory.daily_summary()
    print(f"  Today's summary:  {summary_data['memory_count']} memories")

    # Qdrant verification
    print("\n" + "=" * 70)
    print("  📊 Qdrant Verification")
    print("=" * 70)

    import requests
    r = requests.get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
    info = r.json()["result"]
    print(f"  Collection:       {QDRANT_COLLECTION}")
    print(f"  Points count:     {info['points_count']}")
    print(f"  Vector size:      {info['config']['params']['vectors']['size']}")

    # Search validation
    print("\n" + "=" * 70)
    print("  📊 Search Validation")
    print("=" * 70)

    for query in ["NeuroMem architecture", "MegaAuth deployment", "team members", "debugging"]:
        results = memory.retrieve(query)
        print(f"  retrieve(\"{query}\"): {len(results)} results")
        if results:
            print(f"    top: {results[0].content[:70]}...")

    # Final score
    print("\n" + "=" * 70)
    pct = recall_score / total_checks * 100
    print(f"  🏆 RECALL SCORE: {recall_score}/{total_checks} ({pct:.0f}%)")
    print("=" * 70)

    if pct >= 80:
        print("  ✅ EXCELLENT — Memory system working at human-like recall")
    elif pct >= 60:
        print("  ✅ GOOD — Memory system working with some gaps")
    elif pct >= 40:
        print("  ⚠️  FAIR — Memory retrieval needs tuning")
    else:
        print("  ❌ POOR — Memory retrieval not working correctly")

    memory.close()


# ─────────────────────────────────────────────
# Interactive chat mode
# ─────────────────────────────────────────────

def run_interactive():
    """Interactive chat with persistent memory."""
    print("=" * 60)
    print("NeuroMem AI Assistant — Interactive Mode")
    print("=" * 60)
    print(f"Chat: {OLLAMA_CHAT_MODEL}  |  Embed: {OLLAMA_EMBED_MODEL}")
    print("Commands: /memories /search <query> /graph /quit")
    print("=" * 60)

    memory = create_neuromem()
    llm = ChatOllama(model=OLLAMA_CHAT_MODEL, temperature=0.3)
    agent = create_agent_graph(llm, memory)

    while True:
        try:
            user_input = input("\n👤 ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue

        if user_input == "/quit":
            break
        elif user_input == "/memories":
            mems = memory.list(limit=20)
            print(f"\n📦 {len(mems)} memories:")
            for m in mems[:10]:
                print(f"  [{m.memory_type.value:10s}] {m.content[:60]}...")
            continue
        elif user_input.startswith("/search "):
            query = user_input[8:]
            results = memory.search(query)
            print(f"\n🔍 {len(results)} results for '{query}':")
            for r in results[:5]:
                print(f"  [{r.memory_type.value}] {r.content[:60]}...")
            continue
        elif user_input == "/graph":
            g = memory.get_graph()
            print(f"\n🕸️ Graph: {g['node_count']} nodes, {g['edge_count']} edges")
            continue

        print("🤖 ", end="")
        stream_chat(agent, user_input)

    print("\nGoodbye!")
    memory.close()


if __name__ == "__main__":
    if "--chat" in sys.argv:
        run_interactive()
    else:
        run_validation()
