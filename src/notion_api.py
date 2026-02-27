"""Notion API integration module."""
from httpx._models import Response


from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import httpx
from notion_client import Client
from notion_client.errors import APIResponseError
from config import Config

NOTION_VERSION = "2025-09-03"

class NotionExpenseClient:
    """Handle all Notion API operations for expense tracking."""
    
    def __init__(self, api_token: str, expense_db_id: str, split_db_id: str, balance_page_id: str):
        self.client = Client(auth=api_token)
        self.api_token = api_token
        self.expense_db_id = expense_db_id
        self.split_db_id = split_db_id
        self.balance_page_id = balance_page_id
        
        # Map person names to Notion user IDs
        self.user_id_map = {
            Config.YOUR_NAME: Config.YOUR_USER_ID,
            Config.PARTNER_NAME: Config.PARTNER_USER_ID
        }
    
    def _get_user_id(self, person_name: str) -> str:
        """Get Notion user ID for a person name."""
        user_id = self.user_id_map.get(person_name)
        if not user_id:
            raise ValueError(f"No user ID found for person: {person_name}")
        return user_id
    
    def _upload_file_to_notion(self, file_path: Path, new_filename: str) -> Optional[str]:
        """
        Upload a local file to Notion using the official File Upload API (single-part).
        Returns the File Upload ID (NOT a final CDN URL). You attach this ID to a page/block/property.
        """
        try:
            if not file_path.exists():
                raise FileNotFoundError(str(file_path))

            # If you want strict enforcement: Direct Upload single-part is for files <= 20MB (per Notion docs guide).
            # You can choose to branch to multi_part for larger files.
            size_bytes = file_path.stat().st_size

            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Notion-Version": NOTION_VERSION,
            }

            with httpx.Client(timeout=60) as client:
                # 1) Create file upload
                create_resp = client.post(
                    "https://api.notion.com/v1/file_uploads",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "mode": "single_part",
                        "filename": new_filename,              # recommended
                        "content_type": "application/pdf",     # set appropriately
                    },
                )
                create_resp.raise_for_status()
                upload_obj = create_resp.json()

                file_upload_id = upload_obj["id"]
                upload_url = upload_obj["upload_url"]  # typically .../v1/file_uploads/{id}/send

                # 2) Send file bytes (multipart/form-data)
                # IMPORTANT: Let httpx set the multipart boundary. Do NOT manually set Content-Type.
                with file_path.open("rb") as f:
                    send_resp = client.post(
                        upload_url,
                        headers=headers,
                        files={
                            "file": (new_filename, f, "application/pdf")
                        },
                    )
                send_resp.raise_for_status()
                send_obj = send_resp.json()


                # Optional: verify status is uploaded (it should be for single_part)
                if send_obj.get("status") != "uploaded":
                    # Defensive polling (usually unnecessary for single_part)
                    for _ in range(10):
                        time.sleep(0.5)
                        r: Response = client.get(
                            f"https://api.notion.com/v1/file_uploads/{file_upload_id}",
                            headers=headers,
                        )
                        r.raise_for_status()
                        if r.json().get("status") == "uploaded":
                            break

                

                return file_upload_id

        except Exception as e:
            print(f"Warning: Failed to upload file to Notion: {e}")
            return None
    
    def create_expense_entry(
        self,
        merchant_description: str,
        date: datetime,
        amount: float,
        paid_by: str,
        receipt_file_path: Optional[Path] = None,
        receipt_filename: Optional[str] = None
    ) -> str:
        """
        Create an entry in the Expense Table.
        Returns the page ID of the created entry.
        """
        properties = {
            "Merchant / Description": {
                "title": [
                    {
                        "text": {
                            "content": merchant_description
                        }
                    }
                ]
            },
            "Date": {
                "date": {
                    "start": date.strftime('%Y-%m-%d')
                }
            },
            "Amount": {
                "number": amount
            },
            "Paid By": {
                "people": [
                    {
                        "object": "user",
                        "id": self._get_user_id(person_name=paid_by)
                    }
                ]
            },
            "Paid": {
                "number": 0.0
            }
        }
        
        # Upload file to Notion if provided
        if receipt_file_path and receipt_filename:
            file_id = self._upload_file_to_notion(receipt_file_path, receipt_filename)
            
            if file_id:
                properties["Receipt (optional)"] = {
                    "files": [
                        {
                            "name": receipt_filename,
                            "file_upload": {
                                "id": file_id
                            }
                        }
                    ]
                }
        
        try:
            response = self.client.pages.create(
                parent={"database_id": self.expense_db_id},
                properties=properties
            )
            return response["id"]
        except APIResponseError as e:
            raise Exception(f"Failed to create expense entry: {e}")
    
    def create_split_entry(
        self,
        title: str,
        person: str,
        share_percent: float,
        expense_page_id: str
    ) -> str:
        """
        Create an entry in the Split Details Table.
        Returns the page ID of the created entry.
        """
        properties = {
            "Title": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            },
            "Person": {
                "people": [
                    {
                        "object": "user",
                        "id": self._get_user_id(person_name=person)
                    }
                ]
            },
            "Share Percent": {
                "number": share_percent / 100
            }
        }
        
        try:
            response = self.client.pages.create(
                parent={"database_id": self.split_db_id},
                properties=properties
            )
            split_page_id = response["id"]
            
            # Link the split entry to the expense entry (critical: orphaned split is a data integrity issue)
            self._link_pages(source_page_id=expense_page_id, target_page_id=split_page_id, table_name=Config.EXPENSE_RELATION_PROPERTY, critical=True)

            # Link the split entry to the balance entry (non-critical: warn only)
            self._link_pages(source_page_id=self.balance_page_id, target_page_id=split_page_id, table_name=Config.BALANCES_RELATION_PROPERTY, critical=False)
            
            return split_page_id
        except APIResponseError as e:
            raise Exception(f"Failed to create split entry: {e}")
    
    def _link_pages(self, source_page_id: str, target_page_id: str, table_name: str, critical: bool = False):
        """Append target_page_id to the relation property `table_name` on source_page_id, deduplicating existing entries.

        Args:
            critical: If True, re-raises APIResponseError on failure instead of only warning.
        """
        try:
            # Get existing relations
            page = self.client.pages.retrieve(page_id=source_page_id)
            existing_relations = page["properties"][table_name]["relation"]

            # Avoid duplicates
            existing_ids = {r["id"] for r in existing_relations}
            if target_page_id not in existing_ids:
                existing_relations.append({"id": target_page_id})

            # Send full updated list
            self.client.pages.update(
                page_id=source_page_id,
                properties={
                    table_name: {
                        "relation": existing_relations
                    }
                }
            )
        except (APIResponseError, KeyError) as e:
            if critical:
                raise Exception(f"Failed to link source page {source_page_id} to target page {target_page_id}: {e}")
            print(f"Warning: Failed to link source page {source_page_id} to target page {target_page_id}: {e}")
    
    def generate_split_title(
        self,
        person_name: str,
        merchant_name: str,
        description: str,
        date: datetime
    ) -> str:
        """
        Generate a split title following the pattern from CSV examples.
        Pattern: "[Person]'s [Merchant] [Type] Split ([Details])"
        """
        # Extract category/type from merchant name
        merchant_lower = merchant_name.lower()
        
        if 'walmart' in merchant_lower:
            category = 'Walmart Food Split'
        elif 'amazon' in merchant_lower:
            category = 'Amazon Order Split' if 'order' in merchant_lower else 'Amazon Split'
        elif 'electrical' in merchant_lower or 'electric' in merchant_lower:
            month = date.strftime('%b')
            return f"{person_name}'s Electrical Bill Split ({month})"
        elif 'rent' in merchant_lower:
            month = date.strftime('%b')
            return f"{person_name}'s Rent Split ({month})"
        elif 'netflix' in merchant_lower:
            month = date.strftime('%b')
            return f"{person_name}'s Netflix Payment ({month})"
        elif 'youtube' in merchant_lower or 'yt' in merchant_lower:
            month = date.strftime('%b')
            return f"{person_name}'s YT Premium Split ({month})"
        elif 'parking' in merchant_lower:
            month = date.strftime('%b')
            return f"{person_name}'s Parking Share ({month})"
        elif 'longo' in merchant_lower:
            return f"{person_name}'s Longo's Groceries Share"
        elif 'tv' in merchant_lower:
            month = date.strftime('%b')
            return f"{person_name}'s TV Payment ({month})"
        else:
            category = f"{merchant_name} Split"
        
        # Extract details from description (text in parentheses)
        details = ''
        if '(' in description and ')' in description:
            start = description.index('(') + 1
            end = description.index(')')
            details = description[start:end]
        
        if details:
            return f"{person_name}'s {category} ({details})"
        else:
            return f"{person_name}'s {category}"
    
    def test_connection(self) -> bool:
        """Test the Notion API connection and database access."""
        try:
            # Try to retrieve database info
            self.client.databases.retrieve(database_id=self.expense_db_id)
            self.client.databases.retrieve(database_id=self.split_db_id)
            self.client.pages.retrieve(page_id=self.balance_page_id)
            return True
        except APIResponseError as e:
            print(f"Notion API connection test failed: {e}")
            return False

# Made with Bob
