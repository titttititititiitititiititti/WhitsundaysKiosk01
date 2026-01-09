"""
ElevenLabs Text-to-Speech Integration
Provides premium AI voice synthesis for the tour kiosk
"""

import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Voice IDs for different languages and styles
# Hannah - Natural Australian Voice (matches welcome message!)
HANNAH_VOICE_ID = 'M7ya1YbaeFaPXljg9BpK'
# Japanese-optimized voice
JAPANESE_VOICE_ID = 'PmgfHCGeS5b7sH90BOOJ'

VOICE_MAP = {
    'en': {
        'default': HANNAH_VOICE_ID,  # Hannah - Natural Australian Voice
        'female': HANNAH_VOICE_ID,   # Hannah
        'male': 'TxGEqnHWrfWFTfGW9XjX',     # Josh - Friendly male (backup)
    },
    'zh': {
        'default': HANNAH_VOICE_ID,
        'female': HANNAH_VOICE_ID,
        'male': 'TxGEqnHWrfWFTfGW9XjX',
    },
    'ja': {
        'default': JAPANESE_VOICE_ID,  # Japanese-optimized voice
        'female': JAPANESE_VOICE_ID,
        'male': 'TxGEqnHWrfWFTfGW9XjX',
    },
    'ko': {
        'default': HANNAH_VOICE_ID,
        'female': HANNAH_VOICE_ID,
        'male': 'TxGEqnHWrfWFTfGW9XjX',
    },
    'de': {
        'default': HANNAH_VOICE_ID,
        'female': HANNAH_VOICE_ID,
        'male': 'TxGEqnHWrfWFTfGW9XjX',
    },
    'fr': {
        'default': HANNAH_VOICE_ID,
        'female': HANNAH_VOICE_ID,
        'male': 'TxGEqnHWrfWFTfGW9XjX',
    },
    'es': {
        'default': HANNAH_VOICE_ID,
        'female': HANNAH_VOICE_ID,
        'male': 'TxGEqnHWrfWFTfGW9XjX',
    },
    'hi': {
        'default': HANNAH_VOICE_ID,
        'female': HANNAH_VOICE_ID,
        'male': 'TxGEqnHWrfWFTfGW9XjX',
    },
}

# Currency conversion rates from AUD (approximate)
CURRENCY_RATES = {
    'en': {'symbol': 'A$', 'rate': 1.0, 'name': 'Australian dollars', 'code': 'AUD'},
    'fr': {'symbol': '€', 'rate': 0.61, 'name': 'euros', 'code': 'EUR'},
    'de': {'symbol': '€', 'rate': 0.61, 'name': 'Euro', 'code': 'EUR'},
    'es': {'symbol': '€', 'rate': 0.61, 'name': 'euros', 'code': 'EUR'},
    'ja': {'symbol': '¥', 'rate': 97.5, 'name': '円', 'code': 'JPY'},
    'ko': {'symbol': '₩', 'rate': 875.0, 'name': '원', 'code': 'KRW'},
    'zh': {'symbol': '¥', 'rate': 4.72, 'name': '人民币', 'code': 'CNY'},
    'hi': {'symbol': '₹', 'rate': 54.5, 'name': 'रुपये', 'code': 'INR'},
}

def number_to_words(n, language='en'):
    """Convert a number to spoken words in the specified language"""
    if language == 'en':
        return _number_to_words_en(n)
    elif language == 'fr':
        return _number_to_words_fr(n)
    elif language == 'de':
        return _number_to_words_de(n)
    elif language == 'es':
        return _number_to_words_es(n)
    elif language == 'ja':
        return _number_to_words_ja(n)
    elif language == 'ko':
        return _number_to_words_ko(n)
    elif language == 'zh':
        return _number_to_words_zh(n)
    elif language == 'hi':
        return _number_to_words_hi(n)
    else:
        return _number_to_words_en(n)

def _number_to_words_en(n):
    """Convert number to English words"""
    if n == 0:
        return 'zero'
    
    ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
            'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
            'seventeen', 'eighteen', 'nineteen']
    tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
    
    def convert_below_thousand(num):
        if num == 0:
            return ''
        elif num < 20:
            return ones[num]
        elif num < 100:
            return tens[num // 10] + ('' if num % 10 == 0 else ' ' + ones[num % 10])
        else:
            return ones[num // 100] + ' hundred' + ('' if num % 100 == 0 else ' and ' + convert_below_thousand(num % 100))
    
    if n < 1000:
        return convert_below_thousand(n)
    elif n < 1000000:
        thousands = n // 1000
        remainder = n % 1000
        result = convert_below_thousand(thousands) + ' thousand'
        if remainder > 0:
            if remainder < 100:
                result += ' and ' + convert_below_thousand(remainder)
            else:
                result += ' ' + convert_below_thousand(remainder)
        return result
    else:
        millions = n // 1000000
        remainder = n % 1000000
        result = convert_below_thousand(millions) + ' million'
        if remainder > 0:
            if remainder < 1000:
                result += ' ' + convert_below_thousand(remainder)
            else:
                result += ' ' + _number_to_words_en(remainder)
        return result

def _number_to_words_fr(n):
    """Convert number to French words"""
    if n == 0:
        return 'zéro'
    
    ones = ['', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf',
            'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize', 'dix-sept',
            'dix-huit', 'dix-neuf']
    tens = ['', '', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 'soixante', 'quatre-vingt', 'quatre-vingt']
    
    def convert_below_hundred(num):
        if num < 20:
            return ones[num]
        elif num < 70:
            t = num // 10
            u = num % 10
            if u == 1 and t != 8:
                return tens[t] + ' et un'
            elif u == 0:
                return tens[t]
            else:
                return tens[t] + '-' + ones[u]
        elif num < 80:
            return 'soixante-' + ones[num - 60] if num != 71 else 'soixante et onze'
        elif num < 100:
            if num == 80:
                return 'quatre-vingts'
            return 'quatre-vingt-' + ones[num - 80]
        return ''
    
    def convert_below_thousand(num):
        if num < 100:
            return convert_below_hundred(num)
        else:
            h = num // 100
            r = num % 100
            if h == 1:
                return 'cent' + ('' if r == 0 else ' ' + convert_below_hundred(r))
            return ones[h] + ' cent' + ('s' if r == 0 else ' ' + convert_below_hundred(r))
    
    if n < 1000:
        return convert_below_thousand(n)
    elif n < 1000000:
        t = n // 1000
        r = n % 1000
        if t == 1:
            result = 'mille'
        else:
            result = convert_below_thousand(t) + ' mille'
        if r > 0:
            result += ' ' + convert_below_thousand(r)
        return result
    else:
        m = n // 1000000
        r = n % 1000000
        if m == 1:
            result = 'un million'
        else:
            result = convert_below_thousand(m) + ' millions'
        if r > 0:
            result += ' ' + _number_to_words_fr(r)
        return result

def _number_to_words_de(n):
    """Convert number to German words"""
    if n == 0:
        return 'null'
    
    ones = ['', 'eins', 'zwei', 'drei', 'vier', 'fünf', 'sechs', 'sieben', 'acht', 'neun',
            'zehn', 'elf', 'zwölf', 'dreizehn', 'vierzehn', 'fünfzehn', 'sechzehn',
            'siebzehn', 'achtzehn', 'neunzehn']
    tens = ['', '', 'zwanzig', 'dreißig', 'vierzig', 'fünfzig', 'sechzig', 'siebzig', 'achtzig', 'neunzig']
    
    def convert_below_hundred(num):
        if num < 20:
            return ones[num]
        elif num % 10 == 0:
            return tens[num // 10]
        else:
            u = num % 10
            t = num // 10
            unit = 'ein' if u == 1 else ones[u]
            return unit + 'und' + tens[t]
    
    def convert_below_thousand(num):
        if num < 100:
            return convert_below_hundred(num)
        else:
            h = num // 100
            r = num % 100
            return ones[h] + 'hundert' + (convert_below_hundred(r) if r > 0 else '')
    
    if n < 1000:
        return convert_below_thousand(n)
    elif n < 1000000:
        t = n // 1000
        r = n % 1000
        if t == 1:
            result = 'eintausend'
        else:
            result = convert_below_thousand(t) + 'tausend'
        if r > 0:
            result += convert_below_thousand(r)
        return result
    else:
        m = n // 1000000
        r = n % 1000000
        if m == 1:
            result = 'eine Million'
        else:
            result = convert_below_thousand(m) + ' Millionen'
        if r > 0:
            result += ' ' + _number_to_words_de(r)
        return result

def _number_to_words_es(n):
    """Convert number to Spanish words"""
    if n == 0:
        return 'cero'
    
    ones = ['', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve',
            'diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete',
            'dieciocho', 'diecinueve']
    tens = ['', '', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta', 'ochenta', 'noventa']
    
    def convert_below_hundred(num):
        if num < 20:
            return ones[num]
        elif num < 30:
            if num == 20:
                return 'veinte'
            return 'veinti' + ones[num - 20]
        elif num % 10 == 0:
            return tens[num // 10]
        else:
            return tens[num // 10] + ' y ' + ones[num % 10]
    
    def convert_below_thousand(num):
        if num < 100:
            return convert_below_hundred(num)
        elif num == 100:
            return 'cien'
        else:
            h = num // 100
            r = num % 100
            hundreds = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 
                       'quinientos', 'seiscientos', 'setecientos', 'ochocientos', 'novecientos']
            return hundreds[h] + (' ' + convert_below_hundred(r) if r > 0 else '')
    
    if n < 1000:
        return convert_below_thousand(n)
    elif n < 1000000:
        t = n // 1000
        r = n % 1000
        if t == 1:
            result = 'mil'
        else:
            result = convert_below_thousand(t) + ' mil'
        if r > 0:
            result += ' ' + convert_below_thousand(r)
        return result
    else:
        m = n // 1000000
        r = n % 1000000
        if m == 1:
            result = 'un millón'
        else:
            result = convert_below_thousand(m) + ' millones'
        if r > 0:
            result += ' ' + _number_to_words_es(r)
        return result

def _number_to_words_ja(n):
    """Convert number to Japanese words (using Arabic numerals with counter)"""
    # Japanese typically uses Arabic numerals with currency counter
    return str(n)

def _number_to_words_ko(n):
    """Convert number to Korean words (using Arabic numerals with counter)"""
    # Korean typically uses Arabic numerals with currency counter
    return str(n)

def _number_to_words_zh(n):
    """Convert number to Chinese words"""
    if n == 0:
        return '零'
    
    digits = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    units = ['', '十', '百', '千']
    big_units = ['', '万', '亿']
    
    def convert_below_ten_thousand(num):
        if num == 0:
            return ''
        result = ''
        s = str(num).zfill(4)
        for i, c in enumerate(s):
            d = int(c)
            if d != 0:
                result += digits[d] + units[3 - i]
            elif result and not result.endswith('零'):
                result += '零'
        return result.rstrip('零')
    
    if n < 10000:
        return convert_below_ten_thousand(n) or '零'
    elif n < 100000000:
        wan = n // 10000
        remainder = n % 10000
        result = convert_below_ten_thousand(wan) + '万'
        if remainder > 0:
            if remainder < 1000:
                result += '零'
            result += convert_below_ten_thousand(remainder)
        return result
    else:
        yi = n // 100000000
        remainder = n % 100000000
        result = convert_below_ten_thousand(yi) + '亿'
        if remainder > 0:
            result += _number_to_words_zh(remainder)
        return result

def _number_to_words_hi(n):
    """Convert number to Hindi words"""
    if n == 0:
        return 'शून्य'
    
    ones = ['', 'एक', 'दो', 'तीन', 'चार', 'पाँच', 'छह', 'सात', 'आठ', 'नौ',
            'दस', 'ग्यारह', 'बारह', 'तेरह', 'चौदह', 'पंद्रह', 'सोलह', 'सत्रह',
            'अठारह', 'उन्नीस']
    tens = ['', '', 'बीस', 'तीस', 'चालीस', 'पचास', 'साठ', 'सत्तर', 'अस्सी', 'नब्बे']
    
    def convert_below_hundred(num):
        if num < 20:
            return ones[num]
        elif num % 10 == 0:
            return tens[num // 10]
        else:
            return tens[num // 10] + ' ' + ones[num % 10]
    
    def convert_below_thousand(num):
        if num < 100:
            return convert_below_hundred(num)
        else:
            h = num // 100
            r = num % 100
            return ones[h] + ' सौ' + (' ' + convert_below_hundred(r) if r > 0 else '')
    
    if n < 1000:
        return convert_below_thousand(n)
    elif n < 100000:
        t = n // 1000
        r = n % 1000
        result = convert_below_thousand(t) + ' हज़ार'
        if r > 0:
            result += ' ' + convert_below_thousand(r)
        return result
    elif n < 10000000:
        l = n // 100000
        r = n % 100000
        result = convert_below_thousand(l) + ' लाख'
        if r > 0:
            result += ' ' + _number_to_words_hi(r)
        return result
    else:
        cr = n // 10000000
        r = n % 10000000
        result = convert_below_thousand(cr) + ' करोड़'
        if r > 0:
            result += ' ' + _number_to_words_hi(r)
        return result

def convert_price_for_tts(text, language='en'):
    """
    Convert price notations in text to spoken words for TTS.
    E.g., "A$1,050" -> "one thousand and fifty Australian dollars"
    Also converts currency based on the selected language.
    """
    currency_info = CURRENCY_RATES.get(language, CURRENCY_RATES['en'])
    
    # Pattern to match various price formats: A$1,050, $299, €500, ¥10000, etc.
    price_pattern = r'(A\$|AU\$|\$|€|¥|₩|₹)[\s]*([\d,]+(?:\.\d{2})?)'
    
    def replace_price(match):
        currency_symbol = match.group(1)
        amount_str = match.group(2).replace(',', '')
        
        try:
            # Parse the amount
            if '.' in amount_str:
                amount = float(amount_str)
            else:
                amount = int(amount_str)
            
            # If it's AUD (A$ or AU$ or just $), convert to target currency
            if currency_symbol in ['A$', 'AU$', '$']:
                # Convert from AUD to target currency
                converted_amount = round(amount * currency_info['rate'])
                currency_name = currency_info['name']
            else:
                # Already in some other currency, just convert to words
                converted_amount = round(amount)
                currency_name = currency_info['name']
            
            # Convert number to words
            amount_words = number_to_words(int(converted_amount), language)
            
            # Build the spoken price
            return f"{amount_words} {currency_name}"
            
        except ValueError:
            return match.group(0)
    
    return re.sub(price_pattern, replace_price, text)

def convert_price_for_display(text, language='en'):
    """
    Convert price notations in text to the appropriate currency for display.
    E.g., for French: "A$1,050" -> "€640"
    Keeps number format but changes currency symbol and converts amount.
    """
    if language == 'en':
        # No conversion needed for English/AUD
        return text
    
    currency_info = CURRENCY_RATES.get(language, CURRENCY_RATES['en'])
    
    # Pattern to match AUD price formats: A$1,050, AU$299, $500
    price_pattern = r'(A\$|AU\$|\$)([\d,]+(?:\.\d{2})?)'
    
    def replace_price(match):
        amount_str = match.group(2).replace(',', '')
        
        try:
            # Parse the amount
            if '.' in amount_str:
                amount = float(amount_str)
            else:
                amount = int(amount_str)
            
            # Convert from AUD to target currency
            converted_amount = round(amount * currency_info['rate'])
            
            # Format with the new currency symbol
            symbol = currency_info['symbol']
            
            # Format number with thousands separator based on language
            if language in ['de', 'fr', 'es']:
                # European format: use dots for thousands
                formatted_amount = f"{converted_amount:,}".replace(',', '.')
            elif language in ['ja', 'zh']:
                # Asian format: no separator for small amounts, comma for large
                formatted_amount = f"{converted_amount:,}"
            else:
                formatted_amount = f"{converted_amount:,}"
            
            return f"{symbol}{formatted_amount}"
            
        except ValueError:
            return match.group(0)
    
    return re.sub(price_pattern, replace_price, text)

def get_voice_id(language='en', gender='default'):
    """Get the appropriate voice ID for the given language and gender"""
    if language not in VOICE_MAP:
        language = 'en'
    
    if gender not in VOICE_MAP[language]:
        gender = 'default'
    
    return VOICE_MAP[language][gender]

def synthesize_speech(text, language='en', gender='default'):
    """
    Convert text to speech using ElevenLabs API
    
    Args:
        text (str): Text to convert to speech
        language (str): Language code (en, zh, ja, ko, de, fr, es, hi)
        gender (str): Voice gender (default, female, male)
    
    Returns:
        bytes: Audio data in MP3 format
        None: If synthesis fails
    """
    if not ELEVENLABS_API_KEY:
        print("❌ ElevenLabs API key not found in .env file")
        return None
    
    voice_id = get_voice_id(language, gender)
    url = f"{ELEVENLABS_API_URL}/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    # Convert prices to spoken words for natural TTS pronunciation
    # E.g., "A$1,050" -> "one thousand and fifty Australian dollars"
    tts_text = convert_price_for_tts(text, language)
    
    print(f"🔊 TTS text conversion: '{text[:100]}...' -> '{tts_text[:100]}...'")
    
    data = {
        "text": tts_text,
        "model_id": "eleven_multilingual_v2",  # Supports all languages
        "voice_settings": {
            "stability": 0.5,        # Balance between consistency and expressiveness
            "similarity_boost": 0.75, # How much it sounds like the original voice
            "style": 0.0,            # Exaggeration level (0 = natural)
            "use_speaker_boost": True
        }
    }
    
    try:
        print(f"🎤 ElevenLabs: Synthesizing {len(tts_text)} chars in {language}...")
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ ElevenLabs: Success! Generated {len(response.content)} bytes")
            return response.content
        else:
            print(f"❌ ElevenLabs error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ ElevenLabs: Request timeout")
        return None
    except Exception as e:
        print(f"❌ ElevenLabs error: {str(e)}")
        return None

def is_configured():
    """Check if ElevenLabs is properly configured"""
    return bool(ELEVENLABS_API_KEY)

if __name__ == "__main__":
    # Test the integration
    if is_configured():
        print("✅ ElevenLabs API key found")
        print("Testing synthesis...")
        
        test_text = "Hello! I'm your AI tour assistant. Welcome to the Whitsundays!"
        audio = synthesize_speech(test_text, language='en')
        
        if audio:
            # Save test audio
            with open('test_elevenlabs.mp3', 'wb') as f:
                f.write(audio)
            print("✅ Test audio saved as test_elevenlabs.mp3")
        else:
            print("❌ Synthesis failed")
    else:
        print("❌ ElevenLabs API key not found")
        print("   Add ELEVENLABS_API_KEY to your .env file")






















