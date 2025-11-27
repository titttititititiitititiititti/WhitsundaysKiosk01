# 📬 Booking System Setup Guide

## Overview
The kiosk now has a complete lead generation system that sends booking inquiries via email to tour operators.

## ✨ Features
- Touch-friendly booking form modal
- Professional HTML emails to tour operators
- Lead backup logging to CSV
- Success confirmation screen for guests

## 🚀 Setup Instructions

### 1. Get SendGrid API Key (Free)

1. Go to [SendGrid.com](https://sendgrid.com/)
2. Create a free account (100 emails/day)
3. Navigate to Settings → API Keys
4. Create a new API key with "Full Access"
5. Copy the key (you'll only see it once!)

### 2. Configure Environment Variables

Add these to your `.env` file (create it if it doesn't exist):

```env
# OpenAI API Key (for chat features)
OPENAI_API_KEY=your_openai_api_key_here

# SendGrid API Key (for sending booking emails)
SENDGRID_API_KEY=your_sendgrid_api_key_here

# Email Configuration
FROM_EMAIL=bookings@whitsundayskiosk.com
ADMIN_EMAIL=your_admin_email@example.com
```

### 3. Update Tour Operator Emails

Edit `app.py` and update the `COMPANY_EMAILS` dictionary with real operator emails:

```python
COMPANY_EMAILS = {
    'redcatadventures': 'info@redcatadventures.com.au',
    'cruisewhitsundays': 'reservations@cruisewhitsundays.com',
    # ... update with real emails
}
```

### 4. Verify SendGrid Domain (Recommended)

For best deliverability:
1. In SendGrid, go to Settings → Sender Authentication
2. Verify your domain or single sender email
3. This prevents emails from going to spam

## 📧 Email Flow

1. Guest fills out booking form on kiosk
2. Email is sent to tour operator via SendGrid
3. Lead is logged to `leads_log.csv` (backup)
4. Guest sees success screen

## 📊 Lead Tracking

All booking inquiries are logged to `leads_log.csv` with:
- Timestamp
- Tour details
- Guest information
- Contact details
- Preferred date
- Special requests
- Email send status

## 🧪 Testing

### Test Without SendGrid (Development)
If `SENDGRID_API_KEY` is not set, the system will:
- Still log leads to CSV
- Print warning in console
- Show success to user
- Not actually send emails

### Test With SendGrid
1. Set your SendGrid API key in `.env`
2. Fill out a booking form
3. Check the console for "Email sent successfully"
4. Check `leads_log.csv` for the logged entry
5. Check the tour operator's email inbox

## 🎨 Customization

### Email Template
Edit the HTML email template in `app.py` → `send_booking_email()` function

### Form Fields
Edit `templates/index.html` → booking-modal section

### Styling
Edit the `.modal` styles in `templates/index.html`

## ⚠️ Important Notes

- **SendGrid free tier**: 100 emails/day (plenty for a kiosk)
- **CSV backup**: Always logs, even if email fails
- **Error handling**: Form shows user-friendly error if email fails
- **Email validation**: Form requires valid email format
- **Date validation**: Cannot select dates in the past

## 📝 Email Example

Tour operators receive formatted emails like this:

```
Subject: New Tour Inquiry - Whitehaven Beach Full Day Tour

┌─────────────────────────────────────┐
│   🏝️ New Tour Inquiry               │
└─────────────────────────────────────┘

Tour: Whitehaven Beach Full Day Tour
Company: Cruise Whitsundays

Guest Information:
Name: John Smith
Email: john@example.com
Phone: +61 400 123 456

Booking Details:
Adults: 2
Children: 1
Preferred Date: 2025-10-15

Message:
Interested in morning departure

Inquiry submitted from Whitsundays Visitor Kiosk
Time: 2025-10-11 14:30:22
```

## 🐛 Troubleshooting

### Emails not sending?
1. Check `SENDGRID_API_KEY` is set in `.env`
2. Verify API key is valid in SendGrid dashboard
3. Check console for error messages
4. Verify sender email is authenticated

### Leads not logging?
1. Check file permissions for `leads_log.csv`
2. Check console for write errors
3. Verify booking data is complete

### Form not opening?
1. Check browser console for JavaScript errors
2. Verify "Book Now" button onclick is correct
3. Check modal z-index isn't conflicting

## 💡 Future Enhancements

- SMS notifications via Twilio
- Automated follow-up emails
- Analytics dashboard
- Multiple language support
- Calendar integration








