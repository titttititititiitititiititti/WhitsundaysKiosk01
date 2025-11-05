# 🤖 AI Chat Assistant - Whitsundays Tour Kiosk

## Overview
An AI-powered conversational assistant that helps visitors discover the perfect tours through natural language conversations. Results are displayed in the main tour grid just like filtered results!

## Features Implemented ✅

### Phase 1: Text-Based AI Assistant
1. **Smart Query Understanding**
   - AI analyzes user intent and preferences
   - Understands natural language in all 8 supported languages
   - Contextual conversation with memory

2. **Tour Matching**
   - Automatically categorizes 91+ tours by type
   - Matches user preferences to relevant tours
   - Recommends 2-3 best-fit tours

3. **Guided Conversational Flow** ⭐ IMPROVED
   - **Step-by-step questioning**: Asks ONE preference at a time
   - Guides users through: Interest → Duration → Vibe → Group → Budget
   - Keeps responses SHORT (1-2 sentences)
   - Natural, friendly personality like a local expert
   - **STRICT preference matching**: Only recommends tours that match ALL collected criteria
   - If user says "multi-day", only shows multi-day tours (NOT half-day!)
   - If user wants "cheapest", finds the lowest price that matches their other preferences

4. **Integrated Display** ⭐ NEW
   - Chat bubble enlarges when user starts typing
   - Recommended tours appear in **main tour grid**
   - Header changes to: **"🤖 Recommended by our Tour-Bot based on your preferences"**
   - Shows your query: *"You asked: [your question]"*
   - "Clear & Start Over" button to reset everything

5. **Tour Knowledge Base**
   - Great Barrier Reef Tours
   - Whitehaven Beach Tours
   - Sailing & Cruises
   - Diving & Snorkeling
   - Scenic Tours (helicopter, seaplane)

## How It Works

### Backend (`app.py`)
- **`/chat` endpoint**: Handles all AI conversations
- **`build_tour_context()`**: Creates tour knowledge for AI
- **GPT-4o integration**: Powers intelligent responses
- **Tour extraction**: Parses AI recommendations

### Frontend (`templates/index.html`)
- **Floating chat button**: Bottom-left corner (💬)
- **Chat interface**: Modern chat UI with message history
- **Real-time responses**: Loading animations while AI thinks
- **Tour cards**: Clickable recommended tours
- **Multi-language**: Works with all kiosk languages

## Usage

### For Users
1. Click the 💬 chat button (bottom-left)
2. Start typing - **chat enlarges automatically!**
3. Send your message
4. **Tours appear in the main grid** with AI banner
5. Click any tour card to view full details
6. Click "Clear & Start Over" to reset

### Example Queries
- "What tours do you recommend?"
- "I want to see the Great Barrier Reef"
- "Family-friendly tours under $200"
- "Half-day sailing tours"
- "Best snorkeling experiences"
- "Helicopter tours with scenic views"

## Technical Details

### API Endpoint
```
POST /chat
{
  "message": "user query",
  "language": "en",
  "history": [...]
}
```

### Response Format
```
{
  "success": true,
  "message": "AI response text",
  "recommended_tours": [...],
  "tour_keys": [...]
}
```

### Configuration
- Model: GPT-4o
- Max tokens: 500
- Temperature: 0.7
- Conversation memory: Last 3 exchanges

## Next Steps (Phase 2)

### Speech Integration 🎤
1. **Speech-to-Text**
   - User speaks → converts to text
   - Multi-language speech recognition
   - Touchscreen-friendly mic button

2. **Text-to-Speech**
   - AI responses spoken back
   - Natural voice synthesis
   - Language-specific voices

### Suggested Libraries
- Web Speech API (built-in browser)
- Google Cloud Speech-to-Text
- Azure Speech Services

## Testing

Try these test queries:
- ✅ "What tours do you recommend?"
- ✅ "I want to see whitehaven beach"
- ✅ "Great barrier reef snorkeling"
- ✅ "Family friendly sailing"
- ✅ "Budget under $150"
- ✅ "Full day adventures"

## Performance
- Average response time: 2-4 seconds
- Tour categorization: Instant
- Conversation memory: Last 6 messages
- Max recommendations: 3 tours per response

---

Built with ❤️ for the Whitsundays Visitor Kiosk

