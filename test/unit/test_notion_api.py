"""
Unit tests for notion_api.py
Tests Notion API request building and response handling with mocked HTTP calls.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime
from pathlib import Path
from notion_client.errors import APIResponseError, APIErrorCode
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from src.notion_api import NotionExpenseClient
from src.config import Config


@pytest.fixture
def notion_client():
    """Create a NotionExpenseClient instance with mocked Notion client and config"""
    with patch('src.notion_api.Client') as mock_client:
        with patch('src.config.Config.YOUR_NAME', 'Alice'):
            with patch('src.config.Config.PARTNER_NAME', 'Bob'):
                with patch('src.config.Config.YOUR_USER_ID', 'user-id-alice'):
                    with patch('src.config.Config.PARTNER_USER_ID', 'user-id-bob'):
                        with patch('src.config.Config.EXPENSE_RELATION_PROPERTY', 'Split Details Table'):
                            with patch('src.config.Config.BALANCES_RELATION_PROPERTY', 'Split Details Table'):
                                client = NotionExpenseClient(
                                    api_token="test_token",
                                    expense_db_id="expense_db_id",
                                    split_db_id="split_db_id",
                                    balance_page_id="balance_page_id"
                                )
                                client.client = mock_client.return_value
                                # Manually set the user_id_map since Config is patched
                                client.user_id_map = {
                                    'Alice': 'user-id-alice',
                                    'Bob': 'user-id-bob'
                                }
                                yield client
from pathlib import Path

from src.notion_api import NotionExpenseClient
from src.config import Config


@pytest.mark.unit
class TestEmojiMappings:
    """Test emoji mapping functionality"""
    
    def test_get_merchant_emoji_amazon(self):
        """Test emoji for Amazon merchant"""
        emoji = Config.get_merchant_emoji("Amazon Order")
        assert emoji == '🛒'
    
    def test_get_merchant_emoji_walmart(self):
        """Test emoji for Walmart merchant"""
        emoji = Config.get_merchant_emoji("Walmart Groceries")
        assert emoji == '🛒'
    
    def test_get_merchant_emoji_restaurant(self):
        """Test emoji for restaurant"""
        emoji = Config.get_merchant_emoji("McDonald's")
        assert emoji == '🍔'
    
    def test_get_merchant_emoji_coffee(self):
        """Test emoji for coffee shop"""
        emoji = Config.get_merchant_emoji("Starbucks")
        assert emoji == '☕'
    
    def test_get_merchant_emoji_gas(self):
        """Test emoji for gas station"""
        emoji = Config.get_merchant_emoji("Shell Gas Station")
        assert emoji == '⛽'
    
    def test_get_merchant_emoji_pharmacy(self):
        """Test emoji for pharmacy"""
        emoji = Config.get_merchant_emoji("Shoppers Drug Mart")
        assert emoji == '🏥'
    
    def test_get_merchant_emoji_entertainment(self):
        """Test emoji for entertainment"""
        emoji = Config.get_merchant_emoji("Netflix Subscription")
        assert emoji == '🎬'
    
    def test_get_merchant_emoji_utilities(self):
        """Test emoji for utilities"""
        emoji = Config.get_merchant_emoji("Electrical Bill")
        assert emoji == '⚡'
    
    def test_get_merchant_emoji_rent(self):
        """Test emoji for rent"""
        emoji = Config.get_merchant_emoji("Monthly Rent")
        assert emoji == '🏠'
    
    def test_get_merchant_emoji_parking(self):
        """Test emoji for parking"""
        emoji = Config.get_merchant_emoji("Parking Fee")
        assert emoji == '🅿️'
    
    def test_get_merchant_emoji_unknown(self):
        """Test default emoji for unknown merchant"""
        emoji = Config.get_merchant_emoji("Unknown Store XYZ")
        assert emoji == '💳'
    
    def test_get_merchant_emoji_case_insensitive(self):
        """Test that merchant matching is case insensitive"""
        emoji1 = Config.get_merchant_emoji("AMAZON")
        emoji2 = Config.get_merchant_emoji("amazon")
        emoji3 = Config.get_merchant_emoji("Amazon")
        assert emoji1 == emoji2 == emoji3 == '🛒'
    
    def test_get_person_emoji_your_name(self):
        """Test emoji for YOUR_NAME from config"""
        emoji = Config.get_person_emoji(Config.YOUR_NAME)
        assert emoji == Config.YOUR_EMOJI
    
    def test_get_person_emoji_partner_name(self):
        """Test emoji for PARTNER_NAME from config"""
        emoji = Config.get_person_emoji(Config.PARTNER_NAME)
        assert emoji == Config.PARTNER_EMOJI
    
    def test_get_person_emoji_your_name_case_insensitive(self):
        """Test that YOUR_NAME matching is case insensitive"""
        emoji1 = Config.get_person_emoji(Config.YOUR_NAME.upper())
        emoji2 = Config.get_person_emoji(Config.YOUR_NAME.lower())
        emoji3 = Config.get_person_emoji(Config.YOUR_NAME)
        assert emoji1 == emoji2 == emoji3 == Config.YOUR_EMOJI
    
    def test_get_person_emoji_partner_name_case_insensitive(self):
        """Test that PARTNER_NAME matching is case insensitive"""
        emoji1 = Config.get_person_emoji(Config.PARTNER_NAME.upper())
        emoji2 = Config.get_person_emoji(Config.PARTNER_NAME.lower())
        emoji3 = Config.get_person_emoji(Config.PARTNER_NAME)
        assert emoji1 == emoji2 == emoji3 == Config.PARTNER_EMOJI
    
    def test_get_person_emoji_boyfriend(self):
        """Test emoji for boyfriend keyword"""
        emoji = Config.get_person_emoji("boyfriend")
        assert emoji == '👦'
    
    def test_get_person_emoji_girlfriend(self):
        """Test emoji for girlfriend keyword"""
        emoji = Config.get_person_emoji("girlfriend")
        assert emoji == '👩🏾'
    
    def test_get_person_emoji_partner_keyword(self):
        """Test emoji for partner keyword"""
        emoji = Config.get_person_emoji("partner")
        assert emoji == '💑'
    
    def test_get_person_emoji_me(self):
        """Test emoji for me keyword"""
        emoji = Config.get_person_emoji("me")
        assert emoji == '👤'
    
    def test_get_person_emoji_unknown(self):
        """Test default emoji for unknown person"""
        emoji = Config.get_person_emoji("Random Person XYZ")
        assert emoji == '👤'
    
    def test_get_person_emoji_keyword_case_insensitive(self):
        """Test that keyword matching is case insensitive"""
        emoji1 = Config.get_person_emoji("BOYFRIEND")
        emoji2 = Config.get_person_emoji("boyfriend")
        emoji3 = Config.get_person_emoji("Boyfriend")
        assert emoji1 == emoji2 == emoji3 == '👦'


@pytest.mark.unit
class TestNotionExpenseClient:
    """Test Notion API interaction logic"""
    
    @patch('src.notion_api.Client')
    def test_create_expense_entry_includes_emoji(self, mock_client):
        """Test that expense entry includes emoji icon"""
        # Setup mock
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.pages.create.return_value = {"id": "test-page-id"}
        
        # Create client
        client = NotionExpenseClient(
            api_token="test-token",
            expense_db_id="test-expense-db",
            split_db_id="test-split-db",
            balance_page_id="test-balance-page"
        )
        
        # Create expense entry
        page_id = client.create_expense_entry(
            merchant_description="Amazon Order",
            date=datetime(2026, 3, 10),
            amount=50.00,
            paid_by=Config.YOUR_NAME
        )
        
        # Verify the call included emoji
        call_args = mock_instance.pages.create.call_args
        assert call_args is not None
        assert 'icon' in call_args.kwargs
        assert call_args.kwargs['icon']['type'] == 'emoji'
        assert call_args.kwargs['icon']['emoji'] == '🛒'
        assert page_id == "test-page-id"
    
    @patch('src.notion_api.Client')
    def test_create_split_entry_includes_emoji(self, mock_client):
        """Test that split entry includes emoji icon"""
        # Setup mock
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.pages.create.return_value = {"id": "test-split-id"}
        mock_instance.pages.retrieve.return_value = {
            "properties": {
                Config.EXPENSE_RELATION_PROPERTY: {"relation": []},
                Config.BALANCES_RELATION_PROPERTY: {"relation": []}
            }
        }
        mock_instance.pages.update.return_value = {}
        
        # Create client
        client = NotionExpenseClient(
            api_token="test-token",
            expense_db_id="test-expense-db",
            split_db_id="test-split-db",
            balance_page_id="test-balance-page"
        )
        
        # Create split entry
        split_id = client.create_split_entry(
            title="Test Split",
            person=Config.PARTNER_NAME,
            share_percent=50.0,
            expense_page_id="test-expense-id"
        )
        
        # Verify the call included emoji
        call_args = mock_instance.pages.create.call_args
        assert call_args is not None
        assert 'icon' in call_args.kwargs
        assert call_args.kwargs['icon']['type'] == 'emoji'
        # The emoji depends on PARTNER_NAME, which defaults to 'Partner'
        # 'Partner' contains 'partner' which maps to '💑'
        expected_emoji = Config.get_person_emoji(Config.PARTNER_NAME)
        assert call_args.kwargs['icon']['emoji'] == expected_emoji
        assert split_id == "test-split-id"
    
    def test_init(self):
        """Test NotionExpenseClient initialization"""
        with patch('src.notion_api.Client') as mock_client:
            with patch('src.notion_api.Config.YOUR_NAME', 'Alice'):
                with patch('src.notion_api.Config.PARTNER_NAME', 'Bob'):
                    with patch('src.notion_api.Config.YOUR_USER_ID', 'user-id-alice'):
                        with patch('src.notion_api.Config.PARTNER_USER_ID', 'user-id-bob'):
                            client = NotionExpenseClient(
                                api_token="test_token",
                                expense_db_id="expense_db",
                                split_db_id="split_db",
                                balance_page_id="balance_page"
                            )
                            
                            assert client.api_token == "test_token"
                            assert client.expense_db_id == "expense_db"
                            assert client.split_db_id == "split_db"
                            assert client.balance_page_id == "balance_page"
                            assert client.user_id_map == {
                                'Alice': 'user-id-alice',
                                'Bob': 'user-id-bob'
                            }
                            mock_client.assert_called_once_with(auth="test_token")
    
    def test_get_user_id_valid(self, notion_client):
        """Test getting user ID for valid person name"""
        user_id = notion_client._get_user_id("Alice")
        assert user_id == "user-id-alice"
        
        user_id = notion_client._get_user_id("Bob")
        assert user_id == "user-id-bob"
    
    def test_get_user_id_invalid(self, notion_client):
        """Test getting user ID for invalid person name raises ValueError"""
        with pytest.raises(ValueError, match="No user ID found for person: Charlie"):
            notion_client._get_user_id("Charlie")
    
    def test_get_username_from_id_success(self, notion_client):
        """Test successful username retrieval from user ID"""
        notion_client.client.users.retrieve.return_value = {
            "id": "user-id-alice",
            "name": "Alice Smith"
        }
        
        username = notion_client.get_username_from_id("user-id-alice")
        assert username == "Alice Smith"
        notion_client.client.users.retrieve.assert_called_once_with(user_id="user-id-alice")
    
    def test_get_username_from_id_no_name(self, notion_client):
        """Test username retrieval when API returns no name"""
        notion_client.client.users.retrieve.return_value = {
            "id": "user-id-alice"
        }
        
        username = notion_client.get_username_from_id("user-id-alice")
        assert username == "user-id-alice"
    
    def test_get_username_from_id_api_error_fallback_to_map(self, notion_client):
        """Test username retrieval falls back to local map on API error"""
        notion_client.client.users.retrieve.side_effect = Exception("API Error")
        
        username = notion_client.get_username_from_id("user-id-alice")
        assert username == "Alice"
    
    def test_get_username_from_id_api_error_fallback_to_id(self, notion_client):
        """Test username retrieval falls back to user ID when not in map"""
        notion_client.client.users.retrieve.side_effect = Exception("API Error")
        
        username = notion_client.get_username_from_id("unknown-user-id")
        assert username == "unknown-user-id"
    
    @patch('src.notion_api.httpx.Client')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.open', new_callable=mock_open, read_data=b'PDF content')
    def test_upload_file_to_notion_success(self, mock_file, mock_stat, mock_exists, mock_httpx, notion_client):
        """Test successful file upload to Notion"""
        mock_exists.return_value = True
        mock_stat.return_value = Mock(st_size=1024)
        
        # Mock httpx client
        mock_client_instance = MagicMock()
        mock_httpx.return_value.__enter__.return_value = mock_client_instance
        
        # Mock create response
        create_response = Mock()
        create_response.raise_for_status = Mock()
        create_response.json.return_value = {
            "id": "file-upload-id-123",
            "upload_url": "https://api.notion.com/v1/file_uploads/file-upload-id-123/send"
        }
        
        # Mock send response
        send_response = Mock()
        send_response.raise_for_status = Mock()
        send_response.json.return_value = {"status": "uploaded"}
        
        # Set up post to return different responses
        mock_client_instance.post.side_effect = [create_response, send_response]
        
        file_path = Path("/test/receipt.pdf")
        result = notion_client._upload_file_to_notion(file_path, "receipt.pdf")
        
        assert result == "file-upload-id-123"
    
    @patch('pathlib.Path.exists')
    def test_upload_file_to_notion_file_not_found(self, mock_exists, notion_client):
        """Test file upload when file doesn't exist"""
        mock_exists.return_value = False
        
        file_path = Path("/test/nonexistent.pdf")
        result = notion_client._upload_file_to_notion(file_path, "receipt.pdf")
        
        assert result is None
    
    @patch('src.notion_api.httpx.Client')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    def test_upload_file_to_notion_api_error(self, mock_stat, mock_exists, mock_httpx, notion_client):
        """Test file upload handles API errors gracefully"""
        mock_exists.return_value = True
        mock_stat.return_value = Mock(st_size=1024)
        
        mock_client_instance = MagicMock()
        mock_httpx.return_value.__enter__.return_value = mock_client_instance
        mock_client_instance.post.side_effect = Exception("API Error")
        
        file_path = Path("/test/receipt.pdf")
        result = notion_client._upload_file_to_notion(file_path, "receipt.pdf")
        
        assert result is None
    
    def test_create_expense_entry_without_receipt(self, notion_client):
        """Test creating expense entry without receipt file"""
        notion_client.client.pages.create.return_value = {"id": "expense-page-id"}
        
        page_id = notion_client.create_expense_entry(
            merchant_description="Walmart Groceries",
            date=datetime(2026, 3, 10),
            amount=85.50,
            paid_by="Alice"
        )
        
        assert page_id == "expense-page-id"
        
        # Verify the call
        call_args = notion_client.client.pages.create.call_args
        assert call_args[1]["parent"]["database_id"] == "expense_db_id"
        
        properties = call_args[1]["properties"]
        assert properties["Merchant / Description"]["title"][0]["text"]["content"] == "Walmart Groceries"
        assert properties["Date"]["date"]["start"] == "2026-03-10"
        assert properties["Amount"]["number"] == 85.50
        assert properties["Paid By"]["people"][0]["id"] == "user-id-alice"
        assert properties["Paid"]["number"] == 0.0
        assert "Receipt (optional)" not in properties
    
    @patch.object(NotionExpenseClient, '_upload_file_to_notion')
    def test_create_expense_entry_with_receipt(self, mock_upload, notion_client):
        """Test creating expense entry with receipt file"""
        mock_upload.return_value = "file-upload-id-123"
        notion_client.client.pages.create.return_value = {"id": "expense-page-id"}
        
        receipt_path = Path("/test/receipt.pdf")
        page_id = notion_client.create_expense_entry(
            merchant_description="Amazon Order",
            date=datetime(2026, 3, 7),
            amount=49.60,
            paid_by="Bob",
            receipt_file_path=receipt_path,
            receipt_filename="2026-03-07_Amazon_Order.pdf"
        )
        
        assert page_id == "expense-page-id"
        mock_upload.assert_called_once_with(receipt_path, "2026-03-07_Amazon_Order.pdf")
        
        # Verify receipt was added to properties
        call_args = notion_client.client.pages.create.call_args
        properties = call_args[1]["properties"]
        assert "Receipt (optional)" in properties
        assert properties["Receipt (optional)"]["files"][0]["name"] == "2026-03-07_Amazon_Order.pdf"
        assert properties["Receipt (optional)"]["files"][0]["file_upload"]["id"] == "file-upload-id-123"
    
    @patch.object(NotionExpenseClient, '_upload_file_to_notion')
    def test_create_expense_entry_with_failed_upload(self, mock_upload, notion_client):
        """Test creating expense entry when file upload fails"""
        mock_upload.return_value = None  # Upload failed
        notion_client.client.pages.create.return_value = {"id": "expense-page-id"}
        
        receipt_path = Path("/test/receipt.pdf")
        page_id = notion_client.create_expense_entry(
            merchant_description="Amazon Order",
            date=datetime(2026, 3, 7),
            amount=49.60,
            paid_by="Bob",
            receipt_file_path=receipt_path,
            receipt_filename="2026-03-07_Amazon_Order.pdf"
        )
        
        assert page_id == "expense-page-id"
        
        # Verify receipt was NOT added to properties
        call_args = notion_client.client.pages.create.call_args
        properties = call_args[1]["properties"]
        assert "Receipt (optional)" not in properties
    
    def test_create_expense_entry_api_error(self, notion_client):
        """Test expense entry creation handles API errors"""
        mock_response = Mock()
        mock_response.status_code = 400
        notion_client.client.pages.create.side_effect = APIResponseError(
            response=mock_response,
            message="Bad Request",
            code=APIErrorCode.ValidationError
        )
        
        with pytest.raises(Exception, match="Failed to create expense entry"):
            notion_client.create_expense_entry(
                merchant_description="Test",
                date=datetime(2026, 3, 10),
                amount=100.0,
                paid_by="Alice"
            )
    
    @patch.object(NotionExpenseClient, '_link_pages')
    def test_create_split_entry_success(self, mock_link, notion_client):
        """Test successful split entry creation"""
        notion_client.client.pages.create.return_value = {"id": "split-page-id"}
        
        page_id = notion_client.create_split_entry(
            title="Alice's Walmart Food Split",
            person="Alice",
            share_percent=50.0,
            expense_page_id="expense-page-id"
        )
        
        assert page_id == "split-page-id"
        
        # Verify the call
        call_args = notion_client.client.pages.create.call_args
        properties = call_args[1]["properties"]
        assert properties["Title"]["title"][0]["text"]["content"] == "Alice's Walmart Food Split"
        assert properties["Person"]["people"][0]["id"] == "user-id-alice"
        assert properties["Share Percent"]["number"] == 0.5
        
        # Verify linking was called
        assert mock_link.call_count == 2
        mock_link.assert_any_call(
            source_page_id="expense-page-id",
            target_page_id="split-page-id",
            table_name="Split Details Table",
            critical=True
        )
        mock_link.assert_any_call(
            source_page_id="balance_page_id",
            target_page_id="split-page-id",
            table_name="Split Details Table",
            critical=False
        )
    
    def test_create_split_entry_api_error(self, notion_client):
        """Test split entry creation handles API errors"""
        mock_response = Mock()
        mock_response.status_code = 400
        notion_client.client.pages.create.side_effect = APIResponseError(
            response=mock_response,
            message="Bad Request",
            code=APIErrorCode.ValidationError
        )
        
        with pytest.raises(Exception, match="Failed to create split entry"):
            notion_client.create_split_entry(
                title="Test Split",
                person="Alice",
                share_percent=50.0,
                expense_page_id="expense-page-id"
            )
    
    def test_link_pages_success(self, notion_client):
        """Test successful page linking"""
        notion_client.client.pages.retrieve.return_value = {
            "properties": {
                "Split Details Table": {
                    "relation": [{"id": "existing-page-id"}]
                }
            }
        }
        
        notion_client._link_pages(
            source_page_id="source-page",
            target_page_id="target-page",
            table_name="Split Details Table",
            critical=False
        )
        
        # Verify retrieve was called
        notion_client.client.pages.retrieve.assert_called_once_with(page_id="source-page")
        
        # Verify update was called with both existing and new relation
        call_args = notion_client.client.pages.update.call_args
        assert call_args[1]["page_id"] == "source-page"
        relations = call_args[1]["properties"]["Split Details Table"]["relation"]
        assert len(relations) == 2
        assert {"id": "existing-page-id"} in relations
        assert {"id": "target-page"} in relations
    
    def test_link_pages_deduplication(self, notion_client):
        """Test page linking deduplicates existing relations"""
        notion_client.client.pages.retrieve.return_value = {
            "properties": {
                "Split Details Table": {
                    "relation": [{"id": "target-page"}]
                }
            }
        }
        
        notion_client._link_pages(
            source_page_id="source-page",
            target_page_id="target-page",
            table_name="Split Details Table",
            critical=False
        )
        
        # Verify update was called with only one relation (no duplicate)
        call_args = notion_client.client.pages.update.call_args
        relations = call_args[1]["properties"]["Split Details Table"]["relation"]
        assert len(relations) == 1
        assert {"id": "target-page"} in relations
    
    def test_link_pages_non_critical_error(self, notion_client, capsys):
        """Test non-critical page linking handles errors gracefully"""
        mock_response = Mock()
        mock_response.status_code = 404
        notion_client.client.pages.retrieve.side_effect = APIResponseError(
            response=mock_response,
            message="Not Found",
            code=APIErrorCode.ObjectNotFound
        )
        
        # Should not raise exception
        notion_client._link_pages(
            source_page_id="source-page",
            target_page_id="target-page",
            table_name="Split Details Table",
            critical=False
        )
        
        # Verify warning was printed
        captured = capsys.readouterr()
        assert "Warning: Failed to link" in captured.out
    
    def test_link_pages_critical_error(self, notion_client):
        """Test critical page linking raises exception on error"""
        mock_response = Mock()
        mock_response.status_code = 404
        notion_client.client.pages.retrieve.side_effect = APIResponseError(
            response=mock_response,
            message="Not Found",
            code=APIErrorCode.ObjectNotFound
        )
        
        with pytest.raises(Exception, match="Failed to link source page"):
            notion_client._link_pages(
                source_page_id="source-page",
                target_page_id="target-page",
                table_name="Split Details Table",
                critical=True
            )
    
    def test_generate_split_title_walmart(self, notion_client):
        """Test split title generation for Walmart"""
        title = notion_client.generate_split_title(
            person_name="Alice",
            merchant_name="Walmart",
            description="Groceries (Meatballs)",
            date=datetime(2026, 3, 10)
        )
        assert title == "Alice's Walmart Food Split (Meatballs)"
    
    def test_generate_split_title_amazon(self, notion_client):
        """Test split title generation for Amazon"""
        title = notion_client.generate_split_title(
            person_name="Bob",
            merchant_name="Amazon Order",
            description="Kitchen supplies (Baking Sheets)",
            date=datetime(2026, 3, 7)
        )
        assert title == "Bob's Amazon Order Split (Baking Sheets)"
    
    def test_generate_split_title_electrical(self, notion_client):
        """Test split title generation for electrical bill"""
        title = notion_client.generate_split_title(
            person_name="Alice",
            merchant_name="Electrical Company",
            description="Monthly bill",
            date=datetime(2026, 3, 10)
        )
        assert title == "Alice's Electrical Bill Split (Mar)"
    
    def test_generate_split_title_rent(self, notion_client):
        """Test split title generation for rent"""
        title = notion_client.generate_split_title(
            person_name="Bob",
            merchant_name="Rent Payment",
            description="Monthly rent",
            date=datetime(2026, 2, 1)
        )
        assert title == "Bob's Rent Split (Feb)"
    
    def test_generate_split_title_netflix(self, notion_client):
        """Test split title generation for Netflix"""
        title = notion_client.generate_split_title(
            person_name="Alice",
            merchant_name="Netflix",
            description="Subscription",
            date=datetime(2026, 1, 15)
        )
        assert title == "Alice's Netflix Payment (Jan)"
    
    def test_generate_split_title_youtube(self, notion_client):
        """Test split title generation for YouTube Premium"""
        title = notion_client.generate_split_title(
            person_name="Bob",
            merchant_name="YouTube Premium",
            description="Subscription",
            date=datetime(2026, 3, 10)
        )
        assert title == "Bob's YT Premium Split (Mar)"
    
    def test_generate_split_title_parking(self, notion_client):
        """Test split title generation for parking"""
        title = notion_client.generate_split_title(
            person_name="Alice",
            merchant_name="Parking Garage",
            description="Monthly parking",
            date=datetime(2026, 3, 10)
        )
        assert title == "Alice's Parking Share (Mar)"
    
    def test_generate_split_title_longos(self, notion_client):
        """Test split title generation for Longo's"""
        title = notion_client.generate_split_title(
            person_name="Bob",
            merchant_name="Longo's",
            description="Groceries",
            date=datetime(2026, 3, 10)
        )
        assert title == "Bob's Longo's Groceries Share"
    
    def test_generate_split_title_tv(self, notion_client):
        """Test split title generation for TV payment"""
        title = notion_client.generate_split_title(
            person_name="Alice",
            merchant_name="TV Service",
            description="Cable bill",
            date=datetime(2026, 3, 10)
        )
        assert title == "Alice's TV Payment (Mar)"
    
    def test_generate_split_title_generic(self, notion_client):
        """Test split title generation for generic merchant"""
        title = notion_client.generate_split_title(
            person_name="Bob",
            merchant_name="Generic Store",
            description="Purchase",
            date=datetime(2026, 3, 10)
        )
        assert title == "Bob's Generic Store Split"
    
    def test_generate_split_title_generic_with_details(self, notion_client):
        """Test split title generation for generic merchant with details"""
        title = notion_client.generate_split_title(
            person_name="Alice",
            merchant_name="Hardware Store",
            description="Tools (Hammer and Nails)",
            date=datetime(2026, 3, 10)
        )
        assert title == "Alice's Hardware Store Split (Hammer and Nails)"
    
    def test_test_connection_success(self, notion_client):
        """Test successful connection test"""
        notion_client.client.databases.retrieve.return_value = {"id": "db-id"}
        notion_client.client.pages.retrieve.return_value = {"id": "page-id"}
        
        result = notion_client.test_connection()
        assert result is True
        
        # Verify all three retrievals were called
        assert notion_client.client.databases.retrieve.call_count == 2
        notion_client.client.pages.retrieve.assert_called_once_with(page_id="balance_page_id")
    
    def test_test_connection_failure(self, notion_client, capsys):
        """Test connection test handles failures"""
        mock_response = Mock()
        mock_response.status_code = 401
        notion_client.client.databases.retrieve.side_effect = APIResponseError(
            response=mock_response,
            message="Unauthorized",
            code=APIErrorCode.Unauthorized
        )
        
        result = notion_client.test_connection()
        assert result is False
        
        # Verify error message was printed
        captured = capsys.readouterr()
        assert "Notion API connection test failed" in captured.out


