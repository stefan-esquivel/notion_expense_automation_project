# QA Environment - Manual Formula Setup

After running the setup script, you need to manually add the following formulas in Notion to complete the QA environment.

## Split Details Table Formulas

### 1. Share Amount
**Property Type:** Formula  
**Formula:**
```
prop("Share Percent") * prop("Expense Total")
```

**Steps:**
1. Open the "QA - Split Details Table" in Notion
2. Click the "+" button to add a new property
3. Name it "Share Amount"
4. Select "Formula" as the property type
5. Paste the formula above
6. Set format to "Canadian Dollar" (optional)

---

### 2. Outstanding
**Property Type:** Formula  
**Formula:**
```
if(prop("Paid"), 0, prop("Share Amount"))
```

**Description:** Shows the outstanding amount if not paid, otherwise shows 0.

**Steps:**
1. Add a new property called "Outstanding"
2. Select "Formula" as the property type
3. Paste the formula above
4. Set format to "Canadian Dollar" (optional)

---

### 3. Signed Outstanding
**Property Type:** Formula  
**Formula:**
```
if(prop("Person").some(current.name() == "Lydu"), prop("Outstanding"), -prop("Outstanding"))
```

**Description:** Shows positive outstanding for Lydu, negative for others (to calculate who owes whom).

**Note:** Replace "Lydu" with the actual person name from your configuration.

**Steps:**
1. Add a new property called "Signed Outstanding"
2. Select "Formula" as the property type
3. Paste the formula above (update the name if needed)
4. Set format to "Canadian Dollar" (optional)

---

## Balances Database Formula

### Current Balance
**Property Type:** Formula  
**Formula:**
```
if(prop("Balance") > 0, 
   "John Owes $" + format(round(abs(prop("Balance")), 2)), 
   if(prop("Balance") < 0, 
      "Jane Owes $" + format(round(abs(prop("Balance")), 2)), 
      "All settled ✅"
   )
)
```

**Description:** Displays a human-readable balance message showing who owes whom.

**Note:** Replace "John" and "Jane" with the actual names from your configuration (YOUR_NAME and PARTNER_NAME).

**Steps:**
1. Open the "QA - Total Balance" database in Notion
2. Add a new property called "Current Balance" or "Balance Status"
3. Select "Formula" as the property type
4. Paste the formula above (update names if needed)

---

## Additional Properties Needed

### Split Details Table
Make sure these properties exist (they should have been created by the script):
- ✅ Title (Title)
- ✅ Person (People)
- ✅ Date (Date)
- ✅ Share Percent (Number - Percent)
- ✅ Balances (Relation to Balances Database)
- ✅ Expense Table (Relation to Expense Table)
- ⚠️ **Paid** (Checkbox) - **ADD THIS MANUALLY**
- ⚠️ **Expense Total** (Rollup from Expense Table → Amount) - **ADD THIS MANUALLY**

### Adding the Paid Checkbox
1. Open "QA - Split Details Table"
2. Add new property "Paid"
3. Select "Checkbox" type

### Adding the Expense Total Rollup
1. Open "QA - Split Details Table"
2. Add new property "Expense Total"
3. Select "Rollup" type
4. Relation: "Expense Table"
5. Property: "Amount"
6. Calculate: "Sum"

---

## Expense Table Properties
These should already exist from the script:
- ✅ Merchant / Description (Title)
- ✅ Date (Date)
- ✅ Amount (Number - Canadian Dollar)
- ✅ Paid By (People)
- ✅ Split Details Table (Relation)
- ✅ Receipt (optional) (Files)
- ✅ Paid (Number - Canadian Dollar)

---

## Balances Database Properties
These should already exist from the script:
- ✅ Name (Title)
- ✅ Person (People)
- ✅ Balance (Number - Canadian Dollar)

---

## Quick Setup Checklist

- [ ] Add "Paid" checkbox to Split Details Table
- [ ] Add "Expense Total" rollup to Split Details Table
- [ ] Add "Share Amount" formula to Split Details Table
- [ ] Add "Outstanding" formula to Split Details Table
- [ ] Add "Signed Outstanding" formula to Split Details Table
- [ ] Add "Current Balance" formula to Balances Database
- [ ] Update person names in formulas to match your configuration
- [ ] Test by creating a sample expense entry

---

## Testing Your Setup

1. Create a test expense in the Expense Table:
   - Merchant: "Test Store"
   - Date: Today
   - Amount: $100
   - Paid By: Your name

2. Create split entries in Split Details Table:
   - Person: Your name, Share Percent: 50%
   - Person: Partner name, Share Percent: 50%

3. Verify formulas calculate correctly:
   - Share Amount should show $50 for each person
   - Outstanding should show $50 (if not marked as Paid)
   - Signed Outstanding should show +$50 for one person, -$50 for the other

4. Check the Balances database updates correctly

---

## Troubleshooting

### Formula shows "Invalid formula"
- Check that all referenced properties exist
- Verify property names match exactly (case-sensitive)
- Ensure relations are properly set up

### Rollup shows empty
- Verify the relation between tables is working
- Check that the Expense Table has the "Amount" property
- Make sure the relation property name matches exactly

### Person name not working in formula
- Update the name in the "Signed Outstanding" formula to match your actual Notion user name
- Names are case-sensitive

---

## Related Documentation
- [QA Environment Guide](QA_ENVIRONMENT_GUIDE.md)
- [QA Setup Fix](QA_SETUP_FIX.md)
- [Scripts README](../scripts/README.md)