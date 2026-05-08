# QA Environment Setup Scripts

This directory contains scripts for managing QA testing environments.

## setup_qa_environment.py

Automates the creation and teardown of Notion databases for QA testing.

### Features

- **Setup**: Creates complete QA environment with proper schema and relations
  - Expense Table database
  - Split Details Table database  
  - Balances page
  - Proper relations between all resources

- **Teardown**: Cleans up QA environment by archiving all created resources

- **Status**: Checks current QA environment status and verifies resources

### Prerequisites

1. Notion API token with appropriate permissions
2. Configured `.env` file with `NOTION_API_TOKEN`
3. Python dependencies installed (`pip install -r requirements.txt`)

### Usage

#### Create QA Environment

```bash
python scripts/setup_qa_environment.py setup
```

This will:
1. Create a Balances page
2. Create Split Details Table database
3. Create Expense Table database
4. Set up proper relations between all resources
5. Save environment state to `.qa_environment_state.json`
6. Output database IDs for your `.env.qa` file

#### Check Status

```bash
python scripts/setup_qa_environment.py status
```

Shows current QA environment status and verifies resources are accessible.

#### Tear Down QA Environment

```bash
python scripts/setup_qa_environment.py teardown
```

Archives all QA resources and removes state file.

### Configuration

#### Optional: Parent Page

To organize QA resources under a specific Notion page, set:

```bash
export QA_PARENT_PAGE_ID=your-page-id
```

Or add to your `.env` file:

```
QA_PARENT_PAGE_ID=your-page-id
```

#### Environment Files

After setup, add the generated IDs to `.env.qa`:

```bash
# QA Environment
EXPENSE_TABLE_DATABASE_ID=<generated-id>
SPLIT_DETAILS_DATABASE_ID=<generated-id>
BALANCES_PAGE_ID=<generated-id>
```

### Database Schema

#### Expense Table

| Property | Type | Description |
|----------|------|-------------|
| Merchant / Description | Title | Expense description |
| Date | Date | Transaction date |
| Amount | Number (CAD) | Total amount |
| Paid By | People | Who paid |
| Split Details Table | Relation | Links to splits |
| Receipt (optional) | Files | Receipt attachments |
| Paid | Number (CAD) | Amount paid back |

#### Split Details Table

| Property | Type | Description |
|----------|------|-------------|
| Title | Title | Split description |
| Person | People | Who owes |
| Date | Date | Split date |
| Share Percent | Number (%) | Split percentage |
| Share Amount | Formula | Calculated amount |
| Balances | Relation | Links to balance page |
| Expense Table | Relation | Links to expense |

### State Management

The script maintains state in `.qa_environment_state.json`:

```json
{
  "created_at": "2026-05-08T01:00:00",
  "expense_db_id": "...",
  "split_db_id": "...",
  "balance_page_id": "...",
  "parent_page_id": "..."
}
```

This file is automatically created during setup and removed during teardown.

### Troubleshooting

#### "No QA environment state found"

Run `setup` command first to create the environment.

#### "Failed to archive resource"

The resource may have been manually deleted. Run `teardown` to clean up state file.

#### Import errors

Make sure you're running from the project root:

```bash
cd /path/to/notion_expense_automation_project
python scripts/setup_qa_environment.py setup
```

### Best Practices

1. **Always teardown** after testing to avoid cluttering your Notion workspace
2. **Use separate API tokens** for QA and production if possible
3. **Document test scenarios** that use the QA environment
4. **Verify status** before running tests to ensure environment is ready
5. **Keep .env.qa separate** from production .env files

### Integration with Testing

Use the QA environment in your test suite:

```python
import os
import pytest

@pytest.fixture(scope="session")
def qa_environment():
    """Ensure QA environment is set up before tests."""
    # Load .env.qa
    from dotenv import load_dotenv
    load_dotenv(".env.qa")
    
    # Verify QA environment exists
    assert os.getenv("EXPENSE_TABLE_DATABASE_ID"), "QA environment not set up"
    
    yield
    
    # Optional: teardown after all tests
    # os.system("python scripts/setup_qa_environment.py teardown")
```

### Example Workflow

```bash
# 1. Set up QA environment
python scripts/setup_qa_environment.py setup

# 2. Copy IDs to .env.qa
# (IDs are printed by setup command)

# 3. Run tests with QA environment
ENV=qa python -m pytest test/integration/

# 4. Check environment status
python scripts/setup_qa_environment.py status

# 5. Clean up when done
python scripts/setup_qa_environment.py teardown