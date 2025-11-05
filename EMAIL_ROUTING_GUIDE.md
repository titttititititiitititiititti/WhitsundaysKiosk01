# 📧 Email Routing Configuration Guide

## Quick Setup

### 1. Create/Edit `.env` file

Create a file called `.env` in your project root with:

```env
# OpenAI API Key (already have this)
OPENAI_API_KEY=sk-your-actual-openai-key-here

# SendGrid API Key (add this)
SENDGRID_API_KEY=SG.your-sendgrid-key-here

# Email Configuration
FROM_EMAIL=bookings@whitsundayskiosk.com
ADMIN_EMAIL=your_admin_email@example.com
```

### 2. Update Tour Operator Emails

Edit `app.py` and find the `COMPANY_EMAILS` dictionary (around line 295).

**Replace the placeholder emails with real operator emails:**

```python
COMPANY_EMAILS = {
    'redcatadventures': 'bookings@redcatadventures.com.au',
    'cruisewhitsundays': 'reservations@cruisewhitsundays.com',
    'helireef': 'bookings@helireef.com.au',
    # ... update each one with real email addresses
}
```

## How Email Routing Works

When a guest submits a booking:

1. System looks at the tour's `company_name` (e.g., "cruisewhitsundays")
2. Looks up that company in the `COMPANY_EMAILS` dictionary
3. Sends email to the matching email address
4. **If company not found**: sends to `ADMIN_EMAIL` from `.env` file

## Example

```
Guest books: "Whitehaven Beach Tour"
Tour company: "cruisewhitsundays"
System sends email to: reservations@cruisewhitsundays.com
```

## Finding Company Names

To see all company names in your system:

```python
# Run this in Python console
import glob
import csv

companies = set()
for csvfile in glob.glob('*_with_media.csv'):
    with open(csvfile, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.add(row['company_name'])

print(sorted(companies))
```

## Testing Email Routing

1. **Test without sending emails:**
   - Don't set `SENDGRID_API_KEY`
   - Submit a booking
   - Check `leads_log.csv` for logged data
   - Check console to see which email it would send to

2. **Test with real emails:**
   - Set your `SENDGRID_API_KEY`
   - Set `ADMIN_EMAIL` to your own email
   - Submit a test booking
   - Email will go to your inbox (since operator emails are placeholders)

## Updating Individual Emails

You can update emails at any time:

1. Edit `app.py` → `COMPANY_EMAILS` dictionary
2. Save the file
3. Restart Flask app
4. New bookings will use updated emails

## Fallback System

If a company email isn't found:
- Email goes to `ADMIN_EMAIL` from `.env`
- System logs this in console: "Sending to fallback admin email"
- Lead still logs to CSV

## Advanced: Different Emails Per Tour

If you want different email addresses for different tours from the same company:

**Option 1: Add email column to CSV files**
1. Add `operator_email` column to each CSV
2. Modify `send_booking_email()` function to check CSV first
3. Fall back to `COMPANY_EMAILS` dictionary if not found

**Option 2: Use tour-specific routing**
```python
# In app.py, add this before COMPANY_EMAILS:
TOUR_SPECIFIC_EMAILS = {
    'cruisewhitsundays__reefsleep': 'reefsleep@cruisewhitsundays.com',
    'cruisewhitsundays__camira': 'camira@cruisewhitsundays.com',
    # Format: 'company__tourid': 'specific@email.com'
}

# Then in send_booking_email(), check TOUR_SPECIFIC_EMAILS first
tour_key = booking_data.get('tour_key', '')
if tour_key in TOUR_SPECIFIC_EMAILS:
    to_email = TOUR_SPECIFIC_EMAILS[tour_key]
else:
    company = booking_data.get('tour_company', '').lower()
    to_email = COMPANY_EMAILS.get(company, ADMIN_EMAIL)
```

## Example `.env` File

```env
# OpenAI
OPENAI_API_KEY=sk-proj-abc123...

# SendGrid
SENDGRID_API_KEY=SG.xyz789...

# Email Settings
FROM_EMAIL=bookings@yourcompany.com
ADMIN_EMAIL=bailey@yourcompany.com
```

## Troubleshooting

**Email going to wrong address?**
- Check company_name in CSV matches COMPANY_EMAILS key
- Check console for "Sending to..." message
- Company names are case-sensitive in dictionary

**All emails going to admin?**
- Company name not in COMPANY_EMAILS dictionary
- Add the company to the dictionary
- Company name might have different spelling

**Need to test with your own email first?**
- Set all values in COMPANY_EMAILS to your email
- Test bookings
- Once working, update with real operator emails








