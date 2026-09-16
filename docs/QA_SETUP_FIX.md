# QA Environment Setup Fix

## Problem
The QA environment setup script was failing to create databases because it was trying to create a relation between the Split Details Table and a **page** (Balances Page) instead of a **database**. Notion relations can only be created between databases, not between a database and a page.

## Root Cause
The original implementation created:
1. ✅ QA Parent Page (workspace page)
2. ❌ Balances **Page** (should be a database)
3. ❌ Split Details Table trying to relate to the Balances Page (invalid)
4. ❌ Expense Table (never created due to previous error)

## Solution
Changed the Balances from a **page** to a **database** with the following schema:

### Balances Database Schema
| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Balance entry name |
| Person | People | Person associated with balance |
| Balance | Number (CAD) | Current balance amount |

## Changes Made

### 1. Renamed Method
- `_create_balances_page()` → `_create_balances_database()`

### 2. Updated Implementation
Changed from creating a page to creating a database with proper properties:

```python
def _create_balances_database(self) -> str:
    """Create the Balances database."""
    logger.info("Creating Balances database...")
    
    parent = {"type": "page_id", "page_id": self.parent_page_id}
    
    properties = {
        "Name": {"title": {}},
        "Person": {"people": {}},
        "Balance": {"number": {"format": "canadian_dollar"}}
    }
    
    response = self.client.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": "QA - Total Balance"}}],
        properties=properties,
        icon={"type": "emoji", "emoji": "💰"}
    )
    
    balance_db_id = response["id"]
    logger.info(f"✓ Created Balances database: {balance_db_id}")
    return balance_db_id
```

### 3. Updated Parameter Names
- Changed all references from `balance_page_id` to `balance_db_id`
- Updated function signatures
- Updated state storage

### 4. Updated Logging
- Changed "Balances Page ID" to "Balances Database ID" in all output messages

## Database Structure

The complete QA environment now creates:

```
QA Testing Environment (Parent Page)
├── QA - Expense Table (Database)
│   ├── Merchant / Description (Title)
│   ├── Date (Date)
│   ├── Amount (Number - CAD)
│   ├── Paid By (People)
│   ├── Split Details Table (Relation → Split Details)
│   ├── Receipt (optional) (Files)
│   └── Paid (Number - CAD)
│
├── QA - Split Details Table (Database)
│   ├── Title (Title)
│   ├── Person (People)
│   ├── Date (Date)
│   ├── Share Percent (Number - %)
│   ├── Share Amount (Formula)
│   ├── Balances (Relation → Balances Database)
│   └── Expense Table (Relation → Expense Table)
│
└── QA - Total Balance (Database)
    ├── Name (Title)
    ├── Person (People)
    └── Balance (Number - CAD)
```

## Testing

To test the fix:

```bash
# 1. Set up QA environment
python scripts/setup_qa_environment.py setup

# 2. Verify all three databases were created
python scripts/setup_qa_environment.py status

# 3. Check your Notion workspace for:
#    - QA - Expense Table (database)
#    - QA - Split Details Table (database)
#    - QA - Total Balance (database)

# 4. Clean up when done
python scripts/setup_qa_environment.py teardown
```

## Expected Output

```
============================================================
Setting up QA Environment in Notion
============================================================
Creating QA parent page...
✓ Created workspace-level QA parent page: <page-id>
Creating Balances database...
✓ Created Balances database: <db-id>
Creating Split Details Table database...
✓ Created Split Details Table: <db-id>
Creating Expense Table database...
✓ Created Expense Table: <db-id>
Updating Split Details Table relation to Expense Table...
✓ Updated Split Details Table relation
============================================================
✓ QA Environment Setup Complete!
============================================================
Expense Table ID:       <expense-db-id>
Split Details Table ID: <split-db-id>
Balances Database ID:   <balance-db-id>
============================================================

Add these to your .env.qa file:
EXPENSE_TABLE_DATABASE_ID=<expense-db-id>
SPLIT_DETAILS_DATABASE_ID=<split-db-id>
BALANCES_PAGE_ID=<balance-db-id>
============================================================
```

## Files Modified
- [`scripts/setup_qa_environment.py`](../scripts/setup_qa_environment.py) - Fixed database creation logic

## Related Documentation
- [QA Environment Guide](QA_ENVIRONMENT_GUIDE.md)
- [Scripts README](../scripts/README.md)