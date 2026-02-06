# Bug Fix: Memory Retrieval Validation Error

**Date**: 2026-02-06
**Issue**: Memory retrieval failing in interactive mode with validation error
**Status**: ✅ FIXED

---

## Problem Description

### User Report
When running `demo_agent.py` in interactive mode, every user query resulted in the following error:

```
🤖 Assistant: ⚠️ Memory retrieval failed: text must be a non-empty string, got: <class 'str'>
```

### Symptoms
- Error occurred on **every** user interaction during retrieval phase
- Observations were being stored successfully (database showed records)
- The error message was misleading: said "got: <class 'str'>" when expecting a string
- Interactive chat was unusable

### Root Cause Analysis

The issue was in the validation logic in `neuromem/utils/embeddings.py` line 129-130:

```python
# Old validation code
if not text or not isinstance(text, str):
    raise ValueError(f"text must be a non-empty string, got: {type(text)}")
```

**Problem**: This validation rejected **empty strings** (`""`), which are falsy in Python.

**How it happened**:
1. User types a query in `demo_agent.py` interactive mode
2. LangChain's `create_agent` passes the query through messages
3. `NeuroMemRunnable.invoke()` tries to extract query from input dict
4. If extraction fails, `query = input.get("input", input.get("question", ""))` returns `""`
5. Empty string is passed to `neuromem.retrieve("")`
6. `get_embedding("")` is called with empty string
7. Validation fails: `not text` is True for `""`, so error is raised

Additionally, `NeuroMemChatMessageHistory` explicitly called:
```python
memories = self.neuromem.retrieve(query="", task_type="chat", k=self.k)
```

---

## Solution

### Fix 1: Improved Validation in `embeddings.py`

**File**: `neuromem/utils/embeddings.py` (lines 128-135)

**Before**:
```python
# Validate text
if not text or not isinstance(text, str):
    raise ValueError(f"text must be a non-empty string, got: {type(text)}")
```

**After**:
```python
# Validate text
if not isinstance(text, str):
    raise ValueError(f"text must be a string, got: {type(text)}")

if not text or not text.strip():
    # For empty or whitespace-only queries, return a zero vector
    # This allows retrieval with empty queries (returns general context)
    logger.debug("Empty text provided for embedding, returning zero vector")
    return [0.0] * 1536
```

**Changes**:
- Split validation into two stages: type check first, then content check
- Empty/whitespace strings now return a zero vector instead of raising error
- Better error message: distinguishes between type errors and empty content
- Allows retrieval with empty queries (returns no semantic matches, which is correct behavior)

### Fix 2: Better Query Extraction in LangChain Adapter

**File**: `neuromem/adapters/langchain.py` (lines 32-52)

**Before**:
```python
def invoke(self, input: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
    """Retrieve memories and add to input."""
    # Extract query from input
    query = input.get("input", input.get("question", ""))

    # Retrieve memories
    try:
        memories = self.neuromem.retrieve(query=query, task_type="chat", k=self.k)
        context = "\n".join([f"- {m.content}" for m in memories])
    except Exception as e:
        print(f"⚠️ Memory retrieval failed: {e}")
        context = ""
```

**After**:
```python
def invoke(self, input: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
    """Retrieve memories and add to input."""
    # Extract query from input
    query = input.get("input", input.get("question", ""))

    # If no query text, try to extract from messages
    if not query and "messages" in input and isinstance(input["messages"], list):
        for msg in reversed(input["messages"]):
            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
                query = msg.content
                break

    # Retrieve memories
    try:
        if query and query.strip():
            memories = self.neuromem.retrieve(query=query, task_type="chat", k=self.k)
            context = "\n".join([f"- {m.content}" for m in memories])
        else:
            # No query provided, skip retrieval
            memories = []
            context = ""
    except Exception as e:
        print(f"⚠️ Memory retrieval failed: {e}")
        context = ""
```

**Changes**:
- Tries to extract query from `messages` list if not found in `input`/`question` keys
- Checks if query is non-empty before calling `retrieve()`
- Skips retrieval entirely if no valid query (returns empty context)
- Prevents passing empty strings to `get_embedding()`

### Fix 3: Avoid Empty Query in Message History

**File**: `neuromem/adapters/langchain.py` (lines 90-107)

**Before**:
```python
@property
def messages(self) -> List[BaseMessage]:
    """Retrieve messages from memory."""
    try:
        memories = self.neuromem.retrieve(query="", task_type="chat", k=self.k)
        # ...
```

**After**:
```python
@property
def messages(self) -> List[BaseMessage]:
    """Retrieve messages from memory."""
    try:
        # Use the list() method to get all recent memories instead of retrieve with empty query
        from neuromem.core.types import MemoryType
        memories = self.neuromem.list(memory_type=MemoryType.EPISODIC.value, limit=self.k)
        # ...
```

**Changes**:
- Use `list()` method instead of `retrieve("")` to get recent memories
- More semantically correct: we want recent memories, not semantic search with empty query
- Avoids passing empty string to `get_embedding()`

---

## Testing

### Test Suite

Created `test_retrieval_fix.py` with comprehensive tests:

**Test 1: Embedding Validation**
- ✅ Empty string returns zero vector
- ✅ Whitespace-only string returns zero vector
- ✅ Valid text returns embedding
- ✅ Non-string raises ValueError

**Test 2: LangChain Adapter Query Extraction**
- ✅ Successfully extracts query from messages
- ✅ Handles empty messages gracefully
- ✅ Handles missing input/messages gracefully

**Test 3: NeuroMem.retrieve() Method**
- ✅ Valid query returns results
- ✅ Empty query doesn't crash (returns 0 results)
- ✅ Whitespace query doesn't crash (returns 0 results)

### Running Tests

```bash
# Run the fix validation test suite
python3 test_retrieval_fix.py

# Run existing unit tests
pytest tests/ -v

# Run demo in interactive mode
python3 examples/demo_agent.py interactive
```

---

## Impact

### Before Fix
- ❌ Interactive mode unusable
- ❌ Every query resulted in validation error
- ❌ Confusing error message
- ❌ User couldn't retrieve memories

### After Fix
- ✅ Interactive mode works perfectly
- ✅ Empty queries handled gracefully (return no results)
- ✅ Valid queries work as expected
- ✅ Clear error messages for actual type errors
- ✅ Better query extraction from LangChain messages

### Performance
- No performance impact
- Empty queries return zero vector instantly (no API call)
- Valid queries work same as before

### Backward Compatibility
- ✅ Fully backward compatible
- Existing code that passes valid queries continues to work
- Empty queries that previously crashed now return empty results
- No breaking changes to API

---

## Lessons Learned

1. **Validation should be specific**: Distinguish between type errors (wrong type) and content errors (empty string)
2. **Fail gracefully**: Empty queries should return empty results, not crash
3. **Test edge cases**: Always test with empty strings, whitespace, None, etc.
4. **Error messages matter**: "got: <class 'str'>" was confusing when we expected a string
5. **Adapter integration**: LangChain adapters need robust query extraction from various input formats

---

## Related Files Modified

1. **neuromem/utils/embeddings.py**
   - Lines 128-135: Split validation, handle empty strings

2. **neuromem/adapters/langchain.py**
   - Lines 32-52: Better query extraction in `NeuroMemRunnable.invoke()`
   - Lines 90-107: Use `list()` instead of `retrieve("")` in `NeuroMemChatMessageHistory`

3. **test_retrieval_fix.py** (NEW)
   - Comprehensive test suite for validation fixes

---

## Commit

**Commit Hash**: c6def27
**Commit Message**: Fix: Memory retrieval validation error for empty queries

---

## Status

✅ **FIXED AND TESTED**

The interactive mode now works correctly. Users can:
- Ask questions and get responses
- Retrieve memories successfully
- Handle edge cases gracefully
- See clear error messages for actual problems

---

**Fixed by**: Claude Sonnet 4.5
**Date**: 2026-02-06
**Version**: 0.2.0 (post-release hotfix)
