"""
Demo Agent using LangChain's create_agent with NeuroMem integration.

This example demonstrates:
1. Using ChatOpenAI/ChatAnthropic for LLM initialization
2. Creating an agent with create_agent
3. Integrating NeuroMem for memory management
4. Tool calling and conversation flow
"""

import os
from typing import Annotated
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.messages import HumanMessage, AIMessage

# NeuroMem imports
from neuromem import NeuroMem
from neuromem.adapters.langchain import add_memory

# Load environment variables from .env file
load_dotenv()

# Load environment variables
load_dotenv()


# ============================================================================
# Define Tools
# ============================================================================

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    # Simulated web search
    return f"Search results for '{query}': Found relevant information about {query}."


@tool
def get_weather(location: str) -> str:
    """Get current weather for a location."""
    # Simulated weather API
    return f"Weather in {location}: Sunny, 72°F"


@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error calculating: {str(e)}"


# ============================================================================
# Initialize Models
# ============================================================================

def get_chat_model(provider: str = "openai", model_name: str = None):
    """
    Initialize chat model based on provider.
    
    Args:
        provider: "openai" or "anthropic"
        model_name: Specific model name (optional)
    
    Returns:
        Initialized chat model
    """
    if provider == "openai":
        return ChatOpenAI(
            model=model_name or "gpt-4o-mini",
            temperature=0.7,
            max_tokens=1000,
            timeout=30,
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=model_name or "claude-3-5-sonnet-20241022",
            temperature=0.7,
            max_tokens=1000,
            timeout=30,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


# ============================================================================
# Create Agent with NeuroMem
# ============================================================================

def create_demo_agent(
    user_id: str,
    provider: str = "openai",
    model_name: str = None
):
    """
    Create an agent with NeuroMem memory integration.
    
    Args:
        user_id: User identifier for memory
        provider: LLM provider ("openai" or "anthropic")
        model_name: Specific model name
    
    Returns:
        Agent with memory
    """
    # 1. Create or get user (required for Postgres UUID constraint)
    from neuromem.user import UserManager, User
    
    print(f"👤 Creating/getting user: {user_id}")
    
    # Use a hardcoded UUID to ensure memory persistence across runs
    # This is necessary because UserManager is ephemeral (in-memory only)
    # Valid UUID v4 constant
    HARDCODED_UUID = "497f6eca-6276-4993-bfeb-53cbbbba6f08"
    
    user = User(
        user_id=HARDCODED_UUID,
        external_id=user_id,
        metadata={"name": user_id}
    )
    
    # Inject into UserManager cache just in case other components check it
    # accessing private members as a pragmatic workaround for the demo
    UserManager._users[HARDCODED_UUID] = user
    UserManager._external_id_index[user_id] = HARDCODED_UUID
    
    print(f"   ✅ Using Hardcoded User ID: {user.id}")
    
    # 2. Initialize NeuroMem with config from examples directory
    print(f"🧠 Initializing NeuroMem for user: {user.id}")
    import os
    config_path = os.path.join(os.path.dirname(__file__), "neuromem.yaml")
    memory = NeuroMem.from_config(config_path, user_id=user.id)
    
    # 2. Initialize chat model
    print(f"🤖 Initializing {provider} model...")
    model = get_chat_model(provider, model_name)
    
    # 3. Define tools
    tools = [search_web, get_weather, calculate]
    
    # 4. Create agent with create_agent
    print("🔧 Creating agent with tools...")
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt="""You are a helpful AI assistant with specific knowledge about the user.

### Instructions
1. You have access to facts about the user from previous conversations (provided in the conversation history). Use this information to personalize your responses.
2. If the user asks about themselves (e.g., "What is my name?"), check the history for context FIRST.
3. If the answer is in the conversation context, state it confidently.
4. Use tools for external information (weather, search, math).
5. Be concise, natural, and helpful.
"""
    )
    
    # 5. Add memory to the agent
    print("💾 Adding NeuroMem integration...")
    agent_with_memory = add_memory(agent, memory)
    
    return agent_with_memory, memory


# ============================================================================
# Demo Conversation
# ============================================================================

def run_demo_conversation():
    """Run a demo conversation with the agent."""
    
    print("\n" + "="*70)
    print("🎯 NeuroMem + LangChain Agent Demo")
    print("="*70 + "\n")
    
    # Choose provider (can be configured via env var)
    provider = os.getenv("LLM_PROVIDER", "openai")
    model_name = os.getenv("MODEL_NAME", None)
    user_id = "demo_user_001"
    
    # Create agent
    agent, memory = create_demo_agent(
        user_id=user_id,
        provider=provider,
        model_name=model_name
    )
    
    print(f"\n✅ Agent ready! Using {provider}\n")
    
    # Conversation 1: Introduction
    print("👤 User: Hi! My name is Alice and I love hiking.")
    print("🤖 Assistant: ", end="", flush=True)
    
    response1 = agent.invoke({
        "messages": [HumanMessage(content="Hi! My name is Alice and I love hiking.")]
    })
    
    print(response1["messages"][-1].content)
    
    # Conversation 2: Ask about weather
    print("\n👤 User: What's the weather like in San Francisco?")
    print("🤖 Assistant: ", end="", flush=True)
    
    response2 = agent.invoke({
        "messages": [HumanMessage(content="What's the weather like in San Francisco?")]
    })
    
    print(response2["messages"][-1].content)
    
    # Conversation 3: Test memory recall
    print("\n👤 User: Do you remember my name and what I like?")
    print("🤖 Assistant: ", end="", flush=True)
    
    response3 = agent.invoke({
        "messages": [HumanMessage(content="Do you remember my name and what I like?")]
    })
    
    print(response3["messages"][-1].content)
    
    # Conversation 4: Use calculation tool
    print("\n👤 User: Can you calculate 15 * 24 + 100?")
    print("🤖 Assistant: ", end="", flush=True)
    
    response4 = agent.invoke({
        "messages": [HumanMessage(content="Can you calculate 15 * 24 + 100?")]
    })
    
    print(response4["messages"][-1].content)
    
    
    # Wait for async workers to process
    print("\n⏳ Waiting for async workers to persist memories (3 seconds)...")
    import time
    time.sleep(3)
    
    # Show memory stats
    print("\n" + "="*70)
    print("📊 Memory Statistics")
    print("="*70)
    # Get user_id from memory's episodic backend
    if hasattr(memory, 'controller') and hasattr(memory.controller, 'episodic'):
        user_id_display = memory.controller.episodic.user_id if hasattr(memory.controller.episodic, 'user_id') else "N/A"
    else:
        user_id_display = "N/A"
    
    print(f"User ID: {user_id_display}")
    print(f"Provider: {provider}")
    
    # Note: memory here is the NeuroMem instance returned from create_demo_agent
    if hasattr(memory, 'controller'):
        print(f"Async enabled: {memory.controller.async_enabled}")
        if memory.controller.metrics:
            queued = memory.controller.metrics.counters.get('observe.queued', 0)
            created_count = 0
            # Count all memory.created metrics
            for key, value in memory.controller.metrics.counters.items():
                if 'memory.created' in key:
                    created_count += value
            print(f"Observations queued: {queued}")
            print(f"Memories created: {created_count}")
    else:
        print("Memory adapter active (async processing in background)")
    
    print("\n✅ Demo completed!")


# ============================================================================
# Interactive Mode
# ============================================================================

def run_interactive_mode():
    """Run the agent in interactive mode."""
    
    print("\n" + "="*70)
    print("🎯 NeuroMem + LangChain Agent - Interactive Mode")
    print("="*70 + "\n")
    
    # Setup
    provider = os.getenv("LLM_PROVIDER", "openai")
    model_name = os.getenv("MODEL_NAME", None)
    user_id = input("Enter your user ID (or press Enter for 'demo_user'): ").strip() or "demo_user"
    
    # Create agent
    agent, memory = create_demo_agent(
        user_id=user_id,
        provider=provider,
        model_name=model_name
    )
    
    print(f"\n✅ Agent ready! Using {provider}")
    print("Type 'quit' or 'exit' to end the conversation.\n")
    
    # Conversation loop
    while True:
        try:
            user_input = input("👤 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Goodbye!")
                break
            
            print("🤖 Assistant: ", end="", flush=True)
            
            response = agent.invoke({
                "messages": [HumanMessage(content=user_input)]
            })
            
            print(response["messages"][-1].content)
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Check for required API keys
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Error: Please set OPENAI_API_KEY or ANTHROPIC_API_KEY")
        print("\nExample:")
        print("  export OPENAI_API_KEY='sk-...'")
        print("  export LLM_PROVIDER='openai'")
        sys.exit(1)
    
    # Run mode
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    
    if mode == "interactive":
        run_interactive_mode()
    else:
        run_demo_conversation()
