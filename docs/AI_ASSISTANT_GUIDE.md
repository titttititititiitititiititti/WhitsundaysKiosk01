# AI Assistant Technical Guide

> **IMPORTANT**: This document describes exactly how the AI Assistant feature works as of January 2026. If the AI assistant breaks, refer to this guide to restore it to working condition.

## Overview

The AI Assistant helps users find tours through natural conversation. It:
1. Listens to user preferences (activity type, duration, group type)
2. Pre-fetches matching tours BEFORE calling OpenAI
3. Provides the AI with EXACT tour data to describe
4. Uses TTS (ElevenLabs) to speak responses with synchronized tour card highlighting
5. Shows visual feedback through the particle orb visualizer

---

## Critical Architecture

### The Flow (DO NOT CHANGE THIS ORDER)

```
1. User sends message
         ↓
2. /chat/preflight endpoint (FAST - ~10ms)
   - Calls extract_tour_filters()
   - Returns {will_search_tours: true/false}
         ↓
3. Frontend shows animation:
   - If will_search_tours=true → Show "Finding tours..." overlay IMMEDIATELY
   - If will_search_tours=false → Show typing dots
         ↓
4. /chat endpoint (main processing)
   a) extract_tour_filters() - detect duration/activity from message
   b) If filters found → apply_filters() to get MATCHING tours
   c) Sort by promotion status (popular/featured/best_value first)
   d) Limit to TOP 3 tours
   e) Build specific_tours_section with EXACT tour names/details
   f) Send to OpenAI with strict instructions to describe THOSE EXACT tours
   g) Return {message, recommended_tours: [...]}
         ↓
5. Frontend receives response
   - Parse AI text into chunks (intro, tour1, tour2, tour3, outro)
   - Display tour cards from recommended_tours array
   - Start TTS playback with chunk-to-card mapping
         ↓
6. TTS + Card Highlighting
   - Chunk 1 (intro) → No card highlighted
   - Chunk 2 → Highlight card 1
   - Chunk 3 → Highlight card 2
   - Chunk 4 → Highlight card 3
   - Cards show slideshow + flashing highlights while speaking
```

---

## Key Files

### Backend (app.py)

#### `/chat/preflight` endpoint
```python
@app.route('/chat/preflight', methods=['POST'])
def chat_preflight():
    """Quick check if chat will search for tours - returns immediately for UI feedback"""
    detected_filters = extract_tour_filters(user_message, conversation_history)
    return jsonify({'will_search_tours': detected_filters is not None})
```

#### `extract_tour_filters()` function
Extracts filter criteria from user message. **CRITICAL: Order matters - more specific first!**

```python
def extract_tour_filters(user_message, conversation_history):
    # PRIORITIZE user's current message (not assistant history which mentions all activities)
    current_msg = user_message.lower()
    
    # Only use USER messages from history (skip assistant messages)
    user_history = ""
    for msg in conversation_history[-4:]:
        if msg.get('role') == 'user':
            user_history += " " + msg.get('content', '').lower()
    
    # SPECIFIC ACTIVITIES FIRST (more restrictive)
    if 'scuba' or 'diving' in current_msg → activity = 'diving'
    elif 'whitehaven' in current_msg → activity = 'whitehaven_beach'
    elif 'snorkel' in current_msg → activity = 'snorkeling'
    elif 'reef' in current_msg → activity = 'great_barrier_reef'
    elif 'sail' in current_msg → activity = 'island_tours'
    
    # Duration detection
    if 'full day' → duration = 'full_day'
    if 'half day' → duration = 'half_day'
    if 'multi-day' → duration = 'multi_day'
```

#### `apply_filters()` function
Filters tours by criteria. **Activity matching in `tour_matches_any_activity()`:**

- `diving` → Only tours with "dive/diving/scuba" in NAME (strict)
- `snorkeling` → Tours with "snorkel" (but not diving tours)
- `great_barrier_reef` → Any tour with "reef" (broad)
- `whitehaven_beach` → Tours with "whitehaven"
- `island_tours` → Sailing/cruise tours

#### `specific_tours_section` in system prompt
**CRITICAL**: When tours are pre-fetched, the AI is given EXACT tour names and told to use them:

```
═══════════════════════════════════════════════════════════════
🚨 CRITICAL: YOU MUST DESCRIBE THESE EXACT TOURS IN THIS EXACT ORDER!
═══════════════════════════════════════════════════════════════

━━━ TOUR #1 (describe this as number 1) ━━━
NAME: "Bowen Reef Diving Tour" ← USE THIS EXACT NAME
Company: Airlie Beach Diving
Price: A$145
Duration: 6 Hours
Highlights: [actual highlights from CSV]

━━━ TOUR #2 (describe this as number 2) ━━━
NAME: "Ocean Free Dive Experience" ← USE THIS EXACT NAME
...

YOUR OUTPUT FORMAT (COPY THIS STRUCTURE EXACTLY):
"Here are some incredible options for you! 🌊

1. **Bowen Reef Diving Tour** - [2-3 exciting sentences...]

2. **Ocean Free Dive Experience** - [2-3 exciting sentences...]

3. **Third Tour Name** - [2-3 exciting sentences...]

Would you like more details on any of these? 🌟"
```

---

### Frontend (templates/index.html)

#### TTS Chunking System
```javascript
function splitIntoChunks(text) {
    // Split by numbered items: "1. **Tour Name**" etc.
    // This ensures: chunk 0 = intro, chunk 1 = tour 1, chunk 2 = tour 2...
    const hasNumberedList = /\d+\.\s*\*?\*?[A-Z]/.test(text);
    if (hasNumberedList) {
        const parts = text.split(/(?=\d+\.\s*\*?\*?[A-Z])/);
        return parts.filter(p => p.trim());
    }
}
```

#### Chunk-to-Card Mapping
```javascript
// In playNextInQueue():
const cardIndex = ttsCurrentChunkIndex - 1; // Chunk 0 = intro, chunk 1 = card 0, etc.
if (cardIndex >= 0 && cardIndex < currentAITourCards.length) {
    highlightCardByIndex(cardIndex);
} else {
    clearSpeakingHighlights(); // Intro/outro - no card
}
```

#### Card Highlighting Effects
When a card is highlighted (`speaking` class):
- Card gets golden glow border
- Image cycles through gallery (slideshow)
- Info sections flash sequentially (departure, highlight, price)
- Card scales slightly larger

---

## Promotion System

### Agent Settings (`config/agent_settings.json`)
```json
{
    "promoted_tours": {
        "popular": ["company__tour_id", ...],
        "featured": ["company__tour_id", ...],
        "best_value": ["company__tour_id", ...]
    }
}
```

### Sorting by Promotion
In `/chat` endpoint and `apply_filters()`:
```python
promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
tours.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
```

**Result**: Popular tours appear FIRST in recommendations when they match the user's criteria.

---

## Orb Visualizer States

### Visual States
| State | Appearance | Trigger |
|-------|------------|---------|
| Idle | Gentle floating animation | No activity |
| Loading | Pulsing brightness | Waiting for API |
| Searching | Faster spin, larger, rainbow hue | `will_search_tours=true` |
| Speaking | Audio-reactive particles | TTS playing |
| Muted | Grayed out + 🔇 icon | User taps orb |

### Mute Toggle
User can tap the orb to mute/unmute TTS:
- Tap → `ttsMuted = true` → Pause audio, gray out orb, show "🔇 Tap orb to unmute"
- Tap again → Resume playback, restore orb colors

---

## Common Issues & Fixes

### "Same tours for different questions"
**Cause**: Filter detection too broad or promoted tours always sorted first regardless of match.
**Fix**: 
1. Check `extract_tour_filters()` is detecting correct activity
2. Ensure `apply_filters()` actually filters before sorting by promotion

### "AI describes wrong tours"
**Cause**: `specific_tours_section` not included in prompt, or AI ignoring it.
**Fix**: 
1. Verify `pre_fetched_tours` is populated
2. Check system prompt includes the exact tour names
3. Make prompt instructions VERY explicit (tour names in quotes, numbered format)

### "TTS highlighting wrong cards"
**Cause**: AI response not in numbered format, or chunk splitting broken.
**Fix**:
1. Verify AI outputs "1. **Tour Name** - description\n\n2. **Tour Name** - ..."
2. Check `splitIntoChunks()` regex matches the format
3. Ensure `currentAITourCards` array order matches AI description order

### "Loading animation shows after response"
**Cause**: `/chat/preflight` not being called, or not showing animation on `will_search_tours=true`.
**Fix**:
1. Verify preflight fetch happens BEFORE main /chat fetch
2. Check `if (preflightData.will_search_tours)` branch creates overlay

### "Orb not graying out on mute"
**Cause**: CSS not applied or `ttsMuted` variable not updating.
**Fix**:
1. Verify `.ai-visualizer-container.muted` CSS exists
2. Check `toggleTTSMute()` function adds/removes `muted` class

---

## Testing Checklist

1. **Different activity queries should return different tours:**
   - "full day whitehaven beach" → Whitehaven tours
   - "full day scuba diving" → Actual dive tours (not just reef)
   - "full day reef tours" → General reef/snorkel tours

2. **Loading animation timing:**
   - Animation should appear IMMEDIATELY after sending message (not after response)
   - This happens because preflight returns instantly

3. **TTS + Card sync:**
   - Intro plays → No card highlighted
   - Tour 1 description plays → Card 1 highlighted
   - Tour 2 description plays → Card 2 highlighted
   - etc.

4. **Promoted tours:**
   - If a popular tour matches the filter, it should appear first
   - The AI should be extra enthusiastic about popular tours

5. **Mute toggle:**
   - Tap orb → Audio pauses, orb grays out, shows 🔇 indicator
   - Tap again → Audio resumes, orb colors restore

---

## Key Variables to Check

### Backend (app.py)
- `pre_fetched_tours` - Should have 3 tours when filters detected
- `specific_tours_section` - Should contain exact tour names
- `detected_filters` - Should show correct activity/duration

### Frontend (index.html)
- `currentAITourCards` - Array of tour objects being displayed
- `ttsChunkTourMap` - Maps chunk index to tour names
- `ttsMuted` - Mute state
- `preflightData.will_search_tours` - Whether searching animation shown early

---

## Console Log Patterns (What to Look For)

### Successful flow:
```
🔍 Preflight: Tours will be searched - showing animation immediately
💬 CHAT REQUEST:
   User message: 'full day scuba diving tours'
🎯 DETECTED FILTERS: {'duration': 'full_day', 'activity': 'diving'}
   Found 3 tours to describe:
      - Bowen Reef Diving Tour 🔥 popular
      - Ocean Free Dive Experience
      - Whitsunday Dive Adventure
📦 Using full tour objects from API: (3) ['Bowen Reef Diving Tour', ...]
📝 Smart split: 4 chunks (intro + 3 tours)
🎙️ Chunk 1 → No card (intro/outro)
🎙️ Chunk 2 → Highlighting card 1: Bowen Reef Diving Tour
🎙️ Chunk 3 → Highlighting card 2: Ocean Free Dive Experience
🎙️ Chunk 4 → Highlighting card 3: Whitsunday Dive Adventure
```

---

## Entry Flow

### AI Splash Screen
When user clicks "Talk To Our AI Assistant":
1. **Splash Screen** appears first (if no existing conversation)
   - Full-screen video background (NO blur) from Streamable
   - Big text: "AI Tour Booking Assistant" + "Tap Here to Begin"
   - Pulsing tap indicator
2. User taps anywhere on splash screen
3. Splash fades out, AI chat page fades in
4. Welcome message plays

If user has an existing conversation, splash is skipped and chat resumes.

---

## Version History

- **2026-01-14**: Added AI splash screen with video background, improved mute toggle
- **2026-01-14**: Documented working implementation after fixing:
  - Specific activity filters (diving vs snorkeling vs reef)
  - Preflight endpoint for instant loading animation
  - Orb tap-to-mute functionality
  - Strict AI prompt for exact tour names

