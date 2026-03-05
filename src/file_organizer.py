"""File organization and management module."""
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class FileOrganizer:
    """Organize and rename receipt files."""
    
    def __init__(self, processed_folder: Path):
        self.processed_folder = processed_folder
    
    def generate_filename(
        self,
        date: datetime,
        merchant_name: str,
        description: str,
        amount: float,
        original_filename: str
    ) -> str:
        """
        Generate a descriptive filename for the receipt.
        Format: YYYY-MM-DD_Merchant_Description_$Amount.pdf
        """
        # Clean up description for filename
        clean_desc = description.replace(merchant_name, '').strip()
        clean_desc = clean_desc.strip('()')
        
        # Remove special characters
        clean_merchant = self._sanitize_filename(merchant_name)
        clean_desc = self._sanitize_filename(clean_desc)
        
        # Format amount
        amount_str = f"${amount:.2f}"
        
        # Build filename
        date_str = date.strftime('%Y-%m-%d')
        
        if clean_desc:
            filename = f"{date_str}_{clean_merchant}_{clean_desc}_{amount_str}.pdf"
        else:
            filename = f"{date_str}_{clean_merchant}_{amount_str}.pdf"
        
        return filename
    
    def _sanitize_filename(self, text: str) -> str:
        """Remove or replace characters that are invalid in filenames."""
        # Replace spaces with underscores
        text = text.replace(' ', '_')
        # Remove special characters
        text = ''.join(c for c in text if c.isalnum() or c in ('_', '-'))
        return text
    
    def _sanitize_vendor_name(self, vendor_name: str) -> str:
        """
        Sanitize vendor name for use as folder name.
        Returns 'unknown' if vendor name is empty or invalid.
        """
        if not vendor_name or not vendor_name.strip():
            return 'unknown'
        
        # Convert to lowercase and replace spaces with underscores
        sanitized = vendor_name.lower().strip()
        sanitized = sanitized.replace(' ', '_')
        
        # Remove special characters, keep only alphanumeric, underscore, and hyphen
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in ('_', '-'))
        
        # If sanitization resulted in empty string, return 'unknown'
        if not sanitized:
            return 'unknown'
        
        return sanitized
    
    def organize_file(
        self,
        source_path: Path,
        date: datetime,
        merchant_name: str,
        description: str,
        amount: float
    ) -> Path:
        """
        Move and rename file to organized folder structure.
        Creates hierarchical folders: processed/YYYY/MMM/vendor/filename.pdf
        
        Example: receipts/processed/2026/Feb/walmart/receipt_2026-02-15.pdf
        """
        # Create year folder
        year_folder = self.processed_folder / date.strftime('%Y')
        
        # Create month folder (3-letter abbreviation)
        month_name = date.strftime('%b')  # Jan, Feb, Mar, etc.
        month_folder = year_folder / month_name
        
        # Create vendor folder
        vendor_folder_name = self._sanitize_vendor_name(merchant_name)
        vendor_folder = month_folder / vendor_folder_name
        
        # Create all folders in hierarchy
        vendor_folder.mkdir(parents=True, exist_ok=True)
        
        # Generate new filename
        new_filename = self.generate_filename(
            date, merchant_name, description, amount, source_path.name
        )
        
        # Destination path
        dest_path = vendor_folder / new_filename
        
        # Handle duplicate filenames
        if dest_path.exists():
            base = dest_path.stem
            ext = dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = vendor_folder / f"{base}_{counter}{ext}"
                counter += 1
        
        # Move file
        shutil.move(str(source_path), str(dest_path))
        
        return dest_path
    
    def get_relative_path(self, full_path: Path) -> str:
        """Get path relative to processed folder for storage in Notion."""
        try:
            return str(full_path.relative_to(self.processed_folder))
        except ValueError:
            return full_path.name

