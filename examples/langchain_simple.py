"""
Simple LangChain + NeuroMem Example

Shows how to add memory to any LangChain chain in just 2 lines!
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from neuromem import NeuroMem
from neuromem.adapters.langchain import add_memory

# 1. Initialize NeuroMem
memory = NeuroMem.for_langchain(user_id="demo_user")

# 2. Create your LangChain chain (as usual)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. {memory_context}"),
    ("user", "{input}")
])
llm = ChatOpenAI(model="gpt-4o-mini")
output_parser = StrOutputParser()

chain = prompt | llm | output_parser

# 3. Add memory - that's it!
chain_with_memory = add_memory(chain, memory)

# 4. Use it!
if __name__ == "__main__":
    print("🧠 LangChain + NeuroMem Demo\n")
    
    # First conversation
    response1 = chain_with_memory.invoke({"input": "My name is Alice and I love Python"})
    print(f"User: My name is Alice and I love Python")
    print(f"Assistant: {response1}\n")
    
    # Second conversation - memory will recall the name!
    response2 = chain_with_memory.invoke({"input": "What's my name?"})
    print(f"User: What's my name?")
    print(f"Assistant: {response2}\n")
    
    # Third conversation - memory will recall the preference!
    response3 = chain_with_memory.invoke({"input": "What programming language do I like?"})
    print(f"User: What programming language do I like?")
    print(f"Assistant: {response3}\n")
    
    print("✅ Memory is working! The assistant remembered your name and preferences.")
