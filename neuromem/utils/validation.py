"""
Input validation utilities for NeuroMem SDK.

Provides validation functions to prevent security vulnerabilities
and ensure data integrity.
"""

import uuid
from typing import List


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_user_id(user_id: str) -> str:
    """
    Validate user_id format (must be valid UUID).

    Args:
        user_id: User ID to validate

    Returns:
        Validated user_id

    Raises:
        ValidationError: If user_id is invalid
    """
    if not user_id:
        raise ValidationError("user_id cannot be empty")

    if not isinstance(user_id, str):
        raise ValidationError(f"user_id must be a string, got {type(user_id)}")

    # Must be valid UUID format
    try:
        uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise ValidationError(f"user_id must be a valid UUID, got: {user_id[:50]}")

    return user_id


def validate_content(content: str, max_length: int = 50000, field_name: str = "content") -> str:
    """
    Validate content string (e.g., user_input, assistant_output).

    Args:
        content: Content string to validate
        max_length: Maximum allowed length (default: 50KB)
        field_name: Name of the field for error messages

    Returns:
        Validated content

    Raises:
        ValidationError: If content is invalid
    """
    if content is None:
        raise ValidationError(f"{field_name} cannot be None")

    if not isinstance(content, str):
        raise ValidationError(f"{field_name} must be a string, got {type(content)}")

    if len(content) == 0:
        raise ValidationError(f"{field_name} cannot be empty")

    if len(content) > max_length:
        raise ValidationError(
            f"{field_name} exceeds maximum length of {max_length} characters "
            f"(got {len(content)} characters)"
        )

    return content


def validate_memory_id(memory_id: str) -> str:
    """
    Validate memory_id format (must be valid UUID).

    Args:
        memory_id: Memory ID to validate

    Returns:
        Validated memory_id

    Raises:
        ValidationError: If memory_id is invalid
    """
    if not memory_id:
        raise ValidationError("memory_id cannot be empty")

    if not isinstance(memory_id, str):
        raise ValidationError(f"memory_id must be a string, got {type(memory_id)}")

    # Must be valid UUID format
    try:
        uuid.UUID(memory_id)
    except (ValueError, AttributeError):
        raise ValidationError(f"memory_id must be a valid UUID, got: {memory_id[:50]}")

    return memory_id


def validate_memory_type(memory_type: str) -> str:
    """
    Validate memory_type value (must be one of allowed types).

    Args:
        memory_type: Memory type to validate

    Returns:
        Validated memory_type

    Raises:
        ValidationError: If memory_type is invalid
    """
    allowed_types = ["episodic", "semantic", "procedural", "affective", "session"]

    if not memory_type:
        raise ValidationError("memory_type cannot be empty")

    if not isinstance(memory_type, str):
        raise ValidationError(f"memory_type must be a string, got {type(memory_type)}")

    if memory_type.lower() not in allowed_types:
        raise ValidationError(
            f"memory_type must be one of {allowed_types}, got: {memory_type}"
        )

    return memory_type.lower()


def validate_limit(limit: int, max_limit: int = 1000) -> int:
    """
    Validate limit parameter for pagination.

    Args:
        limit: Limit value to validate
        max_limit: Maximum allowed limit (default: 1000)

    Returns:
        Validated limit

    Raises:
        ValidationError: If limit is invalid
    """
    if not isinstance(limit, int):
        raise ValidationError(f"limit must be an integer, got {type(limit)}")

    if limit < 1:
        raise ValidationError(f"limit must be at least 1, got: {limit}")

    if limit > max_limit:
        raise ValidationError(f"limit cannot exceed {max_limit}, got: {limit}")

    return limit


def validate_embedding(embedding: List[float], expected_dims: int = 1536) -> List[float]:
    """
    Validate embedding vector.

    Args:
        embedding: Embedding vector to validate
        expected_dims: Expected dimension count (default: 1536 for OpenAI)

    Returns:
        Validated embedding

    Raises:
        ValidationError: If embedding is invalid
    """
    if not embedding:
        raise ValidationError("embedding cannot be empty")

    if not isinstance(embedding, list):
        raise ValidationError(f"embedding must be a list, got {type(embedding)}")

    if len(embedding) != expected_dims:
        raise ValidationError(
            f"embedding must have {expected_dims} dimensions, got {len(embedding)}"
        )

    if not all(isinstance(x, (int, float)) for x in embedding):
        raise ValidationError("embedding must contain only numbers")

    return embedding


def validate_filters(filters: dict) -> dict:
    """
    Validate and sanitize filter dictionary for queries.

    This prevents SQL injection by ensuring only allowed filter keys are used.

    Args:
        filters: Filter dictionary to validate

    Returns:
        Validated and sanitized filters

    Raises:
        ValidationError: If filters contain invalid keys
    """
    if not isinstance(filters, dict):
        raise ValidationError(f"filters must be a dict, got {type(filters)}")

    # Whitelist of allowed filter keys
    allowed_keys = {'user_id', 'memory_type', 'tags', 'salience_min', 'salience_max',
                    'confidence_min', 'confidence_max', 'created_after', 'created_before'}

    # Check for disallowed keys
    invalid_keys = set(filters.keys()) - allowed_keys
    if invalid_keys:
        raise ValidationError(
            f"Invalid filter keys: {invalid_keys}. Allowed keys: {allowed_keys}"
        )

    # Validate each filter value
    validated = {}

    if 'user_id' in filters:
        validated['user_id'] = validate_user_id(filters['user_id'])

    if 'memory_type' in filters:
        mt = filters['memory_type']
        if isinstance(mt, str):
            validated['memory_type'] = validate_memory_type(mt)
        elif isinstance(mt, list):
            validated['memory_type'] = [validate_memory_type(t) for t in mt]
        else:
            raise ValidationError(f"memory_type must be str or list, got {type(mt)}")

    if 'tags' in filters:
        if not isinstance(filters['tags'], list):
            raise ValidationError(f"tags must be a list, got {type(filters['tags'])}")
        validated['tags'] = filters['tags']

    # Validate numeric ranges
    for key in ['salience_min', 'salience_max', 'confidence_min', 'confidence_max']:
        if key in filters:
            val = filters[key]
            if not isinstance(val, (int, float)):
                raise ValidationError(f"{key} must be a number, got {type(val)}")
            if not 0 <= val <= 1:
                raise ValidationError(f"{key} must be between 0 and 1, got {val}")
            validated[key] = val

    # Validate date filters
    for key in ['created_after', 'created_before']:
        if key in filters:
            validated[key] = filters[key]  # Assume datetime objects are validated elsewhere

    return validated


def sanitize_sql_string(value: str) -> str:
    """
    Sanitize a string value for SQL (additional layer of defense).

    Note: This should NOT replace parameterized queries, but provides
    defense in depth.

    Args:
        value: String value to sanitize

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        raise ValidationError(f"Expected string, got {type(value)}")

    # Remove or escape dangerous SQL characters
    dangerous_chars = ["'", '"', ';', '--', '/*', '*/','xp_', 'sp_', 'DROP', 'DELETE', 'INSERT']

    sanitized = value
    for char in dangerous_chars:
        if char.lower() in sanitized.lower():
            raise ValidationError(f"Potentially dangerous SQL pattern detected: {char}")

    return sanitized
