# QA Environment Setup Guide

This guide walks you through setting up and using the QA testing environment for the Notion Expense Automation project.

## Overview

The QA environment allows you to test the expense automation system without affecting your production Notion databases. It creates isolated test databases that can be easily set up and torn down.

## Quick Start

### 1. Prerequisites

- Python 3.8+ installed
- Notion API token with appropriate permissions
- Project dependencies installed: `pip install -r requirements.txt`

### 2. Initial Setup

```bash
# 1. Copy the QA environment template
cp .env.qa.example .env.qa

# 2. Edit .env.qa and add your Notion API token
# (Keep other fields empty for now)
nano .env.qa

# 3. Run the setup script
python scripts/setup_qa_environment.py setup
```

The setup script will:
- Create a "QA - Expense Table" database
- Create a "QA - Split Details Table" database
- Create a "QA - Total Balance" page
- Set up all necessary relations between them
- Output the database IDs

### 3. Configure .env.qa

Copy the database IDs from the setup output into your `.env.qa` file:

```bash
EXPENSE_TABLE_DATABASE_ID=<paste-expense-id>
SPLIT_DETAILS_DATABASE_ID=<paste-split-id>
BALANCES_PAGE_ID=<paste-balance-id>
```

### 4. Run Tests

```bash
# Run with QA environment
ENV=qa bash run.sh

# Or run specific tests
ENV=qa python -m pytest test/integration/
```

### 5. Cleanup

When done testing:

```bash
python scripts/setup_qa_environment.py teardown
```

## Detailed Usage

### Environment Management

#### Check Status

```bash
python scripts/setup_qa_environment.py status
```

Shows:
- When the environment was created
- Database IDs
- Whether resources are still accessible

#### Organize QA Resources

To keep QA databases organized under a specific Notion page:

1. Create a page in Notion called "QA Testing"
2. Get the page ID from the URL
3. Add to `.env.qa`:

```bash
QA_PARENT_PAGE_ID=your-page-id-here
```

4. Run setup - databases will be created under this page

### Testing Workflow

#### 1. Prepare Test Data

Place test receipts in `receipts/test_input/`:

```bash
cp test/fixtures/pdfs/*.pdf receipts/test_input/
```

#### 2. Run Application

```bash
ENV=qa bash run.sh
```

The application will:
- Use QA databases instead of production
- Process receipts from test_input
- Archive to `receipts/qa_processed/`

#### 3. Verify Results

Check your Notion QA databases to verify:
- Expenses were created correctly
- Splits were calculated properly
- Relations are working
- Files were uploaded

#### 4. Clean Up

```bash
# Remove processed test files
rm -rf receipts/qa_processed/*

# Tear down QA environment
python scripts/setup_qa_environment.py teardown
```

## Database Schema

### Expense Table

The QA Expense Table has the same schema as production:

| Property | Type | Description |
|----------|------|-------------|
| Merchant / Description | Title | Expense description |
| Date | Date | Transaction date |
| Amount | Number (CAD) | Total amount |
| Paid By | People | Person who paid |
| Split Details Table | Relation | Links to split entries |
| Receipt (optional) | Files | Receipt PDF attachments |
| Paid | Number (CAD) | Amount paid back |

### Split Details Table

| Property | Type | Description |
|----------|------|-------------|
| Title | Title | Split description |
| Person | People | Person who owes |
| Date | Date | Split date |
| Share Percent | Number (%) | Split percentage (0.5 = 50%) |
| Share Amount | Formula | Auto-calculated from expense |
| Balances | Relation | Links to balance page |
| Expense Table | Relation | Links back to expense |

### Formulas

The Share Amount is calculated automatically:

```
round(first(prop("Expense Table").prop("Amount")) * prop("Share Percent") * 100) / 100
```

## Troubleshooting

### "No module named 'config'"

Make sure you're running from the project root:

```bash
cd /path/to/notion_expense_automation_project
python scripts/setup_qa_environment.py setup
```

### "Failed to create database"

Check that:
1. Your Notion API token is valid
2. The token has permission to create databases
3. If using QA_PARENT_PAGE_ID, the token has access to that page

### "Resource not found" during teardown

The resource may have been manually deleted. This is safe to ignore - the script will clean up the state file.

### Databases not appearing in Notion

1. Check the setup output for database IDs
2. Navigate directly to the database using the ID:
   `https://notion.so/<database-id>`
3. Verify your API token has access to the workspace

## Best Practices

### 1. Separate Environments

Keep QA and production completely separate:

```bash
# Production
.env          # Production credentials
.env.prod     # Production backup

# QA
.env.qa       # QA credentials
```

### 2. Clean Up Regularly

Always tear down QA environments after testing:

```bash
# After each test session
python scripts/setup_qa_environment.py teardown
```

### 3. Use Test Data

Never use real receipts in QA:

```bash
# Good: Use test fixtures
cp test/fixtures/pdfs/*.pdf receipts/test_input/

# Bad: Using real receipts
cp ~/Downloads/real_receipt.pdf receipts/test_input/
```

### 4. Automate in CI/CD

Integrate QA setup/teardown in your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Setup QA Environment
  run: python scripts/setup_qa_environment.py setup
  
- name: Run Integration Tests
  run: ENV=qa pytest test/integration/
  
- name: Teardown QA Environment
  if: always()
  run: python scripts/setup_qa_environment.py teardown
```

### 5. Document Test Scenarios

Keep track of what you're testing:

```bash
# Create test documentation
echo "Testing split calculation with 50/50 split" > test_log.txt
ENV=qa bash run.sh >> test_log.txt 2>&1
```

## Advanced Usage

### Multiple QA Environments

Create multiple QA environments for different test scenarios:

```bash
# Environment 1: Basic testing
QA_PARENT_PAGE_ID=page-1 python scripts/setup_qa_environment.py setup
# Save IDs to .env.qa1

# Environment 2: Edge case testing  
QA_PARENT_PAGE_ID=page-2 python scripts/setup_qa_environment.py setup
# Save IDs to .env.qa2
```

### Persistent QA Environment

For long-term testing, keep the QA environment:

```bash
# Setup once
python scripts/setup_qa_environment.py setup

# Use for multiple test sessions
ENV=qa bash run.sh

# Only teardown when completely done
python scripts/setup_qa_environment.py teardown
```

### Integration with pytest

```python
# conftest.py
import pytest
import subprocess

@pytest.fixture(scope="session", autouse=True)
def qa_environment():
    """Set up QA environment for test session."""
    # Setup
    subprocess.run(["python", "scripts/setup_qa_environment.py", "setup"], check=True)
    
    yield
    
    # Teardown
    subprocess.run(["python", "scripts/setup_qa_environment.py", "teardown"], check=True)
```

## Support

For issues or questions:

1. Check the [scripts/README.md](../scripts/README.md) for detailed script documentation
2. Review logs in `logs/qa_expense_automation.log`
3. Verify your Notion API permissions
4. Check the state file: `scripts/.qa_environment_state.json`

## Related Documentation

- [Main README](../README.md) - Project overview
- [Setup Guide](../SETUP_GUIDE.md) - Initial project setup
- [Architecture](../ARCHITECTURE.md) - System design
- [Scripts README](../scripts/README.md) - Script documentation