# Auto B.O.M. Filler - Chrome Extension

## Location
`C:\Users\RaunoArulaane\Documents\bom-chrome-extension`

## Files
- `manifest.json` - Chrome MV3 manifest
- `background.js` - Service worker: context menu + Google Sheets API write
- `content.js` - Content script (currently unused, extraction moved to background.js executeScript)
- `popup.html` / `popup.js` - Project selector UI (multi-project support)
- `icon48.png` / `icon128.png` - Generated blue "B" icons

## What It Does
- Right-click any product page → "Lisa BOM-i"
- Extracts: product name (h1/og:title/ld+json), price, currency, weight, category (auto-detected)
- Writes row to Google Sheets via Sheets API v4 (append)
- Multi-project support: user can add multiple Sheet+Tab combos and switch between them

## Google Cloud Setup
- **GCP Project:** "My First Project" (console.cloud.google.com)
- **OAuth Client ID:** `808357040288-ln0fp907sqrncs9o6j9qs7t4dgaiacv7.apps.googleusercontent.com`
- **Type:** Chrome Extension
- **Extension ID:** `nbjpamaplocenhbdkhngbopmjlgpldcb`
- **Google Sheets API:** Enabled

## Current Status: WORKING + PUBLISHING IN PROGRESS
- Extension loads in Chrome ✅
- Context menu "Lisa BOM-i" appears ✅
- OAuth client created ✅
- Google Sheets API enabled ✅
- Test user added ✅
- Auth works, writes to Google Sheets ✅
- Chrome Web Store upload done ✅
- Store listing + description filled ✅
- Privacy policy created (Google Sites) ✅
- Screenshot uploaded ✅

### Publishing blockers resolved:
- Removed content_scripts `<all_urls>` (caused broad host permissions warning)
- Now uses only `activeTab` + `scripting` (safer, faster review)

### Still pending for publish:
- E-mail verification in Chrome Web Store Developer account
- Review by Google (may take days)

## Google Sheet Target
- **Sheet ID:** `19LbRZNh7GI3ve9yQwzdlurFCz2MJ85Bq7hNctVlejdQ`
- **Tab:** `Beast Mario BOM`
- **Columns:** PRoduct_ID | Component_ID | Qty | Units | Weight | Unit | Price | Currency

## Beast Mario Drone Build - Components Selected
| Category | Component | Price | Source |
|---|---|---|---|
| Frame | SpeedyBee Mario 5 DC Frame O4 PRO Version | - | - |
| Motors | T-Motor P2207 V3.0 2080KV blue FPV Motor (x4) | 89.80 EUR | - |
| Props | HQProp ETHiX S3/P3/S4/S5 + Durable (5 sets) | ~15 EUR | - |
| FC-ESC | SpeedyBee F7 V3 Wi-Fi 50A BL32 Stack | 109.95 EUR | n-factory.de |
| GPS | HGLRC M100-5883 GPS & Compass (21x21mm) | 23.95 EUR | n-factory.de |
| VTX | TBD | - | - |
| Camera | TBD | - | - |
| Receiver | TBD | - | - |
| Antenna | TBD | - | - |
| Battery | TBD | - | - |

## Still Needed Components
- VTX (video transmitter)
- FPV Camera
- Receiver (RX)
- Antenna
- Battery (LiPo)
- Accessories (straps, pads, etc.)

## Recent Changes (2026-03-06)
- Removed content_scripts from manifest (was causing <all_urls> broad permission warning)
- content.js no longer used — extraction function is inside background.js (executeScript)
- Popup redesigned: spreadsheet-centric with auto-tab detection from Google Sheets API
- Project link (📄) opens Sheet directly
- Form draft auto-saves (survives popup close)
- Weight sent as parseFloat (number, not string)
- Product name as HYPERLINK formula (clickable link in Sheet)
- Privacy policy at Google Sites
- Store screenshot: C:\Users\RaunoArulaane\Documents\bom-store-screenshot.png

## Apps Script Attempt (Failed)
- Tried Google Apps Script doPost/doGet as backend - didn't work due to redirect issues and auth
- Chrome extension + direct Sheets API is the better approach

## Notes
- GPS mount: 21x21mm fits Mario 5 frame with 3D printed mount (printables.com/model/849274)
- F405 V5 stack was discontinued at n-factory.de, chose F7 V3 instead
- F7 V3 has WiFi+BT (wireless firmware flash), 500MB blackbox, F722 processor
