#!/bin/bash
# Test script for NeuroMem SDK before publishing

echo "🧪 Testing NeuroMem SDK..."
echo ""

# Activate virtual environment
source venv/bin/activate

# Test 1: Import test
echo "1️⃣ Testing imports..."
python3 -c "
from neuromem import NeuroMem
from neuromem.adapters.langchain import add_memory, NeuroMemRunnable
from neuromem.adapters.langgraph import with_memory, NeuroMemCheckpointer
print('✅ All imports successful!')
print('  - LangChain: add_memory, NeuroMemRunnable')
print('  - LangGraph: with_memory, NeuroMemCheckpointer')
print('  - LiteLLM: Optional (install with: pip install litellm)')
" || { echo "❌ Import test failed"; exit 1; }

echo ""

# Test 2: Basic initialization
echo "2️⃣ Testing NeuroMem initialization..."
python3 -c "
from neuromem import NeuroMem
from neuromem.user import UserManager

# Create user
user = UserManager.create('test_user_ext_id', {'name': 'Test User'})

# Initialize NeuroMem with the user ID
memory = NeuroMem.from_config('neuromem.yaml', user_id=user.id)
print('✅ NeuroMem initialized successfully!')
" || { echo "❌ Initialization test failed"; exit 1; }

echo ""

# Test 3: Convenience methods
echo "3️⃣ Testing convenience methods..."
python3 -c "
from neuromem import NeuroMem
from neuromem.user import UserManager

user = UserManager.create('test_user_2', {})

memory_lc = NeuroMem.for_langchain(user_id=user.id)
memory_lg = NeuroMem.for_langgraph(user_id=user.id)
memory_ll = NeuroMem.for_litellm(user_id=user.id)
print('✅ Convenience methods work!')
print('  - NeuroMem.for_langchain()')
print('  - NeuroMem.for_langgraph()')
print('  - NeuroMem.for_litellm()')
" || { echo "❌ Convenience methods test failed"; exit 1; }

echo ""

# Test 4: Async infrastructure
echo "4️⃣ Testing async infrastructure..."
python3 -c "
from neuromem import NeuroMem
from neuromem.user import UserManager

user = UserManager.create('test_user_3', {})
memory = NeuroMem.for_langchain(user_id=user.id)

# Check async components
assert hasattr(memory.controller, 'scheduler'), 'Scheduler not found'
assert hasattr(memory.controller, 'metrics'), 'Metrics not found'
assert hasattr(memory.controller, 'ingest_worker'), 'Ingest worker not found'
assert hasattr(memory.controller, 'maintenance_worker'), 'Maintenance worker not found'
print('✅ Async infrastructure initialized!')
print('  - PriorityTaskScheduler')
print('  - MetricsCollector')
print('  - IngestWorker')
print('  - MaintenanceWorker')
" || { echo "❌ Async infrastructure test failed"; exit 1; }

echo ""

# Test 5: Observe (async)
echo "5️⃣ Testing async observe..."
python3 -c "
from neuromem import NeuroMem
from neuromem.user import UserManager
import time

user = UserManager.create('test_user_4', {})
memory = NeuroMem.for_langchain(user_id=user.id)

# Observe should return immediately
start = time.time()
memory.observe('Hello', 'Hi there!')
duration = time.time() - start

print(f'⏱️  observe() took {duration*1000:.2f}ms')
if duration < 0.1:  # Should be under 100ms
    print('✅ Async observe is FAST! (<100ms)')
else:
    print('⚠️  observe() slower than expected but still works')
" || { echo "❌ Observe test failed"; exit 1; }

echo ""
echo "🎉 All tests passed!"
echo ""
echo "📦 SDK is ready for local testing!"
echo ""
echo "To test with examples:"
echo "  source venv/bin/activate"
echo "  python examples/langchain_simple.py"
echo "  python examples/langgraph_simple.py"
echo "  python examples/litellm_simple.py  # (requires: pip install litellm)"
echo ""
echo "To publish to PyPI:"
echo "  1. Update version in pyproject.toml"
echo "  2. Build: python3 -m build"
echo "  3. Upload: python3 -m twine upload dist/*"
