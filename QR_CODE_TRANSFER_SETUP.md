# 📱 QR Code Transfer System - Setup Guide

## 🎉 What's Been Built

A complete "Send to Phone" system that lets kiosk users transfer AI tour recommendations to their phones via QR code!

---

## ✨ Features

### For Users:
1. **📱 Send to Phone Button** - Appears after AI recommends tours
2. **QR Code Generation** - Instant QR code for scanning
3. **Mobile-Optimized Page** - Beautiful, responsive recommendations page
4. **Email Option** - Optional email delivery on mobile page
5. **Share Functionality** - Native share or copy link
6. **Session-Based** - Each recommendation gets a unique, shareable URL

### Technical:
- ✅ Session storage (in-memory, upgradeable to database)
- ✅ QR code generation
- ✅ Mobile-first responsive design
- ✅ Email delivery with SendGrid
- ✅ Link sharing and copying
- ✅ Privacy-friendly (no signup required)

---

## 🛠️ Installation

### Step 1: Install Dependencies

```bash
pip install qrcode
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### Step 2: Verify Setup

All files are ready:
- ✅ `app.py` - Backend routes added
- ✅ `templates/recommendations.html` - Mobile page
- ✅ `templates/error.html` - Error page
- ✅ `templates/index.html` - QR button integrated
- ✅ `requirements.txt` - Updated

### Step 3: Restart Flask

```bash
python app.py
```

---

## 🎯 How It Works

### User Flow:

```
1. User chats with AI at kiosk
2. AI recommends tours
3. "📱 Send to My Phone" button appears
4. Click button → QR code pops up
5. Scan QR code with phone
6. View recommendations on mobile
7. Optional: Email to self
8. Optional: Share with travel companions
```

### Technical Flow:

```
Kiosk Chat
   ↓
AI Recommends Tours
   ↓
User Clicks "Send to Phone"
   ↓
POST /api/create-recommendation-session
   ↓
Generate unique session ID
   ↓
Store: tours, preferences, chat summary
   ↓
Return session URL
   ↓
Display QR Code (GET /api/generate-qr/{id})
   ↓
User scans QR
   ↓
GET /recommendations/{id}
   ↓
Display mobile-optimized page
   ↓
Optional: POST /api/email-recommendations
```

---

## 📱 Mobile Page Features

### What Users See:
- **Header**: "Your Tour Recommendations"
- **Preferences Summary**: Shows their search criteria
- **Chat Summary**: Quote from their kiosk conversation
- **Tour Cards**:
  - Tour image
  - Name & company
  - Price & duration
  - Rating & reviews
  - Summary
  - "Book Now" button
- **Action Bar**:
  - 📤 Share button
  - 📧 Email Me button

### Email Feature:
- Enter email address
- Receive beautifully formatted HTML email
- Includes all tour details
- Link to view online
- Valid for 7 days

---

## 🔧 Configuration

### Environment Variables Required:

```env
# For Email Feature (Optional)
SENDGRID_API_KEY=your_sendgrid_key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
```

If you don't have SendGrid set up, the email feature will fail gracefully - users can still use QR codes and share links!

---

## 🎨 Customization

### Session Storage

Currently uses in-memory storage. For production with multiple servers, upgrade to:

#### Option 1: Database (PostgreSQL/MySQL)
```python
from flask_sqlalchemy import SQLAlchemy

class RecommendationSession(db.Model):
    id = db.Column(db.String(8), primary_key=True)
    tours = db.Column(db.JSON)
    preferences = db.Column(db.JSON)
    chat_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime)
    language = db.Column(db.String(2))
```

#### Option 2: Redis (Fast, Scalable)
```python
import redis
r = redis.Redis(host='localhost', port=6379, db=0)

# Store session
r.setex(
    f"session:{session_id}",
    604800,  # 7 days in seconds
    json.dumps(session_data)
)

# Retrieve session
session_data = json.loads(r.get(f"session:{session_id}"))
```

### Session Expiration

Currently sessions never expire (in-memory). To add expiration:

```python
# In app.py, add cleanup function
import time

def cleanup_old_sessions():
    """Remove sessions older than 7 days"""
    current_time = time.time()
    seven_days = 7 * 24 * 60 * 60
    
    expired = [
        sid for sid, data in recommendation_sessions.items()
        if current_time - data['created_at'] > seven_days
    ]
    
    for sid in expired:
        del recommendation_sessions[sid]
    
    print(f"🧹 Cleaned up {len(expired)} expired sessions")

# Call periodically or on each request
```

### Branding

Update these in `templates/recommendations.html`:
- Color scheme (search for `#0077b6`)
- Logo (add to header)
- Footer text
- Email template styling in `app.py`

---

## 🧪 Testing

### Test Checklist:

1. **Basic Flow**
   - [ ] Chat with AI
   - [ ] Get recommendations
   - [ ] See "Send to Phone" button
   - [ ] Click button
   - [ ] QR code appears

2. **QR Code**
   - [ ] QR code is scannable
   - [ ] Opens correct URL
   - [ ] Shows recommendations

3. **Mobile Page**
   - [ ] Displays all tours
   - [ ] Shows preferences
   - [ ] Shows chat summary
   - [ ] "Book Now" buttons work
   - [ ] Responsive design looks good

4. **Share Features**
   - [ ] Share button works (if native share available)
   - [ ] Copy link works
   - [ ] Link is shareable

5. **Email (if configured)**
   - [ ] Email modal opens
   - [ ] Email sends successfully
   - [ ] Email looks good
   - [ ] Links in email work

### Manual Testing:

```bash
# Test session creation
curl -X POST http://localhost:5000/api/create-recommendation-session \
  -H "Content-Type: application/json" \
  -d '{
    "tours": [{"name": "Test Tour", "price_adult": "$100"}],
    "preferences": {"duration": "full_day"},
    "chat_summary": "User wants full-day tours",
    "language": "en"
  }'

# Should return: {"success": true, "session_id": "abc123", "url": "..."}

# Then visit: http://localhost:5000/recommendations/abc123
```

---

## 🚀 Deployment Notes

### For Production:

1. **Use Database for Sessions**
   - Don't rely on in-memory storage
   - Sessions will be lost on server restart
   - Not scalable with multiple servers

2. **Add Rate Limiting**
   - Prevent QR code spam
   - Limit session creation per IP

3. **Add Analytics**
   - Track QR code scans
   - Monitor email sends
   - Measure conversion rates

4. **Cache QR Codes**
   - Generate once, serve multiple times
   - Reduce server load

5. **HTTPS Required**
   - QR codes with HTTP won't open on many phones
   - Use SSL certificate

### Security Considerations:

- ✅ Session IDs are random UUIDs (hard to guess)
- ✅ No sensitive data in sessions
- ⚠️ Add expiration (7 days recommended)
- ⚠️ Add rate limiting
- ⚠️ Validate email addresses before sending

---

## 📊 Analytics Ideas

Track these metrics:

```python
# Add to session creation
recommendation_sessions[session_id] = {
    'tours': tours,
    'preferences': preferences,
    'chat_summary': chat_summary,
    'created_at': time.time(),
    'language': language,
    # Analytics
    'views': 0,
    'email_sent': False,
    'shared': False,
    'bookings_clicked': 0
}

# Increment on page view
recommendation_sessions[session_id]['views'] += 1

# Track booking clicks
@app.route('/api/track-booking-click', methods=['POST'])
def track_booking_click():
    session_id = request.json.get('session_id')
    if session_id in recommendation_sessions:
        recommendation_sessions[session_id]['bookings_clicked'] += 1
    return jsonify({'success': True})
```

---

## 🎓 How It Integrates

### With AI Chat:
- Automatically appears after AI recommends tours
- Stores the conversation context
- Preserves user preferences
- Works with both filter-based and manual recommendations

### With Existing Features:
- ✅ Works with all language translations
- ✅ Compatible with voice chat
- ✅ Works with tour filtering
- ✅ Maintains tour images and data
- ✅ Booking links functional

---

## 🐛 Troubleshooting

### QR Code Not Appearing:
- Check browser console for errors
- Verify QR code library installed: `pip list | grep qrcode`
- Check button appears in chat after recommendations

### QR Code Won't Scan:
- Ensure adequate lighting
- Try different QR scanner app
- Check QR code image loads (visit `/api/generate-qr/test123`)

### Mobile Page Not Loading:
- Check session ID is valid
- Verify Flask app is running
- Check browser console on phone
- Ensure correct URL (no trailing slash)

### Email Not Sending:
- Verify SendGrid API key in `.env`
- Check SendGrid from email is verified
- Look for errors in Flask console
- Test with: `curl -X POST ... /api/email-recommendations`

---

## 📱 Example URLs

After setup, you'll have:

```
Kiosk Interface:
http://localhost:5000/

API Endpoints:
http://localhost:5000/api/create-recommendation-session
http://localhost:5000/api/generate-qr/{session_id}
http://localhost:5000/api/email-recommendations

Mobile Pages:
http://localhost:5000/recommendations/{session_id}

Example:
http://localhost:5000/recommendations/a1b2c3d4
```

---

## 🎉 Success!

You now have a complete QR code transfer system! Users can:
- ✅ Get personalized recommendations at the kiosk
- ✅ Scan QR code to view on phone
- ✅ Email recommendations to themselves
- ✅ Share with travel companions
- ✅ Book tours from their phone

**Next steps:**
1. Test the feature end-to-end
2. Customize branding/colors
3. Add analytics tracking
4. Upgrade to database storage
5. Deploy to production!

Need help? Check the troubleshooting section or review the code comments.

