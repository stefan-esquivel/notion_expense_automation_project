# Test Suite Documentation

This directory contains the complete test suite for the Notion Expense Automation project, organized into three testing layers as defined in [GitHub Issue #10](https://github.com/stefan-esquivel/notion_expense_automation_project/issues/10).

## Test Structure

```
test/
├── unit/                          # Fast, fully mocked tests
│   ├── test_config.py             # Configuration loading/validation
│   ├── test_pdf_extractor.py      # PDF parsing logic
│   ├── test_file_organizer.py     # File organization logic
│   └── test_notion_api.py         # Notion API request building
├── integration/                   # Module interaction tests
│   ├── test_pdf_to_notion.py      # PDF → Notion payload flow
│   └── test_file_organizer_flow.py # File organization integration
├── e2e/                           # Real Notion API tests
│   ├── conftest.py                # Test database lifecycle fixtures
│   └── test_expense_submission.py # Full expense submission flow
└── fixtures/                      # Shared test data
    ├── sample_receipt.txt         # Sample receipt text
    ├── sample_receipt_data.json   # Structured receipt data
    └── mock_notion_response.json  # Mock Notion API responses
```

## Test Layers

### Unit Tests (`test/unit/`)
- **Purpose**: Test individual functions and classes in isolation
- **Speed**: Very fast (< 1 second total)
- **Dependencies**: Fully mocked, no external services
- **When to run**: On every commit, in CI/CD pipeline

```bash
pytest test/unit/ -v
```

### Integration Tests (`test/integration/`)
- **Purpose**: Test how modules work together
- **Speed**: Fast (< 5 seconds total)
- **Dependencies**: External APIs mocked, modules interact
- **When to run**: Before merging PRs, in CI/CD pipeline

```bash
pytest test/integration/ -v
```

### E2E Tests (`test/e2e/`)
- **Purpose**: Test complete workflows with real Notion API
- **Speed**: Slower (depends on API response time)
- **Dependencies**: Real Notion test databases required
- **When to run**: Manually before releases, in QA environment

```bash
pytest test/e2e/ -v -m e2e
```

## Setup

### 1. Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

### 2. Configure E2E Test Environment

E2E tests require separate test databases in Notion. **Never use production databases!**

Create a `.env` file with test credentials:

```bash
# Test Notion credentials (SEPARATE from production!)
NOTION_TEST_TOKEN=secret_test_token_here
NOTION_TEST_EXPENSE_DB_ID=test_expense_database_id
NOTION_TEST_SPLIT_DB_ID=test_split_database_id
```

**Important**: The test suite will verify that `NOTION_TEST_TOKEN` is different from `NOTION_TOKEN` to prevent accidental testing against production.

### 3. Create Test Databases in Notion

1. Create a new Notion workspace for testing (or use a dedicated test page)
2. Duplicate your production expense and split databases
3. Copy the database IDs to your `.env` file
4. Create a test integration token with access to these databases

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Layer
```bash
pytest test/unit/           # Unit tests only
pytest test/integration/    # Integration tests only
pytest test/e2e/           # E2E tests only
```

### Run Tests by Marker
```bash
pytest -m unit              # All unit tests
pytest -m integration       # All integration tests
pytest -m e2e              # All e2e tests
```

### Run Specific Test File
```bash
pytest test/unit/test_config.py -v
```

### Run Specific Test
```bash
pytest test/unit/test_config.py::TestConfig::test_load_config_success -v
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html
```

View coverage report: `open htmlcov/index.html`

## Test Markers

Tests are marked with pytest markers for easy filtering:

- `@pytest.mark.unit` - Unit tests (fast, fully mocked)
- `@pytest.mark.integration` - Integration tests (modules working together)
- `@pytest.mark.e2e` - End-to-end tests (real API calls)

## E2E Test Fixtures

The `test/e2e/conftest.py` file provides important fixtures:

- `notion_test_client` - Authenticated Notion client for tests
- `test_expense_database_id` - Test expense database ID
- `test_split_database_id` - Test split database ID
- `cleanup_test_entries` - Automatic cleanup of test data
- `sample_expense_data` - Sample expense data for testing
- `sample_split_data` - Sample split data for testing

### Cleanup Behavior

The `cleanup_test_entries` fixture ensures all test data is cleaned up after each test:

```python
def test_create_expense(notion_test_client, cleanup_test_entries):
    # Create expense
    response = notion_test_client.pages.create(...)
    
    # Add to cleanup list
    cleanup_test_entries["expenses"].append(response["id"])
    
    # Test assertions...
    # Cleanup happens automatically after test completes
```

## Writing New Tests

### Unit Test Template

```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.unit
class TestMyModule:
    def test_my_function(self):
        # Arrange
        mock_dependency = Mock()
        
        # Act
        result = my_function(mock_dependency)
        
        # Assert
        assert result == expected_value
        mock_dependency.method.assert_called_once()
```

### E2E Test Template

```python
import pytest

@pytest.mark.e2e
def test_my_e2e_flow(
    notion_test_client,
    test_expense_database_id,
    cleanup_test_entries
):
    # Create test data
    response = notion_test_client.pages.create(...)
    
    # Track for cleanup
    cleanup_test_entries["expenses"].append(response["id"])
    
    # Verify
    assert response["object"] == "page"
```

## Continuous Integration

The test suite is designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Unit Tests
  run: pytest test/unit/ -v

- name: Run Integration Tests
  run: pytest test/integration/ -v

# E2E tests run in separate QA environment
- name: Run E2E Tests
  run: pytest test/e2e/ -v
  env:
    NOTION_TEST_TOKEN: ${{ secrets.NOTION_TEST_TOKEN }}
    NOTION_TEST_EXPENSE_DB_ID: ${{ secrets.NOTION_TEST_EXPENSE_DB_ID }}
    NOTION_TEST_SPLIT_DB_ID: ${{ secrets.NOTION_TEST_SPLIT_DB_ID }}
```

## Best Practices

1. **Keep unit tests fast** - Mock all external dependencies
2. **Use fixtures** - Share common test setup via pytest fixtures
3. **Clean up after E2E tests** - Always use `cleanup_test_entries` fixture
4. **Test edge cases** - Include tests for error conditions
5. **Use descriptive names** - Test names should describe what they test
6. **One assertion per test** - Keep tests focused and simple
7. **Never test against production** - Always use separate test databases

## Troubleshooting

### E2E Tests Skipped
- Ensure `NOTION_TEST_TOKEN` is set in `.env`
- Ensure test database IDs are configured
- Verify test token has access to test databases

### Import Errors
- Install dev dependencies: `pip install -r requirements-dev.txt`
- Ensure you're in the project root directory

### Cleanup Failures
- Check test token permissions
- Verify database IDs are correct
- Review logs for specific error messages

## Contributing

When adding new features:
1. Write unit tests first (TDD approach)
2. Add integration tests for module interactions
3. Add E2E tests for critical user flows
4. Ensure all tests pass before submitting PR

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Notion API Documentation](https://developers.notion.com/)
- [GitHub Issue #10](https://github.com/stefan-esquivel/notion_expense_automation_project/issues/10) - Original test suite requirements