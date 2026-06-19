# Drone Test Report App - Electric Wings Group OÜ

## Project File
`C:\Users\RaunoArulaane\Documents\drone-test\Drone test raport generator.html`
Single HTML file (~3000 lines), all CSS + JS embedded. Vanilla JS, no frameworks.

## What It Does
Mobile-first web app for drone flight test logging, reporting, and comparison.

## Company
**Electric Wings Group OÜ** - displayed in header ("EWG Test Raport") and on printed reports.

## Data Model (localStorage)
- **Batteries** (`droneTestApp_batteries`) - separate entities: name, type (LiPo/Li-Ion/NiMH), cells (4S-12S), capacity (mAh), voltage, weight, notes
- **Payloads** (`droneTestApp_payloads`) - separate entities: name, weight, description, notes (e.g. cameras, LiDAR, packages)
- **Drones** (`droneTestApp_drones`) - droneWeight, payloadIds[] (compatible payloads), batteryIds[] (compatible batteries), technical specs (frame, motors, ESC, FC, props, VTX, notes) - all optional except name and weight
- **Logs** (`droneTestApp_logs`) - droneId, batteryId, payloadId, dateTime, location (GPS), weather data, flight results (distance, duration, battery voltages), conditions, notes
- **Settings** (`droneTestApp_settings`) - OpenWeatherMap API key (optional), lastLocation

## UI Structure (4 tabs, bottom nav on mobile)
1. **Logid** - log list, search, compare mode (select 2+ → comparison table)
2. **Uus Logi** - form: drone select → battery dropdown (compatible shown first), GPS + auto weather, flight results
3. **Droonid** - drone cards + "Akud" button opens battery management modal
4. **Veel** - API key settings, import/export (JSON + text), statistics

## Weather Sources (4, auto-tried in order)
1. **Open-Meteo** - NO API key, GPS-based, most reliable
2. **Ilmateenistus.ee XML** - NO API key, 100+ Estonian stations, nearest auto-found
3. **Lennuilm.ee METAR** - 6 airports, METAR parser (wind knots→m/s, dewpoint→humidity via Magnus formula)
4. **OpenWeatherMap** - needs API key (optional supplement)

Auto-fetch: one button → GPS → all 4 sources → fills empty fields only (no overwriting). Status bar shows which sources succeeded.

## Print / PDF ("Test Raport")
- Compact A4 single-page layout (8pt Arial, tight margins)
- Header: "Electric Wings Group OÜ" + "TEST RAPORT"
- Sections: Droon ja varustus | Ilmastikuolud | Lennu tulemused | Märkused
- Footer: signature lines (Läbiviija, Kuupäev, Allkiri) + company name
- PDF via browser print dialog ("Save as PDF")
- Comparison print also available

## Export/Import
- Single log JSON export (includes related drone + battery data)
- Full data export (all drones, batteries, logs)
- JSON import with duplicate detection
- Text file import (.txt/.log/.csv) with regex parser → pre-fills form

## Key Functions Reference
- `autoFetchLocationAndWeather()` - main one-button weather+GPS
- `fetchOpenMeteo(lat, lon)` - Open-Meteo API
- `fetchIlmateenistus(lat, lon)` - Estonian weather XML
- `applyMetar(metarString, stationCode)` - METAR parser
- `parseMetar(metar)` - returns {temperature, dewpoint, pressure, windSpeed, windDirection, windGust, visibility, cloudCover, precipitation}
- `generatePrintContent(logs)` - builds print-ready HTML
- `migrateLegacyDrones()` - auto-migrates old embedded battery format

## TODO / Potential Improvements
- Dark mode
- Chart/graph visualizations for log comparison
- Drone image upload
- Flight path map integration
- Multi-language support
- Better text file parser patterns
