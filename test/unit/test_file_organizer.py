"""
Unit tests for file_organizer.py
Tests file organization logic with mocked filesystem operations.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime
from src.file_organizer import FileOrganizer


@pytest.mark.unit
class TestFileOrganizer:
    """Test file organization functionality"""
    
    @pytest.fixture
    def organizer(self, tmp_path):
        """Create FileOrganizer instance with temporary directory"""
        processed_folder = tmp_path / "processed"
        processed_folder.mkdir()
        return FileOrganizer(processed_folder)
    
    @pytest.fixture
    def sample_receipt(self, tmp_path):
        """Create a sample receipt file"""
        input_folder = tmp_path / "input"
        input_folder.mkdir()
        receipt_file = input_folder / "receipt.pdf"
        receipt_file.write_text("Sample receipt content")
        return receipt_file
    
    def test_organize_receipt_by_date(self, organizer, sample_receipt):
        """Test organizing receipt into year/month/vendor folder structure"""
        date = datetime(2026, 2, 15)
        merchant = "Walmart"
        description = "Groceries"
        amount = 45.67
        
        result_path = organizer.organize_file(
            sample_receipt, date, merchant, description, amount
        )
        
        # Verify the path structure: YYYY/MMM/vendor/filename.pdf
        assert result_path.parent.name == "walmart"
        assert result_path.parent.parent.name == "Feb"
        assert result_path.parent.parent.parent.name == "2026"
        assert result_path.exists()
    
    def test_create_year_month_vendor_folder_structure(self, organizer, sample_receipt):
        """Test creation of YYYY/MMM/vendor folder structure"""
        date = datetime(2026, 3, 20)
        merchant = "Amazon"
        
        result_path = organizer.organize_file(
            sample_receipt, date, merchant, "Order", 99.99
        )
        
        # Check folder hierarchy
        expected_path = organizer.processed_folder / "2026" / "Mar" / "amazon"
        assert result_path.parent == expected_path
        assert expected_path.exists()
    
    def test_sanitize_vendor_name(self, organizer):
        """Test vendor name sanitization for folder creation"""
        # Test normal vendor name
        assert organizer._sanitize_vendor_name("Walmart") == "walmart"
        
        # Test vendor with spaces
        assert organizer._sanitize_vendor_name("Best Buy") == "best_buy"
        
        # Test vendor with special characters
        assert organizer._sanitize_vendor_name("Trader Joe's") == "trader_joes"
        
        # Test empty vendor name
        assert organizer._sanitize_vendor_name("") == "unknown"
        assert organizer._sanitize_vendor_name("   ") == "unknown"
        
        # Test vendor with only special characters
        assert organizer._sanitize_vendor_name("@#$%") == "unknown"
    
    def test_handle_unknown_vendor(self, organizer, sample_receipt):
        """Test handling when vendor name is unknown or empty"""
        date = datetime(2026, 2, 15)
        
        result_path = organizer.organize_file(
            sample_receipt, date, "", "Purchase", 25.00
        )
        
        # Should use 'unknown' folder
        assert result_path.parent.name == "unknown"
    
    def test_move_file_to_processed_folder(self, organizer, sample_receipt):
        """Test moving file from input to processed folder"""
        date = datetime(2026, 2, 15)
        original_path = sample_receipt
        
        result_path = organizer.organize_file(
            sample_receipt, date, "Target", "Shopping", 50.00
        )
        
        # Original file should be moved (not exist anymore)
        assert not original_path.exists()
        # New file should exist
        assert result_path.exists()
    
    def test_handle_duplicate_filename(self, organizer, tmp_path):
        """Test handling when file with same name already exists"""
        date = datetime(2026, 2, 15)
        merchant = "Costco"
        
        # Create first file
        receipt1 = tmp_path / "input" / "receipt1.pdf"
        receipt1.parent.mkdir(exist_ok=True)
        receipt1.write_text("Receipt 1")
        
        path1 = organizer.organize_file(
            receipt1, date, merchant, "Purchase", 100.00
        )
        
        # Create second file with same parameters (would generate same filename)
        receipt2 = tmp_path / "input" / "receipt2.pdf"
        receipt2.write_text("Receipt 2")
        
        path2 = organizer.organize_file(
            receipt2, date, merchant, "Purchase", 100.00
        )
        
        # Both files should exist with different names
        assert path1.exists()
        assert path2.exists()
        assert path1 != path2
        assert "_1" in path2.name or path2.name != path1.name
    
    def test_generate_filename(self, organizer):
        """Test filename generation"""
        date = datetime(2026, 2, 15)
        merchant = "Walmart"
        description = "Groceries"
        amount = 45.67
        
        filename = organizer.generate_filename(
            date, merchant, description, amount, "original.pdf"
        )
        
        assert "2026-02-15" in filename
        assert "Walmart" in filename
        assert "$45.67" in filename
        assert filename.endswith(".pdf")
    
    def test_get_relative_path(self, organizer):
        """Test getting relative path from processed folder"""
        full_path = organizer.processed_folder / "2026" / "Feb" / "walmart" / "receipt.pdf"
        
        relative = organizer.get_relative_path(full_path)
        
        assert relative == "2026/Feb/walmart/receipt.pdf"
    
    def test_month_abbreviation(self, organizer, sample_receipt):
        """Test that month names are abbreviated correctly"""
        test_cases = [
            (datetime(2026, 1, 15), "Jan"),
            (datetime(2026, 2, 15), "Feb"),
            (datetime(2026, 3, 15), "Mar"),
            (datetime(2026, 12, 15), "Dec"),
        ]
        
        for date, expected_month in test_cases:
            # Create a new receipt for each test
            receipt = sample_receipt.parent / f"receipt_{date.month}.pdf"
            receipt.write_text("content")
            
            result_path = organizer.organize_file(
                receipt, date, "TestVendor", "Test", 10.00
            )
            
            assert result_path.parent.parent.name == expected_month

