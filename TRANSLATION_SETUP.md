# Multi-Language Translation Setup Guide

## 📋 Overview

This guide will help you set up automatic translation for your tour content into 8 languages:
- 🇬🇧 English (default/source)
- 🇨🇳 Chinese (Simplified) - DeepL
- 🇯🇵 Japanese - DeepL
- 🇰🇷 Korean - DeepL
- 🇩🇪 German - DeepL
- 🇫🇷 French - DeepL
- 🇪🇸 Spanish - DeepL
- 🇮🇳 Hindi - Google Translate

## 🎯 How It Works

1. **English CSVs** are the source (stored in `data/{company}/en/`)
2. **Translation script** creates translated copies in language folders
3. **Flask app** loads the appropriate CSV based on user's language preference
4. **UI** is translated using `static/translations.json`
5. **Tour content** is translated from the language-specific CSVs

## ⚙️ Installation

### Step 1: Install Python Dependencies

```bash
pip install -r requirements_translation.txt
```

This installs:
- `deepl` - High-quality translation for 7 languages
- `googletrans` - Free Google Translate for Hindi
- `python-dotenv` - Environment variable management

### Step 2: Get Your DeepL API Key

1. Go to https://www.deepl.com/pro-api
2. Sign up for a **free account**
   - Free tier: 500,000 characters/month
   - Perfect for translating tours once
3. Copy your API key from the dashboard

### Step 3: Configure Environment Variables

Create a `.env` file in the project root:

```env
# DeepL API (required for 7 languages)
DEEPL_API_KEY=your_deepl_api_key_here

# Google Translate (optional - uses free API by default)
# GOOGLE_TRANSLATE_API_KEY=your_google_api_key_here
```

### Step 4: Organize Your CSVs

Run the organization command (this moves existing CSVs to `data/{company}/en/`):

```bash
python translate_tours.py --organize-only
```

This creates:
```
data/
  ├── cruisewhitsundays/
  │   └── en/
  │       └── tours_cruisewhitsundays_cleaned_with_media.csv
  ├── airliebeachdiving/
  │   └── en/
  │       └── tours_airliebeachdiving_cleaned_with_media.csv
  └── ... (all companies)
```

## 🚀 Translation Usage

### Translate All Companies to All Languages

```bash
python translate_tours.py --all
```

This will:
- Read all English CSVs from `data/{company}/en/`
- Translate tour names, descriptions, highlights, etc.
- Create translated CSVs in `data/{company}/{lang}/`
- Preserve prices, times, URLs (no translation needed)

### Translate Specific Languages Only

```bash
python translate_tours.py --all --languages zh ja ko
```

Only translates to Chinese, Japanese, and Korean.

### Translate Single Company

```bash
python translate_tours.py --company cruisewhitsundays
```

### Re-translate After Content Updates

Just run the translation command again. It will:
- Skip existing translated CSVs (unless you delete them first)
- Only translate new/updated content

## 📊 Cost Estimation

**DeepL Free Tier:** 500,000 characters/month

Average tour has ~2,000 characters of translatable content:
- Name: ~50 chars
- Summary: ~200 chars
- Description: ~500 chars
- Highlights: ~300 chars
- Includes: ~200 chars
- Itinerary: ~400 chars
- Important info: ~350 chars

**Capacity:**
- ~250 tours per language per month (free tier)
- Your current tours (~50) × 7 languages = ~700,000 characters

**Recommendation:** Get the free DeepL account - it's more than enough!

## 🔧 Translation Details

### Fields That Get Translated:
- ✅ `name` - Tour name
- ✅ `summary` - Short description
- ✅ `description` - Full description
- ✅ `highlights` - Key features
- ✅ `includes` - What's included
- ✅ `itinerary` - Schedule
- ✅ `menu` - Food options
- ✅ `important_information` - Policies
- ✅ `what_to_bring` - Packing list
- ✅ `whats_extra` - Additional costs
- ✅ `cancellation_policy` - Refund terms
- ✅ `age_requirements` - Age limits
- ✅ `ideal_for` - Who should book

### Fields That DON'T Get Translated:
- ❌ Prices (A$152, etc.)
- ❌ Times (9:00 AM, etc.)
- ❌ URLs (booking links)
- ❌ Phone numbers
- ❌ Company names
- ❌ Duration (preserved as-is)
- ❌ Departure locations (kept in English)
- ❌ Filter categories
- ❌ Image URLs

## 🌐 How Language Switching Works

### User Experience:
1. User clicks language selector (top right)
2. Selects a language (e.g., 🇯🇵 Japanese)
3. Page reloads with `?lang=ja` in URL
4. Flask loads `data/{company}/ja/tours_*.csv`
5. All tour content displays in Japanese
6. UI elements also translate via `translations.json`

### Language Persistence:
- Saved in browser `localStorage`
- Persists across sessions
- URL parameter takes priority

## 🛠️ Maintenance

### Adding New Tours:
1. Add tour to English CSV: `data/{company}/en/tours_*.csv`
2. Run translation: `python translate_tours.py --company {company}`
3. Restart Flask app

### Updating Existing Tours:
1. Edit English CSV: `data/{company}/en/tours_*.csv`
2. Delete translated versions you want to refresh
3. Run translation again

### Adding New Companies:
1. Create folder: `data/{new_company}/en/`
2. Add CSV: `data/{new_company}/en/tours_{new_company}_cleaned_with_media.csv`
3. Run: `python translate_tours.py --all`

## 🐛 Troubleshooting

### "No DEEPL_API_KEY found"
- Check your `.env` file exists in project root
- Verify the API key is correct (no extra spaces)
- Restart your terminal/IDE after adding `.env`

### "Translation failed"
- Check your DeepL free tier limit (500k chars/month)
- Verify internet connection
- Try translating one language at a time

### "No CSV files found"
- Run `python translate_tours.py --organize-only` first
- Check that CSVs are in `data/{company}/en/` folders

### Language not loading in app
- Clear browser cache and localStorage
- Check Flask console for errors
- Verify translated CSVs exist in `data/{company}/{lang}/`

## 📈 Performance

**Translation Speed:**
- ~5-10 seconds per tour
- ~5-10 minutes for 50 tours × 8 languages
- One-time cost, then instant loading!

**App Loading:**
- No performance impact (loads same CSV, just different language)
- Same speed as English-only version

## ✅ Testing

### Test Translation:
```bash
# Translate just one company to one language
python translate_tours.py --company cruisewhitsundays --languages zh
```

### Test in Browser:
1. Start Flask: `python app.py`
2. Open: http://127.0.0.1:5000
3. Click language selector, choose Chinese
4. Verify tour names/descriptions are in Chinese

## 🎉 You're Done!

Your tour kiosk now supports 8 languages with professional translations!

**Questions?** Check the console output - the script provides detailed progress and error messages.






