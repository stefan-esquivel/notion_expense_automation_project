# Notion Expense Automation System

Automate your expense tracking workflow by processing receipt PDFs and automatically creating entries in your Notion expense and split tables.

## Features

✅ **Automated PDF Processing** - Extract merchant, date, and amount from receipts  
✅ **Smart Categorization** - Automatically detect Walmart, Amazon, utilities, and more  
✅ **Monthly Organization** - Sort receipts into month folders with descriptive names  
✅ **Interactive Review** - Preview and edit extracted information before sending  
✅ **Flexible Splitting** - 50/50 default with custom split or no-split options  
✅ **Notion Integration** - Automatically create linked Expense and Split Detail entries  

## System Requirements

- Python 3.8 or higher
- Notion account with API access
- PDF receipts (from email, downloads, etc.)

## Installation

### 1. Clone or Download the Project

```bash
cd notion_expense_automation_project
```

### 2. Create a Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Notion Integration

#### Create a Notion Integration:
1. Go to https://www.notion.so/my-integrations
2. Click "+ New integration"
3. Name it "Expense Automation"
4. Select your workspace
5. Copy the "Internal Integration Token"

#### Get Database IDs:
1. Open your Expense Table in Notion
2. Click "Share" → "Copy link"
3. Extract the database ID from the URL:
   ```
   https://notion.so/yourworkspace/DATABASE_ID?v=...
   ```
4. Repeat for Split Details Table

#### Get the Balances Page ID:
1. Open your Balances Table in Notion
2. Click into the single row (the balances page)
3. Click "Share" → "Copy link"
4. Extract the page ID from the URL (the long string after the last `/`)

#### Connect Integration to Databases:
1. Open each database in Notion (Expense Table, Split Details Table, Balances Table)
2. Click "•••" (top right) → "Add connections"
3. Select your "Expense Automation" integration
   > Note: The Balances Table connection is still needed for the Balances Page ID to work.

### 5. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
NOTION_API_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxx
EXPENSE_TABLE_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SPLIT_DETAILS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# The single row in your Balances table (page ID, not database ID)
BALANCES_PAGE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Use aliases — these don't have to be real names
# Emojis will appear as icons on Notion entries
YOUR_NAME=You
YOUR_EMOJI=👤
PARTNER_NAME=Partner
PARTNER_EMOJI=👤

INPUT_FOLDER=receipts/input
PROCESSED_FOLDER=receipts/processed

DEFAULT_SPLIT_PERCENTAGE=50.0
```

## Usage

### 1. Add Receipts

Place your PDF receipts in the `receipts/input/` folder.

### 2. Run the Application

```bash
python src/main.py
```

### 3. Follow the Interactive Prompts

The system will:
1. Extract information from each receipt
2. Display extracted data for review
3. Allow you to edit any information
4. Ask who paid for the expense
5. Confirm split details (50/50, custom, or no split)
6. Show final preview
7. Create Notion entries upon confirmation
8. Organize the receipt file by month

### 4. Check Your Notion

- **Expense Table**: New entry with merchant, date, amount, and payer
- **Split Details Table**: Linked entry showing the other person's share (debt)
- **Balances Table**: Split entry linked to the single Balances page to update running totals
- **Organized Files**: Receipts moved to `receipts/processed/YYYY-MM/` with descriptive names

## Workflow Example

**Input:** `invoice.pdf` in `receipts/input/`

**Process:**
1. System extracts: "Walmart Order - $92.01 - Jan 18, 2026"
2. You review and confirm the information
3. You select: `YOU` paid (your alias from `YOUR_NAME`)
4. You confirm the split percentage (default 50%)
5. You confirm and send to Notion

**Output:**
- **Expense Entry**: "Walmart Order" - CA$92.01 - Paid by `YOU`
- **Split Entry**: "`PARTNER`'s Walmart Food Split" - 50% share — Notion calculates the dollar amount via rollup from the Expense entry
- **Balances Entry**: Split linked to the Balances page
- **File**: Moved to `receipts/processed/2026-01/2026-01-18_Walmart_Order_$92.01.pdf`

## File Structure

```
notion_expense_automation_project/
├── src/
│   ├── __init__.py
│   ├── main.py              # Main application entry point
│   ├── config.py            # Configuration management
│   ├── pdf_extractor.py     # PDF text extraction and parsing
│   ├── file_organizer.py    # File organization and renaming
│   ├── notion_client.py     # Notion API integration
│   └── ui.py                # User interface and prompts
├── receipts/
│   ├── input/               # Place new receipts here
│   └── processed/           # Organized receipts by month
├── logs/                    # Application logs
├── examples/                # Example CSV exports from Notion
├── requirements.txt         # Python dependencies
├── .env.example            # Example environment configuration
├── .env                    # Your actual configuration (not in git)
└── README.md               # This file
```

## Supported Merchants

The system automatically detects and categorizes:

- **Walmart** - Grocery orders and deliveries
- **Amazon** - Online orders
- **Electrical/Utility Bills** - Hydro, electricity, power
- **Rent** - Monthly rent payments
- **Netflix** - Streaming subscription
- **YouTube Premium** - Subscription
- **Parking** - Monthly parking fees
- **Longo's** - Grocery store
- **TV/Cable** - Television services

## Split Title Patterns

The system generates split titles following your existing Notion patterns (using your configured name aliases):

- Food: "`PARTNER`'s Walmart Food Split (Shrimp)"
- Bills: "`YOU`'s Electrical Bill Split (Jan)"
- Subscriptions: "`PARTNER`'s Netflix Payment (Feb)"
- Rent: "`YOU`'s Rent Split (Feb)"

## Troubleshooting

### "No PDF files found"
- Ensure PDFs are in `receipts/input/` folder
- Check file extensions are `.pdf` (lowercase)

### "Failed to connect to Notion API"
- Verify your `NOTION_API_TOKEN` in `.env`
- Ensure integration is connected to both databases
- Check database IDs are correct

### "Could not extract amount or date"
- Review the PDF manually
- Use the edit feature to input values manually
- Some PDFs may have poor text extraction

### Import Errors
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again

## Logs

Application logs are stored in `logs/` folder with daily rotation:
```
logs/expense_automation_20260214.log
```

Check logs for detailed error messages and processing history.

## Advanced Configuration

### Custom Split Percentages

Edit `.env` to change default split:
```env
DEFAULT_SPLIT_PERCENTAGE=60.0  # 60/40 split instead of 50/50
```

### Different Folder Locations

```env
INPUT_FOLDER=/path/to/your/receipts
PROCESSED_FOLDER=/path/to/organized/receipts
```

## Security Notes

- Never commit `.env` file to version control
- Keep your Notion API token secure
- The `.env` file is already in `.gitignore`

## Support

For issues or questions:
1. Check the logs in `logs/` folder
2. Review this README
3. Verify your Notion integration setup

## License

This project is for personal use. Modify as needed for your workflow.