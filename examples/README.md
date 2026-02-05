# NeuroMem SDK Examples

This directory contains example scripts demonstrating how to use NeuroMem with different LLM frameworks.

## Setup

### 1. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 2. Set API Keys

```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# For Google
export GOOGLE_API_KEY="..."
```

### 3. Install Dependencies

```bash
pip install -e .
pip install langchain-openai langchain-anthropic python-dotenv
```

## Examples

### 1. Demo Agent (Recommended)

**Full-featured agent using `create_agent` with tools and memory.**

```bash
# Run demo conversation
python examples/demo_agent.py

# Run interactive mode
python examples/demo_agent.py interactive
```

**Features:**
- ✅ Uses `ChatOpenAI` or `ChatAnthropic`
- ✅ LangChain's `create_agent` pattern
- ✅ Multiple tools (web search, weather, calculator)
- ✅ NeuroMem integration via `add_memory()`
- ✅ Interactive and demo modes

**Configuration:**
```bash
# Use OpenAI (default)
export LLM_PROVIDER="openai"
export MODEL_NAME="gpt-4o-mini"

# Use Anthropic
export LLM_PROVIDER="anthropic"
export MODEL_NAME="claude-3-5-sonnet-20241022"
```

---

### 2. LangChain Simple

**Basic LangChain integration (2 lines).**

```bash
python examples/langchain_simple.py
```

**Features:**
- Simple chain with memory
- LCEL-compatible
- Minimal setup

---

### 3. LangGraph Simple

**State-based agent with LangGraph (1 line).**

```bash
python examples/langgraph_simple.py
```

**Features:**
- Graph-based workflow
- State management
- Custom checkpointer

---

### 4. LiteLLM Simple

**Multi-provider support with LiteLLM (1 parameter).**

```bash
# Install LiteLLM first
pip install litellm

python examples/litellm_simple.py
```

**Features:**
- Works with 100+ providers
- Drop-in replacement
- Streaming support

---

## Example Output

### Demo Agent

```
🎯 NeuroMem + LangChain Agent Demo
======================================================================

🧠 Initializing NeuroMem for user: demo_user_001
🤖 Initializing openai model...
🔧 Creating agent with tools...
💾 Adding NeuroMem integration...

✅ Agent ready! Using openai

👤 User: Hi! My name is Alice and I love hiking.
🤖 Assistant: Hello Alice! It's great to meet you. Hiking is a wonderful hobby...

👤 User: What's the weather like in San Francisco?
🤖 Assistant: Let me check the weather for you...
[Tool: get_weather("San Francisco")]
The weather in San Francisco is currently sunny with a temperature of 72°F.

👤 User: Do you remember my name and what I like?
🤖 Assistant: Yes! Your name is Alice, and you mentioned that you love hiking...

📊 Memory Statistics
======================================================================
User ID: demo_user_001
Provider: openai
Async enabled: True
Observations queued: 3

✅ Demo completed!
```

---

## Comparison

| Example | Lines to Integrate | Use Case |
|---------|-------------------|----------|
| **demo_agent.py** | Full agent setup | Production-ready agent with tools |
| **langchain_simple.py** | 2 lines | Simple chat with memory |
| **langgraph_simple.py** | 1 line | State-based workflows |
| **litellm_simple.py** | 1 parameter | Multi-provider support |

---

## Troubleshooting

### Import Errors

```bash
# Make sure SDK is installed in dev mode
pip install -e .

# Install framework dependencies
pip install langchain-openai langchain-anthropic
```

### API Key Errors

```bash
# Check if keys are set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Set them if missing
export OPENAI_API_KEY="sk-..."
```

### Module Not Found

```bash
# Activate venv first!
source venv/bin/activate

# Then run examples
python examples/demo_agent.py
```

---

## Next Steps

1. **Try the demo agent**: `python examples/demo_agent.py`
2. **Run interactive mode**: `python examples/demo_agent.py interactive`
3. **Customize tools**: Edit `demo_agent.py` to add your own tools
4. **Switch providers**: Set `LLM_PROVIDER=anthropic`
5. **Build your app**: Use these examples as templates

---

## Documentation

- [NeuroMem SDK](../README.md)
- [Testing Guide](../TESTING.md)
- [Walkthrough](../walkthrough.md)
- [LangChain Agents](https://python.langchain.com/docs/how_to/agent_executor)

---

## Support

For issues or questions:
- Open an issue on GitHub
- Check the [walkthrough](../walkthrough.md)
- Review [TESTING.md](../TESTING.md)
