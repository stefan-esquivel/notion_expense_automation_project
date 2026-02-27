# Setup Guide - Notion Expense Automation

This guide will walk you through setting up the Notion Expense Automation system step by step.

## Prerequisites Checklist

- [ ] Python 3.8+ installed on your computer
- [ ] Notion account with workspace access
- [ ] Existing Expense Table, Split Details Table, and Balances Table in Notion
- [ ] PDF receipts ready to process

## Step 1: Notion Integration Setup

### 1.1 Create a Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click **"+ New integration"**
3. Fill in the details:
   - **Name**: Expense Automation
   - **Associated workspace**: Select your workspace
   - **Type**: Internal integration
4. Click **"Submit"**
5. **IMPORTANT**: Copy the "Internal Integration Token" (starts with `secret_`)
   - Save this somewhere safe - you'll need it for the `.env` file

### 1.2 Get Your Database IDs

#### For Expense Table:
1. Open your **Expense Table** in Notion
2. Click **"Share"** button (top right)
3. Click **"Copy link"**
4. The link looks like: `https://notion.so/yourworkspace/27361377bcc3807b883be5176931dea4?v=...`
5. The database ID is the long string: `27361377bcc3807b883be5176931dea4`
6. Save this ID

#### For Split Details Table:
1. Open your **Split Details Table** in Notion
2. Click **"Share"** → **"Copy link"**
3. Extract the database ID from the URL (same format as above)
4. Save this ID

#### For Balances Table:
1. Open your **Balances Table** in Notion
2. Click **"Share"** → **"Copy link"**
3. Extract the database ID from the URL
4. Save this ID

#### For Balances Page ID:
1. Open your **Balances Table** in Notion
2. Click into the **single row** (the balances tracking page)
3. Click **"Share"** → **"Copy link"**
4. The page ID is the long string at the end of the URL (after the last `/`, before any `?`)
5. Save this ID — this is different from the database ID above

### 1.3 Connect Integration to Databases

**For EACH database (Expense Table, Split Details Table, and Balances Table):**

1. Open the database in Notion
2. Click the **"•••"** menu (top right corner)
3. Scroll down and click **"Add connections"**
4. Find and select **"Expense Automation"** (your integration)
5. Click **"Confirm"**

✅ You should see "Expense Automation" listed under connections

## Step 2: Project Setup

### 2.1 Navigate to Project Directory

```bash
cd /Users/sesq/Documents/GitHub/notion_expense_automation_project
```

### 2.2 Create Virtual Environment

```bash
python3 -m venv venv
```

### 2.3 Activate Virtual Environment

**On macOS/Linux:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

### 2.4 Install Dependencies

```bash
pip install -r requirements.txt
```

Wait for all packages to install. This may take a few minutes.

## Step 3: Configuration

### 3.1 Create Your .env File

```bash
cp .env.example .env
```

### 3.2 Edit .env File

Open `.env` in a text editor and fill in your values:

```env
# Paste your integration token from Step 1.1
NOTION_API_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxx

# Paste your Expense Table database ID from Step 1.2
EXPENSE_TABLE_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Paste your Split Details Table database ID from Step 1.2
SPLIT_DETAILS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Paste your Balances Table database ID from Step 1.2
BALANCES_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Paste the single Balances row page ID from Step 1.2
BALANCES_PAGE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Your name alias — used in split titles and to match Notion "Paid By" / "Person" fields
# Can be any alias, but must match exactly what's in Notion
YOUR_NAME=You

# Your partner's name alias — same rules as above
PARTNER_NAME=Partner

# Leave these as default or customize
INPUT_FOLDER=receipts/input
PROCESSED_FOLDER=receipts/processed
DEFAULT_SPLIT_PERCENTAGE=50.0
```

**Important Notes:**
- Replace `secret_xxxxx` with your actual token
- Replace all IDs with your actual values
- `YOUR_NAME` and `PARTNER_NAME` are aliases — they must match exactly what appears in your Notion "Paid By" and "Person" fields
- `BALANCES_PAGE_ID` is a **page ID** (a specific row), not a database ID
- Don't add quotes around values

### 3.3 Verify Folder Structure

The installation already created these folders:
```
receipts/
├── input/       # Place new receipts here
└── processed/   # Organized receipts will go here
logs/            # Application logs
```

## Step 4: Test the Setup

### 4.1 Add a Test Receipt

1. Find a PDF receipt (Walmart, Amazon, etc.)
2. Copy it to `receipts/input/`

### 4.2 Run the Application

```bash
python src/main.py
```

### 4.3 What to Expect

The application will:
1. ✅ Validate your configuration
2. ✅ Test Notion API connection
3. 📄 Display extracted receipt information
4. ❓ Ask if you want to edit anything
5. 💳 Ask who paid for the expense
6. 💰 Confirm split details
7. 👁️ Show final preview
8. ✅ Ask for confirmation to send to Notion
9. 🎉 Create entries and organize the file

### 4.4 Verify in Notion

1. Open your **Expense Table** — you should see a new entry
2. Open your **Split Details Table** — you should see a linked split entry
3. Open your **Balances Table** — the single row should now link to the new split entry
4. Check that the amounts are correct (50/50 split by default)

## Step 5: Daily Usage

### Adding Receipts

1. Save PDF receipts to `receipts/input/`
2. Run: `python src/main.py`
3. Follow the prompts for each receipt
4. Check Notion to verify entries

### Organized Files

Processed receipts are moved to:
```
receipts/processed/YYYY-MM/YYYY-MM-DD_Merchant_Description_$Amount.pdf
```

Example:
```
receipts/processed/2026-01/2026-01-18_Walmart_Order_Shrimp_$97.08.pdf
```

## Troubleshooting

### Error: "Configuration errors: NOTION_API_TOKEN is not set"

**Solution**: 
- Check that `.env` file exists (not `.env.example`)
- Verify the token is on the correct line without quotes
- Make sure there are no extra spaces

### Error: "Failed to connect to Notion API"

**Solutions**:
1. Verify your integration token is correct
2. Check that you connected the integration to BOTH databases (Step 1.3)
3. Verify database IDs are correct (no extra characters)

### Error: "No PDF files found"

**Solutions**:
- Ensure files are in `receipts/input/` folder
- Check file extension is `.pdf` (lowercase)
- Verify you're running from the project root directory

### Error: "Could not extract amount or date"

**Solutions**:
- Some PDFs have poor text extraction
- Use the "Edit" option to manually enter values
- Check the PDF opens correctly in a PDF viewer

### Import Errors (pdfplumber, notion_client, etc.)

**Solutions**:
1. Ensure virtual environment is activated: `source venv/bin/activate`
2. Reinstall dependencies: `pip install -r requirements.txt`
3. Check Python version: `python --version` (should be 3.8+)

## Advanced Tips

### Batch Processing

Place multiple PDFs in `receipts/input/` and run once. The system will process them one by one.

### Custom Splits

When prompted for split confirmation:
- Choose "Custom split amount" to enter a different amount
- Choose "No split" for 100% individual expenses

### Logs

Check `logs/expense_automation_YYYYMMDD.log` for detailed processing information and errors.

### Keyboard Shortcuts

- `Ctrl+C` - Cancel/exit the application
- Arrow keys - Navigate menu options
- Enter - Confirm selection

## Getting Help

1. **Check the logs**: `logs/` folder contains detailed error messages
2. **Review README.md**: Comprehensive documentation
3. **Verify Notion setup**: Most issues are from incorrect database connections

## Next Steps

Once everything is working:

1. ✅ Process your backlog of receipts
2. ✅ Set up a routine (weekly/monthly) to process new receipts
3. ✅ Customize merchant patterns in `src/pdf_extractor.py` if needed
4. ✅ Adjust split percentages in `.env` if you don't use 50/50

---

**Congratulations!** 🎉 Your Notion Expense Automation system is ready to use!