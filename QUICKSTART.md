# Quick Start Guide

## Installation

```bash
# Clone the repository
git clone https://github.com/neuromem/neuromem-sdk.git
cd neuromem-sdk

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

## Running the Demo

```bash
# Run the basic usage examples
python examples/basic_usage.py

# Run the full demo agent
python examples/demo_agent.py
```

## Configuration

1. Copy the default config:
```bash
cp neuromem.yaml my_config.yaml
```

2. Edit `my_config.yaml` to configure storage backend:

For **in-memory** (testing):
```yaml
storage:
  database:
    type: memory
```

For **SQLite** (development):
```yaml
storage:
  database:
    type: sqlite
    url: neuromem.db
```

For **PostgreSQL** (production):
```yaml
storage:
  database:
    type: postgres
    url: postgresql://user:pass@localhost:5432/neuromem
```

## PostgreSQL Setup

If using PostgreSQL:

```bash
# Install PostgreSQL and pgvector extension
# On Ubuntu:
sudo apt-get install postgresql postgresql-contrib
sudo apt-get install postgresql-15-pgvector

# Create database
createdb neuromem

# The SDK will automatically create the schema
```

## Environment Variables

For OpenAI embeddings:
```bash
export OPENAI_API_KEY=your_api_key_here
```

## Next Steps

1. Read the [README.md](README.md) for full documentation
2. Explore [examples/](examples/) for more use cases
3. Check the PRD for architectural details
4. Start building your memory-enabled agent!

## Common Issues

## Common Issues

**Import errors**: Make sure you've installed all dependencies:
```bash
pip install -r requirements.txt
```
If running examples directly, the SDK includes code to handle paths automatically.

**Database connection errors**: Check your connection string in the config file.

**Embedding errors**: Set your `OPENAI_API_KEY` environment variable or use the fallback mock embeddings for testing.
