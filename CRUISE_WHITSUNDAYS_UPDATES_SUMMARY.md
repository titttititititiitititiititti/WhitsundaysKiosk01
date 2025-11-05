# Cruise Whitsundays Tour Updates - November 5, 2025

## Summary
Updated departure and return times for 10 Cruise Whitsundays tours, removed 2 duplicate listings, and renamed 1 tour.

---

## Files Updated

### Main Files:
1. ✅ `tours_cruisewhitsundays_cleaned.csv`
2. ✅ `data/cruisewhitsundays/en/tours_cruisewhitsundays_cleaned_with_media.csv`

### Language Files (Still Need Updates):
- `data/cruisewhitsundays/zh/tours_cruisewhitsundays_cleaned_with_media.csv` (Chinese)
- `data/cruisewhitsundays/ja/tours_cruisewhitsundays_cleaned_with_media.csv` (Japanese)
- `data/cruisewhitsundays/ko/tours_cruisewhitsundays_cleaned_with_media.csv` (Korean)
- `data/cruisewhitsundays/de/tours_cruisewhitsundays_cleaned_with_media.csv` (German)
- `data/cruisewhitsundays/fr/tours_cruisewhitsundays_cleaned_with_media.csv` (French)
- `data/cruisewhitsundays/es/tours_cruisewhitsundays_cleaned_with_media.csv` (Spanish)
- `data/cruisewhitsundays/hi/tours_cruisewhitsundays_cleaned_with_media.csv` (Hindi)

---

## Changes Made

### 1. **Whitehaven Beach & Hill Inlet Chill & Grill** ✅
**Tour ID:** `whitehaven_beach___hill_inlet_chill___grill`

**UPDATED:**
- **Departure Times:** `Departs: 7:15am | Returns: 6:00pm`

---

### 2. **Camira Sailing Adventure** ✅
**Tour ID:** `camira_sailing_adventure`

**ACTIONS:**
- ✅ **Removed duplicate listing** (kept first entry, deleted second)
- ✅ **Added:** `Port of Airlie, Departs: 8:15am | Returns: 5:30pm`

---

### 3. **Reefsuites Underwater Accommodation** ✅
**Tour ID:** `reefsuites`

**UPDATED:**
- **Duration:** Changed from `2 Days 1 Night` to `Overnight`
- **Departure Times:** `Departs: 8:00am | Returns: 6:10pm (next day)`

---

### 4. **Reefsleep** ✅
**Tour ID:** `reefsleep`

**UPDATED:**
- **Duration:** Changed from `2 Days 1 Night` to `Overnight`
- **Departure Times:** `Departs: 8:00am | Returns: 6:10pm (next day)`

---

### 5. **Scenic Whitsunday Islands Cruise** ✅
**Tour ID:** `cruising_nomads`

**UPDATED:**
- **Name Changed:** `Scenic Whitsunday Islands Cruise` → `Cruising Nomads Islands Cruise`
- **Departure Times:** 
  - `Port of Airlie Departs: 10:30am | Returns: 1:20pm OR`
  - `Port of Airlie Departs: 12:50pm | Returns: 3:40pm`

---

### 6. **Whitehaven Beach Morning or Afternoon Cruise** ✅
**Tour ID:** `whitehaven_beach_morning_or_afternoon_cruise`

**UPDATED:**
- **Departure Times:** 
  - **Morning:** `Port of Airlie Departs: 7:15am | Returns: 2:20pm OR`
  - **Afternoon:** `Port of Airlie Departs: 11:35am | Returns: 6:00pm`

---

### 7. **Great Barrier Reef Full Day Adventure** ✅
**Tour ID:** `great_barrier_reef_full_day_adventure`

**ACTIONS:**
- ✅ **Kept this tour** (removed duplicate "Great Barrier Reef Adventure")
- ✅ **Added:** `Departs: 8:00am | Returns: 6:10pm`

---

### 8. **Great Barrier Reef Adventure** ❌ REMOVED
**Tour ID:** `ultimate_whitsundays_combo`

**ACTION:**
- ✅ **DELETED** - This was a duplicate of "Great Barrier Reef Full Day Adventure"

---

### 9. **Whitehaven Beach & Hamilton Island Tour** ✅
**Tour ID:** `whitehaven_beach___hamilton_island_tour`

**UPDATED:**
- **Departure Times:** `Departs: 7:15am | Returns: 6:00pm`

---

### 10. **Hamilton Island Freestyle** ✅
**Tour ID:** `hamilton_island_freestyle`

**UPDATED:**
- **Departure Times:** `Departs: 7:15am | Returns: 6:10pm`

---

### 11. **Daydream Island Escape** ✅
**Tour ID:** `daydream_island_escape`

**UPDATED:**
- **Departure Times:** `Departs: 8:20am | Returns: 5:20pm`

---

## Summary Statistics

- ✅ **10 tours updated** with departure/return times
- ✅ **2 duplicate tours removed** (Camira Sailing Adventure, Great Barrier Reef Adventure)
- ✅ **1 tour renamed** (Scenic Whitsunday Islands Cruise → Cruising Nomads Islands Cruise)
- ✅ **2 duration formats updated** (Reefsuites, Reefsleep: "2 Days 1 Night" → "Overnight")

---

## Next Steps

### Recommended:
1. **Restart Flask App** to load the updated tour data
2. **Test each tour** in the kiosk to verify times display correctly
3. **Update language-specific CSV files** if multilingual support is needed
4. **Verify tour filtering** still works correctly with updated data

### Testing Checklist:
- [ ] Whitehaven Beach & Hill Inlet Chill & Grill shows 7:15am departure
- [ ] Only ONE Camira Sailing Adventure appears (8:15am departure)
- [ ] Reefsuites shows overnight duration with next-day return
- [ ] Reefsleep shows overnight duration with next-day return
- [ ] Tour is now called "Cruising Nomads Islands Cruise" with 2 time options
- [ ] Whitehaven Beach Morning/Afternoon shows both time options
- [ ] Only ONE Great Barrier Reef tour appears (Full Day Adventure, 8:00am)
- [ ] Hamilton Island tours show correct times
- [ ] Daydream Island shows 8:20am departure

---

## Notes

- All times are in local Port of Airlie timezone
- Overnight tours clearly indicate "next day" return
- Tours with multiple departure options use "OR" separator
- All updates maintain CSV format integrity
- No pricing or other data was modified

---

**Updated By:** AI Assistant  
**Date:** November 5, 2025  
**Status:** ✅ COMPLETE (Main English files updated)

