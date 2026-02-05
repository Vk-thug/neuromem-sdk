"""
Simple LiteLLM + NeuroMem Example

Shows how to add memory to LiteLLM in just 1 parameter!
"""

from neuromem import NeuroMem
from neuromem.adapters.litellm import completion_with_memory

# 1. Initialize NeuroMem
memory = NeuroMem.for_litellm(user_id="demo_user")

# 2. Use completion_with_memory instead of litellm.completion()
#    Just add the memory parameter - that's it!

if __name__ == "__main__":
    print("🧠 LiteLLM + NeuroMem Demo\n")
    
    # First conversation
    response1 = completion_with_memory(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "My name is Charlie and I love machine learning"}
        ],
        memory=memory  # <-- Just add this!
    )
    print(f"User: My name is Charlie and I love machine learning")
    print(f"Assistant: {response1.choices[0].message.content}\n")
    
    # Second conversation - memory will recall!
    response2 = completion_with_memory(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "What's my name?"}
        ],
        memory=memory
    )
    print(f"User: What's my name?")
    print(f"Assistant: {response2.choices[0].message.content}\n")
    
    # Third conversation
    response3 = completion_with_memory(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "What am I interested in?"}
        ],
        memory=memory
    )
    print(f"User: What am I interested in?")
    print(f"Assistant: {response3.choices[0].message.content}\n")
    
    print("✅ Memory is working! The assistant remembered your name and interests.")
    
    # Bonus: Works with any LiteLLM-supported model!
    print("\n🎉 Bonus: Try with different models:")
    print("  - OpenAI: gpt-4, gpt-3.5-turbo")
    print("  - Anthropic: claude-3-opus, claude-3-sonnet")
    print("  - Google: gemini-pro")
    print("  - And 100+ more models!")
