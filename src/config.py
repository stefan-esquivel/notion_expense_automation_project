"""Configuration management for the expense automation system."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration."""
    
    # Notion API
    NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
    EXPENSE_TABLE_DATABASE_ID = os.getenv('EXPENSE_TABLE_DATABASE_ID')
    SPLIT_DETAILS_DATABASE_ID = os.getenv('SPLIT_DETAILS_DATABASE_ID')
    BALANCES_PAGE_ID = os.getenv('BALANCES_PAGE_ID')
    
    # User Configuration
    YOUR_NAME = os.getenv('YOUR_NAME', 'You')
    PARTNER_NAME = os.getenv('PARTNER_NAME', 'Partner')
    YOUR_EMOJI = os.getenv('YOUR_EMOJI', '👤')
    PARTNER_EMOJI = os.getenv('PARTNER_EMOJI', '👤')
    YOUR_USER_ID = os.getenv('YOUR_USER_ID', 'a20139cd-f446-493b-936f-05cf7f715835')
    PARTNER_USER_ID = os.getenv('PARTNER_USER_ID', 'a9e310cd-1c5b-4cea-8bad-7381b60d7144')
    
    # File Paths
    PROJECT_ROOT = Path(__file__).parent.parent
    INPUT_FOLDER = PROJECT_ROOT / os.getenv('INPUT_FOLDER', 'receipts/input')
    PROCESSED_FOLDER = PROJECT_ROOT / os.getenv('PROCESSED_FOLDER', 'receipts/processed')
    LOG_FOLDER = PROJECT_ROOT / 'logs'
    
    # Split Configuration
    DEFAULT_SPLIT_PERCENTAGE = float(os.getenv('DEFAULT_SPLIT_PERCENTAGE', '50.0'))
    
    # Notion relation property names
    EXPENSE_RELATION_PROPERTY = "Split Details Table"   # relation property name on Expense Table pages
    BALANCES_RELATION_PROPERTY = "Split Details Table"  # relation property name on Balances page

    # Emoji Mappings for Merchants
    MERCHANT_EMOJIS = {
        # Shopping
        'amazon': '🛒',
        'walmart': '🛒',
        'costco': '🛒',
        'target': '🛒',
        'bestbuy': '🛒',
        'best buy': '🛒',
        
        # Food & Restaurants
        'mcdonalds': '🍔',
        'mcdonald': '🍔',
        'burger': '🍔',
        'pizza': '🍕',
        'restaurant': '🍽️',
        'starbucks': '☕',
        'coffee': '☕',
        'tim hortons': '☕',
        'subway': '🥪',
        
        # Groceries
        'longo': '🛒',
        'longos': '🛒',
        'grocery': '🛒',
        'supermarket': '🛒',
        
        # Gas Stations
        'shell': '⛽',
        'esso': '⛽',
        'petro': '⛽',
        'gas': '⛽',
        'fuel': '⛽',
        
        # Healthcare
        'pharmacy': '🏥',
        'shoppers': '🏥',
        'rexall': '🏥',
        'medical': '🏥',
        'doctor': '🏥',
        'hospital': '🏥',
        
        # Entertainment
        'netflix': '🎬',
        'youtube': '🎬',
        'yt': '🎬',
        'movie': '🎬',
        'cinema': '🎬',
        'spotify': '🎵',
        'music': '🎵',
        
        # Utilities & Bills
        'electrical': '⚡',
        'electric': '⚡',
        'hydro': '⚡',
        'internet': '🌐',
        'phone': '📱',
        'tv': '📺',
        
        # Housing
        'rent': '🏠',
        'parking': '🅿️',
        
        # Office & Business
        'staples': '💼',
        'office': '💼',
        'business': '💼',
    }
    
    # Emoji Mappings for Split Persons (configurable)
    PERSON_EMOJIS = {
        'boyfriend': '👦',
        'girlfriend': '👩🏾',
        'partner': '💑',
        'me': '👤',
        'group': '👥',
    }
    
    @classmethod
    def get_merchant_emoji(cls, merchant_name: str) -> str:
        """Get emoji for a merchant based on name matching.
        
        Args:
            merchant_name: The merchant/description name
            
        Returns:
            Emoji string, defaults to 💳 if no match found
        """
        merchant_lower = merchant_name.lower()
        
        # Check for exact or partial matches
        for keyword, emoji in cls.MERCHANT_EMOJIS.items():
            if keyword in merchant_lower:
                return emoji
        
        # Default emoji for unknown merchants
        return '💳'
    
    @classmethod
    def get_person_emoji(cls, person_name: str) -> str:
        """Get emoji for a person based on name or relationship.
        
        Priority order:
        1. Check if person_name matches YOUR_NAME -> return YOUR_EMOJI
        2. Check if person_name matches PARTNER_NAME -> return PARTNER_EMOJI
        3. Check PERSON_EMOJIS dictionary for keyword matches
        4. Return default emoji 👤
        
        Args:
            person_name: The person's name
            
        Returns:
            Emoji string, defaults to 👤 if no match found
        """
        # Check for exact or case-insensitive match with configured names
        if person_name.lower() == cls.YOUR_NAME.lower():
            return cls.YOUR_EMOJI
        if person_name.lower() == cls.PARTNER_NAME.lower():
            return cls.PARTNER_EMOJI
        
        # Check for matches in person emoji mapping (for generic keywords)
        person_lower = person_name.lower()
        for keyword, emoji in cls.PERSON_EMOJIS.items():
            if keyword in person_lower:
                return emoji
        
        # Default emoji for unknown persons
        return '👤'
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        errors = []
        
        if not cls.NOTION_API_TOKEN:
            errors.append("NOTION_API_TOKEN is not set")
        if not cls.EXPENSE_TABLE_DATABASE_ID:
            errors.append("EXPENSE_TABLE_DATABASE_ID is not set")
        if not cls.SPLIT_DETAILS_DATABASE_ID:
            errors.append("SPLIT_DETAILS_DATABASE_ID is not set")
        if not cls.BALANCES_PAGE_ID:
            errors.append("BALANCES_PAGE_ID is not set")
            
        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
        
        # Create directories if they don't exist
        cls.INPUT_FOLDER.mkdir(parents=True, exist_ok=True)
        cls.PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)
        cls.LOG_FOLDER.mkdir(parents=True, exist_ok=True)
        
        return True

