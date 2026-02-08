# Quick Start: Demo Agent

## Run the Demo

```bash
# Activate venv
source venv/bin/activate

# Set API key
export OPENAI_API_KEY="sk-..."

# Run demo
python examples/demo_agent.py

# Run interactive mode
python examples/demo_agent.py interactive
```

## Features

✅ **LangChain's `create_agent`** - Production-ready pattern  
✅ **ChatOpenAI / ChatAnthropic** - Proper model initialization  
✅ **Multiple Tools** - Web search, weather, calculator  
✅ **NeuroMem Integration** - Automatic memory via `add_memory()`  
✅ **Interactive Mode** - Chat with the agent  

## Switch Providers

```bash
# Use OpenAI (default)
export LLM_PROVIDER="openai"
export MODEL_NAME="gpt-4o-mini"

# Use Anthropic
export LLM_PROVIDER="anthropic"
export MODEL_NAME="claude-3-5-sonnet-20241022"
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Code Structure

```python
# 1. Initialize NeuroMem
memory = NeuroMem.for_langchain(user_id="user_123")

# 2. Initialize chat model
model = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# 3. Create agent with tools
agent = create_agent(
    model=model,
    tools=[search_web, get_weather, calculate],
    system_prompt="You are a helpful assistant..."
)

# 4. Add memory (2 lines!)
agent_with_memory = add_memory(agent, memory)

# 5. Use it!
response = agent_with_memory.invoke({
    "messages": [HumanMessage(content="Hello!")]
})
```

## Customize

### Add Your Own Tools

```python
@tool
def my_custom_tool(param: str) -> str:
    """Description of what this tool does."""
    # Your logic here
    return f"Result: {param}"

# Add to tools list
tools = [search_web, get_weather, calculate, my_custom_tool]
```

### Change System Prompt

```python
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt="""You are a specialized assistant for...
    
    Your capabilities include:
    - Capability 1
    - Capability 2
    
    Always respond in a professional tone."""
)
```

## Output Example

```
🎯 NeuroMem + LangChain Agent Demo
======================================================================

🧠 Initializing NeuroMem for user: demo_user_001
🤖 Initializing openai model...
🔧 Creating agent with tools...
💾 Adding NeuroMem integration...

✅ Agent ready! Using openai

👤 User: Hi! My name is Charles and I love coding.
🤖 Assistant: Hi Charles! It's great to meet you. Coding is such a wonderful way...

👤 User: What's the weather like in london?
🤖 Assistant: The weather in London is sunny with a temperature of 72°F.

👤 User: Do you remember my name and what I like?
🤖 Assistant: Yes! Your name is Charles, and you mentioned that you love coding...

📊 Memory Statistics
======================================================================
User ID: demo_user_001
Provider: openai
Memory adapter active (async processing in background)

✅ Demo completed!
```

## Next Steps

1. ✅ Run the demo: `python examples/demo_agent.py`
2. ✅ Try interactive mode: `python examples/demo_agent.py interactive`
3. ✅ Add your own tools
4. ✅ Customize the system prompt
5. ✅ Switch to Anthropic: `export LLM_PROVIDER=anthropic`
6. ✅ Build your application!
