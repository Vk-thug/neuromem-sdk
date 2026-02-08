"""
Constants and configuration defaults for NeuroMem SDK.

This module centralizes all magic numbers and configuration defaults
to improve maintainability and make tuning easier.
"""

# Version
VERSION = "0.1.0"

# Memory Configuration Defaults
DEFAULT_EPISODIC_CONFIDENCE = 0.9  # Direct observations have high confidence
DEFAULT_EPISODIC_DECAY_RATE = 0.05  # Episodic memories decay faster
DEFAULT_SEMANTIC_DECAY_RATE = 0.01  # Semantic memories decay slower
DEFAULT_PROCEDURAL_DECAY_RATE = 0.02  # Procedural memories decay medium

# Retrieval Configuration
DEFAULT_RETRIEVAL_K = 8  # Default number of memories to retrieve
DEFAULT_MAX_RETRIEVAL_K = 100  # Maximum allowed retrieval count

# Retrieval Scoring Weights
DEFAULT_SIMILARITY_WEIGHT = 0.45
DEFAULT_SALIENCE_WEIGHT = 0.20
DEFAULT_RECENCY_WEIGHT = 0.15
DEFAULT_REINFORCEMENT_WEIGHT = 0.10
DEFAULT_CONFIDENCE_WEIGHT = 0.10

# Recency Calculation
DEFAULT_RECENCY_DECAY_LAMBDA = 0.1  # Exponential decay rate for recency
DEFAULT_RECENCY_HALF_LIFE_DAYS = 30  # Half-life for memory recency

# Reinforcement Calculation
DEFAULT_MAX_REINFORCEMENT_FOR_SCORING = 10  # Cap reinforcement at 10 accesses

# Salience Calculation
DEFAULT_BASE_SALIENCE = 0.5  # Base salience for all interactions
SALIENCE_BOOST_QUESTION = 0.2  # Boost for questions
SALIENCE_BOOST_LENGTH = 0.1  # Boost for long interactions (>100 chars)
SALIENCE_BOOST_PREFERENCE = 0.2  # Boost for preference keywords

# Content Validation
MAX_CONTENT_LENGTH = 50000  # 50KB max content length
MAX_USER_INPUT_LENGTH = 50000
MAX_ASSISTANT_OUTPUT_LENGTH = 50000
MAX_EMBEDDING_TEXT_LENGTH = 100000  # OpenAI limit

# Confidence Filtering
DEFAULT_MIN_CONFIDENCE_THRESHOLD = 0.3

# Diversity/Inhibition
DEFAULT_DIVERSITY_THRESHOLD = 0.85  # Similarity threshold for inhibition

# Memory Retention
DEFAULT_EPISODIC_RETENTION_DAYS = 30
DEFAULT_MAX_ACTIVE_MEMORIES = 50

# Consolidation
DEFAULT_CONSOLIDATION_INTERVAL = 10  # Consolidate every N turns
DEFAULT_MIN_CONSOLIDATION_CONFIDENCE = 0.7
DEFAULT_DECAY_THRESHOLD = 0.3

# Embedding Configuration
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
DEFAULT_EMBEDDING_DIMENSIONS = 1536  # OpenAI text-embedding-3-large
DEFAULT_CONSOLIDATION_LLM = "gpt-4o-mini"

# Embedding Cache
DEFAULT_EMBEDDING_CACHE_SIZE = 10000
DEFAULT_CACHE_ENABLED = True

# Retry Configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0  # seconds
DEFAULT_RETRY_MAX_DELAY = 60.0  # seconds
DEFAULT_RETRY_EXPONENTIAL_BASE = 2.0

# Circuit Breaker
DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60.0  # seconds

# Worker Configuration
DEFAULT_MAX_WORKER_RETRIES = 3
DEFAULT_MAINTENANCE_WORKER_RETRIES = 2
DEFAULT_WORKER_RETRY_DELAY = 2  # seconds (exponential: 2^retry_count)

# Queue Configuration
DEFAULT_CRITICAL_QUEUE_SIZE = 1000
DEFAULT_HIGH_QUEUE_SIZE = 500
DEFAULT_MEDIUM_QUEUE_SIZE = 100
DEFAULT_LOW_QUEUE_SIZE = 50
DEFAULT_BACKGROUND_QUEUE_SIZE = 10
DEFAULT_SALIENCE_THRESHOLD = 0.7  # Never drop tasks above this salience

# Dead Letter Queue
DEFAULT_MAX_DEAD_LETTER_SIZE = 1000

# Proactive Maintenance
DEFAULT_AUTO_CONSOLIDATE_THRESHOLD = 10  # Consolidate every N episodic memories
DEFAULT_CONSOLIDATION_INTERVAL_MINUTES = 60
DEFAULT_OPTIMIZATION_INTERVAL_HOURS = 24
DEFAULT_DECAY_INTERVAL_HOURS = 168  # Weekly

# Parallel Retrieval
DEFAULT_PARALLEL_RETRIEVAL_ENABLED = True
DEFAULT_MAX_PARALLEL_WORKERS = 3  # Thread pool size for parallel retrieval

# Health Check Thresholds
HEALTH_QUEUE_DEPTH_WARNING_CRITICAL = 500
HEALTH_QUEUE_DEPTH_WARNING_HIGH = 250
HEALTH_MEMORY_COUNT_WARNING = 100000
HEALTH_MEMORY_COUNT_CRITICAL = 500000
HEALTH_DLQ_WARNING = 10
HEALTH_DLQ_CRITICAL = 50

# PostgreSQL Configuration
POSTGRES_MIN_POOL_SIZE = 1
POSTGRES_MAX_POOL_SIZE = 10
POSTGRES_DEFAULT_VECTOR_DIMENSIONS = 1536

# OpenAI API Configuration
OPENAI_BATCH_SIZE_LIMIT = 2048  # Maximum texts per batch request

# Logging
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_JSON_LOGGING = False

# PII Redaction Patterns (defined in utils/logging.py)
# These are not imported here to avoid circular dependencies

# Feature Flags
DEFAULT_HYBRID_RETRIEVAL_ENABLED = True
DEFAULT_AUTO_TAG_ENABLED = True
DEFAULT_DECAY_ENABLED = True
DEFAULT_ASYNC_ENABLED = True
DEFAULT_RECONSOLIDATION_ENABLED = True

# Tagging Configuration
DEFAULT_MAX_TAGS_PER_MEMORY = 10

# Environment Variable Keys
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
ENV_CACHE_EMBEDDINGS = "NEUROMEM_CACHE_EMBEDDINGS"
ENV_LOG_LEVEL = "NEUROMEM_LOG_LEVEL"
ENV_JSON_LOGGING = "NEUROMEM_JSON_LOGGING"

# Validation
MIN_USER_ID_LENGTH = 1
MAX_USER_ID_LENGTH = 255
MIN_MEMORY_ID_LENGTH = 1
MAX_MEMORY_ID_LENGTH = 255
MIN_LIMIT_VALUE = 1
MAX_LIMIT_VALUE = 1000

# Preference Keywords for Salience Calculation
PREFERENCE_KEYWORDS = [
    "prefer", "like", "want", "need", "always", "never",
    "favorite", "hate", "love", "dislike", "usually", "typically"
]

# HTTP Status Codes (for future API)
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_UNPROCESSABLE_ENTITY = 422
HTTP_TOO_MANY_REQUESTS = 429
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_SERVICE_UNAVAILABLE = 503
