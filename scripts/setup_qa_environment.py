#!/usr/bin/env python3
"""
QA Environment Setup Script for Notion Expense Automation

This script creates and manages QA testing environments in Notion by:
1. Creating test databases (Expense Table, Split Details Table, Balances Page)
2. Setting up proper schema and relations
3. Providing teardown functionality to clean up after testing

Usage:
    python scripts/setup_qa_environment.py setup    # Create QA environment
    python scripts/setup_qa_environment.py teardown # Delete QA environment
    python scripts/setup_qa_environment.py status   # Check QA environment status
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from notion_client import Client
from notion_client.errors import APIResponseError
from config import Config
from logger import get_logger

logger = get_logger(__name__)

# QA Environment state file
QA_STATE_FILE = Path(__file__).parent / ".qa_environment_state.json"


class NotionQAEnvironment:
    """Manage QA testing environment in Notion."""
    
    def __init__(self, api_token: str, parent_page_id: Optional[str] = None, workspace_page_id: Optional[str] = None):
        """
        Initialize QA environment manager.
        
        Args:
            api_token: Notion API token
            parent_page_id: Parent page ID to create databases under (will be created if not provided)
            workspace_page_id: An existing page ID in the workspace to create the parent page under
        """
        self.client = Client(auth=api_token)
        self.parent_page_id = parent_page_id
        self.workspace_page_id = workspace_page_id
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load QA environment state from file."""
        if QA_STATE_FILE.exists():
            with open(QA_STATE_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_state(self):
        """Save QA environment state to file."""
        with open(QA_STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
        logger.info(f"Saved QA environment state to {QA_STATE_FILE}")
    
    def _create_qa_parent_page(self) -> str:
        """Create a parent page to organize all QA resources."""
        logger.info("Creating QA parent page...")
        
        properties = {
            "title": {
                "title": [
                    {
                        "text": {
                            "content": "QA Testing Environment"
                        }
                    }
                ]
            }
        }
        
        # Try workspace-level first (requires insert_content capability)
        if not self.workspace_page_id:
            logger.info("Attempting to create workspace-level page...")
            try:
                parent = {"type": "workspace", "workspace": True}
                response = self.client.pages.create(
                    parent=parent,
                    properties=properties,
                    icon={"type": "emoji", "emoji": "🧪"}
                )
                qa_parent_id = response["id"]
                logger.info(f"✓ Created workspace-level QA parent page: {qa_parent_id}")
                return qa_parent_id
            except APIResponseError as e:
                logger.warning(f"Cannot create workspace-level page: {e}")
                logger.warning("Your integration may need 'insert_content' capability")
                raise ValueError(
                    "Failed to create workspace-level page.\n"
                    "Please either:\n"
                    "1. Grant 'insert_content' capability to your integration, OR\n"
                    "2. Provide QA_WORKSPACE_PAGE_ID (any existing page) to create under"
                )
        
        # Create under existing page
        logger.info(f"Creating QA page under existing page: {self.workspace_page_id}")
        parent = {"type": "page_id", "page_id": self.workspace_page_id}
        
        response = self.client.pages.create(
            parent=parent,
            properties=properties,
            icon={"type": "emoji", "emoji": "🧪"}
        )
        
        qa_parent_id = response["id"]
        logger.info(f"✓ Created QA parent page: {qa_parent_id}")
        return qa_parent_id
    
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
    
    def _create_expense_database(self, split_db_id: str) -> str:
        """Create the Expense Table database."""
        logger.info("Creating Expense Table database...")
        
        parent = {"type": "page_id", "page_id": self.parent_page_id}
        
        properties = {
            "Merchant / Description": {"title": {}},
            "Date": {"date": {}},
            "Amount": {"number": {"format": "canadian_dollar"}},
            "Paid By": {"people": {}},
            "Split Details Table": {
                "relation": {
                    "database_id": split_db_id,
                    "type": "dual_property",
                    "dual_property": {
                        "synced_property_name": "Expense Table",
                        "synced_property_id": "expense_relation"
                    }
                }
            },
            "Receipt (optional)": {"files": {}},
            "Paid": {"number": {"format": "canadian_dollar"}}
        }
        
        response = self.client.databases.create(
            parent=parent,
            title=[{"type": "text", "text": {"content": "QA - Expense Table"}}],
            properties=properties,
            icon={"type": "emoji", "emoji": "💳"}
        )
        
        expense_db_id = response["id"]
        logger.info(f"✓ Created Expense Table: {expense_db_id}")
        return expense_db_id
    
    def _create_split_database(self, balance_db_id: str) -> str:
        """Create the Split Details Table database."""
        logger.info("Creating Split Details Table database...")
        
        parent = {"type": "page_id", "page_id": self.parent_page_id}
        
        properties = {
            "Title": {"title": {}},
            "Person": {"people": {}},
            "Date": {"date": {}},
            "Share Percent": {"number": {"format": "percent"}},
            "Balances": {
                "relation": {
                    "database_id": balance_db_id,
                    "type": "single_property",
                    "single_property": {}
                }
            }
            # Note: "Expense Table" relation and "Share Amount" formula will be added after Expense DB is created
        }
        
        response = self.client.databases.create(
            parent=parent,
            title=[{"type": "text", "text": {"content": "QA - Split Details Table"}}],
            properties=properties,
            icon={"type": "emoji", "emoji": "💸"}
        )
        
        split_db_id = response["id"]
        logger.info(f"✓ Created Split Details Table: {split_db_id}")
        return split_db_id
    
    def setup(self) -> Dict[str, str]:
        """
        Set up complete QA environment.
        
        Returns:
            Dictionary with database IDs
        """
        try:
            logger.info("=" * 60)
            logger.info("Setting up QA Environment in Notion")
            logger.info("=" * 60)
            
            # Step 0: Create parent page if not provided
            if not self.parent_page_id:
                logger.info("No parent page provided, creating one...")
                self.parent_page_id = self._create_qa_parent_page()
            
            # Step 1: Create Balances database
            balance_db_id = self._create_balances_database()
            
            # Step 2: Create Split Details database (needs balance database ID)
            split_db_id = self._create_split_database(balance_db_id)
            
            # Step 3: Create Expense database (needs split DB ID for relation)
            expense_db_id = self._create_expense_database(split_db_id)
            
            # Step 4: Update Split Details database to add Expense Table relation
            logger.info("Updating Split Details Table with Expense Table relation...")
            self.client.databases.update(
                database_id=split_db_id,
                properties={
                    "Expense Table": {
                        "relation": {
                            "database_id": expense_db_id,
                            "type": "dual_property",
                            "dual_property": {
                                "synced_property_name": "Split Details Table",
                                "synced_property_id": "split_relation"
                            }
                        }
                    }
                }
            )
            logger.info("✓ Updated Split Details Table with Expense Table relation")
            
            # Note: Share Amount formula must be added manually in Notion UI
            # Formula: empty(prop("Expense Table")) ? 0 : round(first(prop("Expense Table").prop("Amount")) * prop("Share Percent") * 100) / 100
            logger.info("⚠ Note: You'll need to manually add the Share Amount formula in Notion")
            
            # Save state
            self.state = {
                "created_at": datetime.now().isoformat(),
                "expense_db_id": expense_db_id,
                "split_db_id": split_db_id,
                "balance_db_id": balance_db_id,
                "parent_page_id": self.parent_page_id
            }
            self._save_state()
            
            logger.info("=" * 60)
            logger.info("✓ QA Environment Setup Complete!")
            logger.info("=" * 60)
            logger.info(f"Expense Table ID:       {expense_db_id}")
            logger.info(f"Split Details Table ID: {split_db_id}")
            logger.info(f"Balances Database ID:   {balance_db_id}")
            logger.info("=" * 60)
            logger.info("\nAdd these to your .env.qa file:")
            logger.info(f"EXPENSE_TABLE_DATABASE_ID={expense_db_id}")
            logger.info(f"SPLIT_DETAILS_DATABASE_ID={split_db_id}")
            logger.info(f"BALANCES_PAGE_ID={balance_db_id}")
            logger.info("=" * 60)
            
            return self.state
            
        except APIResponseError as e:
            logger.error(f"Failed to create QA environment: {e}")
            raise
    
    def teardown(self):
        """Tear down QA environment by archiving all created resources."""
        if not self.state:
            logger.warning("No QA environment state found. Nothing to tear down.")
            return
        
        try:
            logger.info("=" * 60)
            logger.info("Tearing down QA Environment")
            logger.info("=" * 60)
            
            # Archive databases
            for resource_type, resource_id in [
                ("Expense Table", self.state.get("expense_db_id")),
                ("Split Details Table", self.state.get("split_db_id")),
                ("Balances Database", self.state.get("balance_db_id"))
            ]:
                if resource_id:
                    try:
                        logger.info(f"Archiving {resource_type}: {resource_id}")
                        self.client.databases.update(
                            database_id=resource_id,
                            archived=True
                        )
                        logger.info(f"✓ Archived {resource_type}")
                    except APIResponseError as e:
                        logger.warning(f"Failed to archive {resource_type}: {e}")
            
            # Remove state file
            if QA_STATE_FILE.exists():
                QA_STATE_FILE.unlink()
                logger.info(f"✓ Removed state file: {QA_STATE_FILE}")
            
            logger.info("=" * 60)
            logger.info("✓ QA Environment Teardown Complete!")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during teardown: {e}")
            raise
    
    def status(self):
        """Check and display QA environment status."""
        if not self.state:
            logger.info("No QA environment currently set up.")
            return
        
        logger.info("=" * 60)
        logger.info("QA Environment Status")
        logger.info("=" * 60)
        logger.info(f"Created: {self.state.get('created_at', 'Unknown')}")
        logger.info(f"Expense Table ID:       {self.state.get('expense_db_id', 'N/A')}")
        logger.info(f"Split Details Table ID: {self.state.get('split_db_id', 'N/A')}")
        logger.info(f"Balances Database ID:   {self.state.get('balance_db_id', 'N/A')}")
        
        # Try to verify resources still exist
        logger.info("\nVerifying resources...")
        for resource_type, resource_id in [
            ("Expense Table", self.state.get("expense_db_id")),
            ("Split Details Table", self.state.get("split_db_id")),
            ("Balances Database", self.state.get("balance_db_id"))
        ]:
            if resource_id:
                try:
                    self.client.databases.retrieve(database_id=resource_id)
                    logger.info(f"✓ {resource_type}: Active")
                except APIResponseError:
                    logger.warning(f"✗ {resource_type}: Not found or archived")
        
        logger.info("=" * 60)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # Load configuration
    try:
        Config.validate()
        
        # Prefer OAuth token, fallback to internal integration token
        api_token = os.getenv("NOTION_OAUTH_ACCESS_TOKEN") or Config.NOTION_API_TOKEN
        
        if os.getenv("NOTION_OAUTH_ACCESS_TOKEN"):
            logger.info("Using OAuth authentication")
        else:
            logger.info("Using internal integration token")
            
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Make sure your .env file is properly configured")
        sys.exit(1)
    
    # Get parent page ID (optional - will be created if not provided)
    parent_page_id = os.getenv("QA_PARENT_PAGE_ID")
    workspace_page_id = os.getenv("QA_WORKSPACE_PAGE_ID")
    
    # Create environment manager
    qa_env = NotionQAEnvironment(api_token, parent_page_id, workspace_page_id)
    
    try:
        if command == "setup":
            qa_env.setup()
        elif command == "teardown":
            qa_env.teardown()
        elif command == "status":
            qa_env.status()
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
            sys.exit(1)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()