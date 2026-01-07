"""
ElevenLabs Text-to-Speech Integration
Provides premium AI voice synthesis for the tour kiosk
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Voice IDs for different languages and styles
# Hannah - Natural Australian Voice (matches welcome message!)
HANNAH_VOICE_ID = 'M7ya1YbaeFaPXljg9BpK'

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
        'default': HANNAH_VOICE_ID,
        'female': HANNAH_VOICE_ID,
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
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",  # Supports all languages
        "voice_settings": {
            "stability": 0.5,        # Balance between consistency and expressiveness
            "similarity_boost": 0.75, # How much it sounds like the original voice
            "style": 0.0,            # Exaggeration level (0 = natural)
            "use_speaker_boost": True
        }
    }
    
    try:
        print(f"🎤 ElevenLabs: Synthesizing {len(text)} chars in {language}...")
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






















