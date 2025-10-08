# Nifty Options Trader - Test Suite

## Running Tests

### Unit Tests
```bash
python -m pytest tests/unit/ -v
```

### Integration Tests  
```bash
python -m pytest tests/integration/ -v
```

### All Tests
```bash
python -m pytest tests/ -v
```

## Test Structure

- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests for system interactions
- `tests/fixtures/` - Test data and fixtures

## Coverage

Run with coverage:
```bash
python -m pytest --cov=src tests/
```