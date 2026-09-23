"""Unit tests for services/ui.py — ExpenseUI._print_edit_diff and review_and_edit."""

import pytest
from datetime import datetime
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from services.ui import ExpenseUI


@pytest.fixture
def ui():
    return ExpenseUI(your_name="Jon Doe", partner_name="Jane Doe")


# ---------------------------------------------------------------------------
# _print_edit_diff
# ---------------------------------------------------------------------------

class TestPrintEditDiff:
    """Tests for ExpenseUI._print_edit_diff()."""

    def test_changed_field_appears_in_table(self, ui):
        """A changed description produces a table row with before/after values."""
        original = {"description": "Saveway", "amount": 47.32, "date": datetime(2025, 1, 15)}
        updated  = {"description": "Safeway", "amount": 47.32, "date": datetime(2025, 1, 15)}

        with patch("services.ui.console") as mock_console, \
             patch("rich.table.Table.add_row") as mock_add_row:
            ui._print_edit_diff(original, updated)

        # console.print was called twice: once for the table, once for "Unchanged:"
        assert mock_console.print.call_count == 2
        # add_row was called once with (field_label, before, after)
        assert mock_add_row.call_count == 1
        args = mock_add_row.call_args[0]
        assert "Saveway" in args
        assert "Safeway" in args

    def test_unchanged_fields_listed_below_table(self, ui):
        """Fields that did not change are shown in the 'Unchanged:' line."""
        original = {"description": "Saveway", "amount": 47.32, "date": datetime(2025, 1, 15)}
        updated  = {"description": "Safeway", "amount": 47.32, "date": datetime(2025, 1, 15)}

        with patch("services.ui.console") as mock_console:
            ui._print_edit_diff(original, updated)

        unchanged_call = mock_console.print.call_args_list[1][0][0]
        assert "amount" in unchanged_call
        assert "date" in unchanged_call

    def test_no_changes_prints_no_fields_changed(self, ui):
        """When nothing changed, no table is printed and a 'no changes' message is shown."""
        info = {"description": "Safeway", "amount": 47.32, "date": datetime(2025, 1, 15)}

        with patch("services.ui.console") as mock_console:
            ui._print_edit_diff(info, info.copy())

        assert mock_console.print.call_count == 1
        msg = mock_console.print.call_args_list[0][0][0]
        assert "No fields were changed" in msg

    def test_date_formatted_as_yyyy_mm_dd(self, ui):
        """datetime values are rendered as YYYY-MM-DD strings in the diff table."""
        original = {"description": "X", "amount": 10.0, "date": datetime(2025, 1, 15)}
        updated  = {"description": "X", "amount": 10.0, "date": datetime(2025, 1, 20)}

        with patch("services.ui.console"), \
             patch("rich.table.Table.add_row") as mock_add_row:
            ui._print_edit_diff(original, updated)

        args = mock_add_row.call_args[0]
        assert "2025-01-15" in args
        assert "2025-01-20" in args

    def test_multiple_changed_fields_all_appear(self, ui):
        """When all three fields change, the table has three rows."""
        original = {"description": "Old",  "amount": 10.0, "date": datetime(2025, 1, 1)}
        updated  = {"description": "New",  "amount": 20.0, "date": datetime(2025, 2, 1)}

        with patch("services.ui.console") as mock_console:
            ui._print_edit_diff(original, updated)

        table_arg = mock_console.print.call_args_list[0][0][0]
        assert len(table_arg.rows) == 3


# ---------------------------------------------------------------------------
# review_and_edit
# ---------------------------------------------------------------------------

class TestReviewAndEdit:
    """Tests for ExpenseUI.review_and_edit()."""

    def _base_receipt(self):
        return {
            "description": "Safeway",
            "amount": 47.32,
            "date": datetime(2025, 1, 15),
            "merchant_name": "Safeway",
        }

    def test_no_edit_returns_original_unchanged(self, ui):
        """If user declines to edit, the original dict is returned untouched."""
        receipt = self._base_receipt()

        with patch("services.ui.ExpenseUI.display_extracted_info"), \
             patch("services.ui.Confirm.ask", return_value=False):
            result = ui.review_and_edit(receipt)

        assert result == self._base_receipt()

    def test_user_confirms_changes_are_applied(self, ui):
        """If user accepts the diff, updated values are written back to receipt_info."""
        receipt = self._base_receipt()

        with patch("services.ui.ExpenseUI.display_extracted_info"), \
             patch("services.ui.ExpenseUI._print_edit_diff"), \
             patch("services.ui.Confirm.ask", side_effect=[True, True]), \
             patch("services.ui.Prompt.ask", side_effect=["Superstore", "52.10", "2025-01-20"]), \
             patch("services.ui.console"):
            result = ui.review_and_edit(receipt)

        assert result["description"] == "Superstore"
        assert result["amount"] == 52.10
        assert result["date"] == datetime(2025, 1, 20)

    def test_user_declines_final_confirm_keeps_originals(self, ui):
        """If user declines the final 'Apply?' prompt, receipt_info is unchanged."""
        receipt = self._base_receipt()

        with patch("services.ui.ExpenseUI.display_extracted_info"), \
             patch("services.ui.ExpenseUI._print_edit_diff"), \
             patch("services.ui.Confirm.ask", side_effect=[True, False]), \
             patch("services.ui.Prompt.ask", side_effect=["Superstore", "52.10", "2025-01-20"]), \
             patch("services.ui.console"):
            result = ui.review_and_edit(receipt)

        assert result["description"] == "Safeway"
        assert result["amount"] == 47.32
        assert result["date"] == datetime(2025, 1, 15)

    def test_invalid_amount_keeps_original(self, ui):
        """Non-numeric amount input keeps the original amount."""
        receipt = self._base_receipt()

        with patch("services.ui.ExpenseUI.display_extracted_info"), \
             patch("services.ui.ExpenseUI._print_edit_diff"), \
             patch("services.ui.Confirm.ask", side_effect=[True, True]), \
             patch("services.ui.Prompt.ask", side_effect=["Safeway", "not-a-number", "2025-01-15"]), \
             patch("services.ui.console"):
            result = ui.review_and_edit(receipt)

        assert result["amount"] == 47.32

    def test_invalid_date_keeps_original(self, ui):
        """Malformed date input keeps the original date."""
        receipt = self._base_receipt()

        with patch("services.ui.ExpenseUI.display_extracted_info"), \
             patch("services.ui.ExpenseUI._print_edit_diff"), \
             patch("services.ui.Confirm.ask", side_effect=[True, True]), \
             patch("services.ui.Prompt.ask", side_effect=["Safeway", "47.32", "not-a-date"]), \
             patch("services.ui.console"):
            result = ui.review_and_edit(receipt)

        assert result["date"] == datetime(2025, 1, 15)
