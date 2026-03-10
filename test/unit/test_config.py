"""
Unit tests for config.py
Tests configuration loading and validation without external dependencies.
"""
import pytest
from unittest.mock import patch, MagicMock
import os
from pathlib import Path
import tempfile
import shutil


@pytest.mark.unit
class TestConfig:
    """Test configuration loading and validation"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        # Cleanup
        shutil.rmtree(temp_path, ignore_errors=True)
    
    def test_config_has_required_attributes(self):
        """Test that Config class has all required attributes"""
        from src.config import Config
        
        # Check required Notion API attributes exist
        assert hasattr(Config, 'NOTION_API_TOKEN')
        assert hasattr(Config, 'EXPENSE_TABLE_DATABASE_ID')
        assert hasattr(Config, 'SPLIT_DETAILS_DATABASE_ID')
        assert hasattr(Config, 'BALANCES_PAGE_ID')
        
        # Check user configuration attributes exist
        assert hasattr(Config, 'YOUR_NAME')
        assert hasattr(Config, 'PARTNER_NAME')
        assert hasattr(Config, 'YOUR_EMOJI')
        assert hasattr(Config, 'PARTNER_EMOJI')
        assert hasattr(Config, 'YOUR_USER_ID')
        assert hasattr(Config, 'PARTNER_USER_ID')
        
        # Check file path attributes exist
        assert hasattr(Config, 'PROJECT_ROOT')
        assert hasattr(Config, 'INPUT_FOLDER')
        assert hasattr(Config, 'PROCESSED_FOLDER')
        assert hasattr(Config, 'LOG_FOLDER')
        
        # Check split configuration exists
        assert hasattr(Config, 'DEFAULT_SPLIT_PERCENTAGE')
        
        # Check relation properties exist
        assert hasattr(Config, 'EXPENSE_RELATION_PROPERTY')
        assert hasattr(Config, 'BALANCES_RELATION_PROPERTY')
    
    def test_config_file_paths_are_path_objects(self):
        """Test that file paths are Path objects"""
        from src.config import Config
        
        assert isinstance(Config.PROJECT_ROOT, Path)
        assert isinstance(Config.INPUT_FOLDER, Path)
        assert isinstance(Config.PROCESSED_FOLDER, Path)
        assert isinstance(Config.LOG_FOLDER, Path)
    
    def test_config_split_percentage_is_float(self):
        """Test that split percentage is a float"""
        from src.config import Config
        
        assert isinstance(Config.DEFAULT_SPLIT_PERCENTAGE, float)
        assert 0 <= Config.DEFAULT_SPLIT_PERCENTAGE <= 100
    
    def test_config_relation_property_names(self):
        """Test that relation property names are set correctly"""
        from src.config import Config
        
        assert Config.EXPENSE_RELATION_PROPERTY == "Split Details Table"
        assert Config.BALANCES_RELATION_PROPERTY == "Split Details Table"
    
    def test_config_project_root_is_correct(self):
        """Test that PROJECT_ROOT points to the correct directory"""
        from src.config import Config
        
        # PROJECT_ROOT should be parent of src directory
        assert (Config.PROJECT_ROOT / 'src').exists()
        assert (Config.PROJECT_ROOT / 'src' / 'config.py').exists()
    
    def test_validate_with_mock_missing_token(self):
        """Test validation fails when NOTION_API_TOKEN is None"""
        from src.config import Config
        
        with patch.object(Config, 'NOTION_API_TOKEN', None):
            with pytest.raises(ValueError) as exc_info:
                Config.validate()
            
            assert "NOTION_API_TOKEN is not set" in str(exc_info.value)
    
    def test_validate_with_mock_missing_expense_db(self):
        """Test validation fails when EXPENSE_TABLE_DATABASE_ID is None"""
        from src.config import Config
        
        with patch.object(Config, 'NOTION_API_TOKEN', 'test_token'), \
             patch.object(Config, 'EXPENSE_TABLE_DATABASE_ID', None), \
             patch.object(Config, 'SPLIT_DETAILS_DATABASE_ID', 'split_db'), \
             patch.object(Config, 'BALANCES_PAGE_ID', 'balances'):
            
            with pytest.raises(ValueError) as exc_info:
                Config.validate()
            
            assert "EXPENSE_TABLE_DATABASE_ID is not set" in str(exc_info.value)
    
    def test_validate_with_mock_missing_split_db(self):
        """Test validation fails when SPLIT_DETAILS_DATABASE_ID is None"""
        from src.config import Config
        
        with patch.object(Config, 'NOTION_API_TOKEN', 'test_token'), \
             patch.object(Config, 'EXPENSE_TABLE_DATABASE_ID', 'expense_db'), \
             patch.object(Config, 'SPLIT_DETAILS_DATABASE_ID', None), \
             patch.object(Config, 'BALANCES_PAGE_ID', 'balances'):
            
            with pytest.raises(ValueError) as exc_info:
                Config.validate()
            
            assert "SPLIT_DETAILS_DATABASE_ID is not set" in str(exc_info.value)
    
    def test_validate_with_mock_missing_balances_page(self):
        """Test validation fails when BALANCES_PAGE_ID is None"""
        from src.config import Config
        
        with patch.object(Config, 'NOTION_API_TOKEN', 'test_token'), \
             patch.object(Config, 'EXPENSE_TABLE_DATABASE_ID', 'expense_db'), \
             patch.object(Config, 'SPLIT_DETAILS_DATABASE_ID', 'split_db'), \
             patch.object(Config, 'BALANCES_PAGE_ID', None):
            
            with pytest.raises(ValueError) as exc_info:
                Config.validate()
            
            assert "BALANCES_PAGE_ID is not set" in str(exc_info.value)
    
    def test_validate_with_multiple_missing_fields(self):
        """Test validation error message includes all missing fields"""
        from src.config import Config
        
        with patch.object(Config, 'NOTION_API_TOKEN', None), \
             patch.object(Config, 'EXPENSE_TABLE_DATABASE_ID', None), \
             patch.object(Config, 'SPLIT_DETAILS_DATABASE_ID', None), \
             patch.object(Config, 'BALANCES_PAGE_ID', None):
            
            with pytest.raises(ValueError) as exc_info:
                Config.validate()
            
            error_message = str(exc_info.value)
            assert "NOTION_API_TOKEN is not set" in error_message
            assert "EXPENSE_TABLE_DATABASE_ID is not set" in error_message
            assert "SPLIT_DETAILS_DATABASE_ID is not set" in error_message
            assert "BALANCES_PAGE_ID is not set" in error_message
    
    def test_validate_creates_directories_if_not_exist(self, temp_dir):
        """Test that validate creates required directories"""
        from src.config import Config
        
        input_path = temp_dir / 'new_input'
        processed_path = temp_dir / 'new_processed'
        log_path = temp_dir / 'new_logs'
        
        # Ensure directories don't exist
        assert not input_path.exists()
        assert not processed_path.exists()
        assert not log_path.exists()
        
        with patch.object(Config, 'NOTION_API_TOKEN', 'test_token'), \
             patch.object(Config, 'EXPENSE_TABLE_DATABASE_ID', 'expense_db'), \
             patch.object(Config, 'SPLIT_DETAILS_DATABASE_ID', 'split_db'), \
             patch.object(Config, 'BALANCES_PAGE_ID', 'balances'), \
             patch.object(Config, 'INPUT_FOLDER', input_path), \
             patch.object(Config, 'PROCESSED_FOLDER', processed_path), \
             patch.object(Config, 'LOG_FOLDER', log_path):
            
            result = Config.validate()
            assert result is True
            
            # Verify directories were created
            assert input_path.exists()
            assert processed_path.exists()
            assert log_path.exists()
    
    def test_validate_handles_existing_directories(self, temp_dir):
        """Test that validate doesn't fail if directories already exist"""
        from src.config import Config
        
        input_path = temp_dir / 'existing_input'
        processed_path = temp_dir / 'existing_processed'
        log_path = temp_dir / 'existing_logs'
        
        # Create directories first
        input_path.mkdir(parents=True)
        processed_path.mkdir(parents=True)
        log_path.mkdir(parents=True)
        
        with patch.object(Config, 'NOTION_API_TOKEN', 'test_token'), \
             patch.object(Config, 'EXPENSE_TABLE_DATABASE_ID', 'expense_db'), \
             patch.object(Config, 'SPLIT_DETAILS_DATABASE_ID', 'split_db'), \
             patch.object(Config, 'BALANCES_PAGE_ID', 'balances'), \
             patch.object(Config, 'INPUT_FOLDER', input_path), \
             patch.object(Config, 'PROCESSED_FOLDER', processed_path), \
             patch.object(Config, 'LOG_FOLDER', log_path):
            
            # Should not raise an error
            result = Config.validate()
            assert result is True
    
    def test_validate_success_with_all_required_fields(self, temp_dir):
        """Test successful validation with all required fields"""
        from src.config import Config
        
        with patch.object(Config, 'NOTION_API_TOKEN', 'test_token'), \
             patch.object(Config, 'EXPENSE_TABLE_DATABASE_ID', 'expense_db'), \
             patch.object(Config, 'SPLIT_DETAILS_DATABASE_ID', 'split_db'), \
             patch.object(Config, 'BALANCES_PAGE_ID', 'balances'), \
             patch.object(Config, 'INPUT_FOLDER', temp_dir / 'input'), \
             patch.object(Config, 'PROCESSED_FOLDER', temp_dir / 'processed'), \
             patch.object(Config, 'LOG_FOLDER', temp_dir / 'logs'):
            
            result = Config.validate()
            assert result is True
    
    def test_config_string_attributes_are_strings_or_none(self):
        """Test that string configuration attributes are strings or None"""
        from src.config import Config
        
        # These can be None if not set in environment
        assert Config.NOTION_API_TOKEN is None or isinstance(Config.NOTION_API_TOKEN, str)
        assert Config.EXPENSE_TABLE_DATABASE_ID is None or isinstance(Config.EXPENSE_TABLE_DATABASE_ID, str)
        assert Config.SPLIT_DETAILS_DATABASE_ID is None or isinstance(Config.SPLIT_DETAILS_DATABASE_ID, str)
        assert Config.BALANCES_PAGE_ID is None or isinstance(Config.BALANCES_PAGE_ID, str)
        
        # These should always be strings (have defaults)
        assert isinstance(Config.YOUR_NAME, str)
        assert isinstance(Config.PARTNER_NAME, str)
        assert isinstance(Config.YOUR_EMOJI, str)
        assert isinstance(Config.PARTNER_EMOJI, str)
        assert isinstance(Config.YOUR_USER_ID, str)
        assert isinstance(Config.PARTNER_USER_ID, str)
        assert isinstance(Config.EXPENSE_RELATION_PROPERTY, str)
        assert isinstance(Config.BALANCES_RELATION_PROPERTY, str)
    
    def test_config_validates_method_exists(self):
        """Test that Config has a validate classmethod"""
        from src.config import Config
        
        assert hasattr(Config, 'validate')
        assert callable(Config.validate)
    
    def test_default_split_percentage_range(self):
        """Test that default split percentage is within valid range"""
        from src.config import Config
        
        assert 0 <= Config.DEFAULT_SPLIT_PERCENTAGE <= 100
    
    def test_config_has_emoji_mappings(self):
        """Test that Config has emoji mapping dictionaries"""
        from src.config import Config
        
        assert hasattr(Config, 'MERCHANT_EMOJIS')
        assert hasattr(Config, 'PERSON_EMOJIS')
        assert isinstance(Config.MERCHANT_EMOJIS, dict)
        assert isinstance(Config.PERSON_EMOJIS, dict)
    
    def test_config_has_emoji_methods(self):
        """Test that Config has emoji getter methods"""
        from src.config import Config
        
        assert hasattr(Config, 'get_merchant_emoji')
        assert hasattr(Config, 'get_person_emoji')
        assert callable(Config.get_merchant_emoji)
        assert callable(Config.get_person_emoji)
    
    def test_merchant_emoji_mappings_not_empty(self):
        """Test that merchant emoji mappings are not empty"""
        from src.config import Config
        
        assert len(Config.MERCHANT_EMOJIS) > 0
        # Verify some key merchants are present
        assert 'amazon' in Config.MERCHANT_EMOJIS
        assert 'walmart' in Config.MERCHANT_EMOJIS
        assert 'netflix' in Config.MERCHANT_EMOJIS
    
    def test_person_emoji_mappings_not_empty(self):
        """Test that person emoji mappings are not empty"""
        from src.config import Config
        
        assert len(Config.PERSON_EMOJIS) > 0
        # Verify some key person types are present
        assert 'boyfriend' in Config.PERSON_EMOJIS
        assert 'girlfriend' in Config.PERSON_EMOJIS
    
    def test_user_emoji_configuration(self):
        """Test that user emoji configuration is properly loaded"""
        from src.config import Config
        
        # Verify emoji attributes exist and are strings
        assert isinstance(Config.YOUR_EMOJI, str)
        assert isinstance(Config.PARTNER_EMOJI, str)
        
        # Verify they have default values if not set in env
        assert len(Config.YOUR_EMOJI) > 0
        assert len(Config.PARTNER_EMOJI) > 0
    
    def test_get_person_emoji_prioritizes_configured_names(self):
        """Test that get_person_emoji prioritizes YOUR_NAME and PARTNER_NAME"""
        from src.config import Config
        
        # Test that configured names return configured emojis
        your_emoji = Config.get_person_emoji(Config.YOUR_NAME)
        partner_emoji = Config.get_person_emoji(Config.PARTNER_NAME)
        
        assert your_emoji == Config.YOUR_EMOJI
        assert partner_emoji == Config.PARTNER_EMOJI
        assert 'partner' in Config.PERSON_EMOJIS

