"""
E2E test fixtures and configuration.
Manages test Notion database lifecycle - creates and cleans up test data.
"""
import pytest
import os
from notion_client import Client
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def notion_test_client():
    """
    Create a Notion client using test credentials.
    Requires NOTION_TEST_TOKEN in environment.
    """
    test_token = os.getenv("NOTION_TEST_TOKEN")
    if not test_token:
        pytest.skip("NOTION_TEST_TOKEN not set - skipping e2e tests")
    
    client = Client(auth=test_token)
    logger.info("Created Notion test client")
    return client


@pytest.fixture(scope="session")
def test_expense_database_id():
    """
    Get test expense database ID from environment.
    This should be a dedicated test database, NOT production.
    """
    db_id = os.getenv("NOTION_TEST_EXPENSE_DB_ID")
    if not db_id:
        pytest.skip("NOTION_TEST_EXPENSE_DB_ID not set - skipping e2e tests")
    
    logger.info(f"Using test expense database: {db_id}")
    return db_id


@pytest.fixture(scope="session")
def test_split_database_id():
    """
    Get test split database ID from environment.
    This should be a dedicated test database, NOT production.
    """
    db_id = os.getenv("NOTION_TEST_SPLIT_DB_ID")
    if not db_id:
        pytest.skip("NOTION_TEST_SPLIT_DB_ID not set - skipping e2e tests")
    
    logger.info(f"Using test split database: {db_id}")
    return db_id


@pytest.fixture
def cleanup_test_entries(notion_test_client, test_expense_database_id, test_split_database_id):
    """
    Fixture to track and cleanup test entries created during tests.
    Yields a list to collect entry IDs, then cleans them up after test.
    """
    created_entries = {
        "expenses": [],
        "splits": []
    }
    
    yield created_entries
    
    # Cleanup after test
    logger.info("Cleaning up test entries...")
    
    # Archive expense entries
    for entry_id in created_entries["expenses"]:
        try:
            notion_test_client.pages.update(
                page_id=entry_id,
                archived=True
            )
            logger.info(f"Archived expense entry: {entry_id}")
        except Exception as e:
            logger.error(f"Failed to archive expense {entry_id}: {e}")
    
    # Archive split entries
    for entry_id in created_entries["splits"]:
        try:
            notion_test_client.pages.update(
                page_id=entry_id,
                archived=True
            )
            logger.info(f"Archived split entry: {entry_id}")
        except Exception as e:
            logger.error(f"Failed to archive split {entry_id}: {e}")
    
    logger.info(f"Cleanup complete: {len(created_entries['expenses'])} expenses, {len(created_entries['splits'])} splits")


@pytest.fixture
def sample_expense_data():
    """
    Provide sample expense data for testing.
    """
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "merchant": "Test Merchant",
        "amount": 100.00,
        "category": "Test Category",
        "description": "E2E Test Expense",
        "payment_method": "Credit Card"
    }


@pytest.fixture
def sample_split_data():
    """
    Provide sample split data for testing.
    """
    return [
        {
            "person": "Person A",
            "amount": 50.00,
            "description": "E2E Test Split 1"
        },
        {
            "person": "Person B",
            "amount": 50.00,
            "description": "E2E Test Split 2"
        }
    ]


@pytest.fixture(scope="session", autouse=True)
def verify_test_environment():
    """
    Verify that we're using test environment, not production.
    This runs automatically before any e2e tests.
    """
    test_token = os.getenv("NOTION_TEST_TOKEN")
    prod_token = os.getenv("NOTION_TOKEN")
    
    if test_token and prod_token and test_token == prod_token:
        pytest.exit("ERROR: NOTION_TEST_TOKEN matches NOTION_TOKEN! Never run e2e tests against production!")
    
    logger.info("✓ Test environment verified - not using production credentials")

# Made with Bob
