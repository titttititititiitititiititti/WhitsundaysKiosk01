# 🌍 Multi-Language System - Quick Start

## What We Just Built

✅ **Full multi-language support** with organized folder structure  
✅ **DeepL + Google Translate** integration (best quality)  
✅ **Translate once, use forever** approach (saves API costs)  
✅ **Smart folder organization** by company and language  
✅ **Automatic language detection** from URL/localStorage  

## File Structure Created

```
data/
  ├── {company}/
  │   ├── en/  ← English (source)
  │   ├── zh/  ← Chinese
  │   ├── ja/  ← Japanese
  │   ├── ko/  ← Korean
  │   ├── de/  ← German
  │   ├── fr/  ← French
  │   ├── es/  ← Spanish
  │   └── hi/  ← Hindi
```

## Quick Start (3 Steps)

### 1️⃣ Install Dependencies
```bash
pip install -r requirements_translation.txt
```

### 2️⃣ Get DeepL API Key
- Go to: https://www.deepl.com/pro-api
- Sign up (free)
- Copy your API key
- Create `.env` file:
```env
DEEPL_API_KEY=your_key_here
```

### 3️⃣ Translate Your Tours
```bash
# Step 1: Organize CSVs into folders
python translate_tours.py --organize-only

# Step 2: Translate to all languages
python translate_tours.py --all
```

## Testing

```bash
# Start the app
python app.py

# Open browser
http://127.0.0.1:5000

# Click language selector (top right)
# Choose a language
# See tours in that language! 🎉
```

## What Gets Translated

**Tour Content:**
- Names, descriptions, highlights
- Itineraries, inclusions, policies
- All text fields

**Not Translated:**
- Prices (A$152)
- Times (9:00 AM)
- URLs, phone numbers
- Company names
- Departure locations

## Translation Services

| Language | Service | Why |
|----------|---------|-----|
| Chinese (Simplified) | DeepL | Best quality for tourism |
| Japanese | DeepL | Native-sounding translations |
| Korean | DeepL | Superior context understanding |
| German | DeepL | DeepL is German-built |
| French | DeepL | Excellent for European languages |
| Spanish | DeepL | Natural phrasing |
| Hindi | Google | DeepL doesn't support Hindi |

## Cost

**DeepL Free:** 500,000 chars/month  
**Your tours:** ~50 tours × 2,000 chars × 7 languages = ~700,000 chars  

**Solution:** Translate in batches or upgrade to DeepL Pro ($5/month for 1M chars)

## Advanced Usage

```bash
# Translate specific languages only
python translate_tours.py --all --languages zh ja ko

# Translate one company
python translate_tours.py --company cruisewhitsundays

# Re-translate after updates (deletes old translations first)
rm -rf data/*/zh/  # Delete Chinese translations
python translate_tours.py --all --languages zh  # Re-translate
```

## How Language Switching Works

1. User clicks 🌐 button
2. Selects language (e.g., 🇯🇵 Japanese)
3. Page reloads with `?lang=ja`
4. Flask loads: `data/{company}/ja/tours_*.csv`
5. Everything displays in Japanese!

## Files Modified

- ✅ `translate_tours.py` - New translation script
- ✅ `app.py` - Loads language-specific CSVs
- ✅ `templates/index.html` - Passes language to backend
- ✅ `requirements_translation.txt` - New dependencies
- ✅ `TRANSLATION_SETUP.md` - Full documentation

## Next Steps

1. **Get your DeepL API key** (5 minutes)
2. **Run the translation** (10 minutes for all languages)
3. **Test in browser** (1 minute)
4. **Show your client** (priceless! 😄)

---

**Need Help?** Check `TRANSLATION_SETUP.md` for full documentation!
























