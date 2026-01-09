# Tour Detail Page Formatting Fix - Complete Guide

## The Problem

Browse All Tours mode tour detail pages looked messy and inconsistent, while Quick Decision mode pages looked perfect with symmetrical, evenly-spaced sections. Despite multiple attempts, the formatting kept breaking.

## Root Cause Analysis

The issue was **CSS specificity conflicts** combined with **inline styles overriding CSS classes**.

### Why It Kept Breaking

1. **Inline styles in JavaScript**: The `openTourDetail()` function was adding inline styles like:
   ```javascript
   info += '<div class="swipe-expanded-details" style="opacity:1;animation:none;max-width:none;width:100%;padding:0 10px;">';
   ```
   These inline styles **override CSS classes**, so the nice grid layout CSS was being ignored.

2. **Multiple conflicting CSS rules**: There were at least 3 different places in the CSS targeting `#detail-info > div`:
   - Line ~1011: `.tour-detail-page #detail-info > div { width: calc(100% - 16px) !important; }`
   - Line ~7796: `.tour-detail-page #detail-info > div { width: calc(100% - 12px) !important; }`
   - Line ~9575: `#detail-info > div { width: 100% !important; min-width: 100% !important; }`
   
   All of these forced child divs to full width, which **broke the CSS grid layout**.

3. **Wrong container structure**: Browse All Tours was putting sections outside `.swipe-expanded-details` with custom inline styles, while Quick Decision put everything inside and let CSS handle it.

## The Fix - Step by Step

### Step 1: Find the Working Reference

First, locate how Quick Decision mode renders tour details. Search for:
```
grep "swipe-expanded-details" templates/index.html
```

Found at line ~12341:
```javascript
let detailsHtml = '<div class="swipe-expanded-details slide-up-fade">';
```
Note: NO inline styles - just clean CSS classes.

### Step 2: Find the Broken Code

Search for where Browse All Tours renders:
```
grep "openTourDetail" templates/index.html
```

Found the problematic code at line ~17031:
```javascript
info += '<div class="swipe-expanded-details" style="opacity:1;animation:none;max-width:none;width:100%;padding:0 10px;box-sizing:border-box;">';
```

### Step 3: Remove Inline Styles from JavaScript

Changed from:
```javascript
info += '<div class="swipe-expanded-details" style="opacity:1;animation:none;max-width:none;width:100%;padding:0 10px;box-sizing:border-box;">';
```

To:
```javascript
info += '<div class="swipe-expanded-details">';
```

Also removed `style="opacity:1;animation:none;"` from all child `swipe-detail-section` divs.

### Step 4: Add CSS Exclusions for the Grid Container

The existing CSS rules were forcing ALL children of `#detail-info` to full width. Added `:not()` exclusions:

**Before:**
```css
.tour-detail-page #detail-info > div {
  width: 100% !important;
  /* ... */
}
```

**After:**
```css
.tour-detail-page #detail-info > div:not(.swipe-expanded-details) {
  width: 100% !important;
  /* ... */
}
```

Applied this exclusion to ALL THREE locations in the CSS where `#detail-info > div` was targeted.

### Step 5: Add Specific CSS Rules for the Grid

Added new CSS rules to FORCE the grid layout to work:

```css
/* EXCEPTION: Preserve swipe-expanded-details grid layout */
.tour-detail-page #detail-info .swipe-expanded-details,
#detail-info .swipe-expanded-details {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)) !important;
  gap: 20px !important;
  width: 100% !important;
  max-width: 900px !important;
  margin: 0 auto !important;
  padding: 15px 0 !important;
}

/* Let grid control child sizing */
.tour-detail-page #detail-info .swipe-expanded-details > .swipe-detail-section,
#detail-info .swipe-expanded-details > .swipe-detail-section {
  width: auto !important;
  min-width: 0 !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 20px 25px !important;
  flex: none !important;
}

/* Full width sections span all columns */
.tour-detail-page #detail-info .swipe-expanded-details > .swipe-detail-section.description-section,
#detail-info .swipe-expanded-details > .swipe-detail-section.description-section {
  grid-column: 1 / -1 !important;
}
```

### Step 6: Implement Smart Section Pairing

Quick Decision mode pairs related sections side-by-side. Implemented the same logic:

```javascript
// Check what sections exist
const hasHighlights = data.highlights && ...;
const hasIncludes = data.includes && ...;

// If both exist, they pair. If one is alone, it spans full width
if (hasHighlights) {
  const highlightsClass = !hasIncludes ? 'description-section' : '';
  info += `<div class="swipe-detail-section ${highlightsClass}">...`;
}
```

**Pairing Logic:**
- Ages ↔ Ideal For (side by side if both exist)
- Highlights ↔ What's Included
- Itinerary ↔ Menu
- What to Bring ↔ What's Extra
- If one section is missing, the other spans full width (`description-section` class)

### Step 7: Move All Sections Inside the Grid

Previously, some sections (Ages, Ideal For, Itinerary, Menu) were rendered OUTSIDE the `.swipe-expanded-details` container with custom inline styles. Moved them all inside.

## Key CSS Classes

| Class | Purpose |
|-------|---------|
| `.swipe-expanded-details` | Grid container - `display: grid` with auto-fit columns |
| `.swipe-detail-section` | Individual section box - white background, rounded corners |
| `.description-section` | Makes section span full width (`grid-column: 1 / -1`) |

## Debugging Checklist

When this breaks again, check:

1. **Search for inline styles**: `grep "swipe-expanded-details.*style=" templates/index.html`
2. **Check CSS specificity**: Look for rules targeting `#detail-info > div` without `:not()` exclusions
3. **Verify grid is working**: In browser dev tools, check if `.swipe-expanded-details` has `display: grid`
4. **Check child widths**: Children should have `width: auto`, not `width: 100%`
5. **Compare with Quick Decision**: The exact same CSS classes should produce the same result

## Files Modified

- `templates/index.html`:
  - Lines ~1011, ~7796, ~9575: Added `:not(.swipe-expanded-details)` exclusions
  - Lines ~9585-9613: Added new CSS rules for grid preservation
  - Lines ~16940-17180: Rewrote `openTourDetail()` section rendering to match Quick Decision

## Test Cases

1. Open a tour from Browse All Tours - sections should be in a 2-column grid
2. Open same tour from Quick Decision - should look identical
3. Resize window - grid should collapse to single column on mobile
4. Sections with pairs (Highlights + Includes) should be side-by-side
5. Sections alone (About This Tour) should span full width

## Summary

The fix required:
1. **Remove inline styles** from JavaScript
2. **Add CSS exclusions** so general rules don't override the grid
3. **Add specific CSS rules** to force the grid layout
4. **Match the JavaScript structure** to Quick Decision mode

The key insight: **CSS grid only works if nothing else is forcing the children to be full width**.


