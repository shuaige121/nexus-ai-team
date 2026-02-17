# NEXUS Test Suite

## Running Tests

### Unit Tests (no external dependencies)

```bash
pytest tests/test_pipeline_integration.py::test_work_order_creation -v
```

### Integration Tests (requires PostgreSQL + Redis)

```bash
# Start infrastructure
docker compose up -d postgres redis

# Initialize database schema
docker compose exec postgres psql -U nexus -d nexus -f /docker-entrypoint-initdb.d/schema.sql

# Run integration tests
pytest tests/test_pipeline_integration.py -v
```

### Full End-to-End Test

```bash
# Start gateway
uvicorn gateway.main:app --reload &

# Wait for startup
sleep 3

# Run E2E test
pytest tests/test_pipeline_integration.py::test_telegram_gateway_integration -v
```

## Test Coverage

- `test_work_order_creation`: AdminAgent work order creation
- `test_queue_enqueue_consume`: Redis Streams queue operations
- `test_dispatcher_process_work_order`: Full dispatcher flow with mocked LLM
- `test_telegram_gateway_integration`: Telegram → Gateway → Pipeline integration
