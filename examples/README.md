# NeuroMem SDK Examples

This directory contains examples demonstrating different use cases and integration patterns for the NeuroMem SDK.

## 📁 Examples

### 1. `basic_usage.py`
Basic examples covering core functionality:
- User creation
- Memory operations (observe, retrieve, list)
- LangChain integration
- Memory control (explain, update, forget)
- Memory consolidation

**Run:**
```bash
python examples/basic_usage.py
```

### 2. `demo_agent.py`
Production-ready LangGraph agent with:
- Real LangGraph StateGraph
- OpenAI LLM integration (with fallback)
- Memory retrieval and storage
- Automatic consolidation
- Memory explanation

**Requirements:**
```bash
pip install langgraph openai
export OPENAI_API_KEY=your_key_here
```

**Run:**
```bash
python examples/demo_agent.py
```

### 3. `langgraph_production.py`
Complete production example showing:
- Full LangGraph integration
- GPT-4 with memory context
- Proper error handling
- Memory consolidation workflow
- Detailed logging

**Requirements:**
```bash
pip install langgraph openai
export OPENAI_API_KEY=your_key_here
```

**Run:**
```bash
python examples/langgraph_production.py
```

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up OpenAI (optional):**
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

3. **Run basic examples:**
   ```bash
   python examples/basic_usage.py
   ```

4. **Try the demo agent:**
   ```bash
   python examples/demo_agent.py
   ```

## 💡 Tips

- **Without OpenAI API key**: The SDK will use deterministic mock embeddings for testing
- **LangGraph not installed**: The demo will gracefully handle missing dependencies
- **Production use**: See `langgraph_production.py` for a complete production-ready example

## 📚 Learn More

- [README.md](../README.md) - Full SDK documentation
- [QUICKSTART.md](../QUICKSTART.md) - Setup guide
- [neuromem.yaml](../neuromem.yaml) - Configuration reference
