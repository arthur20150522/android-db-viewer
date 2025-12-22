# Changelog

## [v1.2.5] - 2025-12-18

### ⚡ Improvements
- **Auto-Open**: Automatically opens the default web browser when the application starts.

## [v1.2.4] - 2025-12-18

### 🌟 UI/UX Improvements
- **Visual Change Tracking**: Added a green gradient animation to highlight rows that have changed or been added during real-time monitoring.
- **Tab Notifications**: Added a red notification dot on background tabs when data updates are detected.
- **Server Status Indicator**: Added a "Connected/Disconnected" badge in the header with auto-reconnect capability.
- **Silent Refresh**: Device list now refreshes silently in the background after reconnection, preventing UI flicker.

### 🐛 Bug Fixes
- **Loading State**: Fixed an issue where the device list would get stuck on "Loading..." due to incorrect event handling.
- **Stability**: Added timeout protection (10s) and data validation for table data requests to prevent UI freezes.
- **JS Error**: Fixed a variable redeclaration error (`tabBtn`) in the tab management logic.
- **Caching**: Implemented cache busting for static resources to ensure clients always load the latest version.

## [v1.2.3] - 2025-12-18

### 🐛 Bug Fixes
- **Data Consistency**: Fixed a critical issue where "Monitor" and "Refresh" would show stale data on Windows due to file locking preventing database overwrites.
- **Snapshot Management**: Implemented unique timestamped filenames for every pull to ensure fresh data access.
- **Auto-Cleanup**: Added automatic cleanup of old temporary database files to prevent disk clutter.
- **Monitor Sync**: Fixed synchronization between the backend pull process and frontend data fetching.

## [v1.2.0] - 2025-12-18

### 🚀 New Features
- **Non-Root Support**: Added support for accessing databases on non-rooted devices using `run-as` command (Debuggable apps only).
- **Debuggable Detection**: Automatically detects and marks debuggable applications with a "🐛 Debug" badge.
- **Package Filtering**: Added filters for Third-party (-3), System (-s), and All packages.
- **Debug Only Filter**: Client-side toggle to show only debuggable applications.
- **Stream Transfer**: Implemented Base64 stream transfer for database pulling, bypassing SD card permission issues on modern Android versions.

### ⚡ Improvements
- Optimized package loading performance.
- Enhanced UI with filter controls in the sidebar.

## [v1.1.0] - 2025-12-18

### 🚀 New Features
- **Multi-Tab Interface**: View multiple tables simultaneously in separate tabs.
- **Auto-Refresh Monitor**: Real-time data monitoring with toggleable 3-second auto-refresh interval.
- **SQL History**: Persistent history of executed SQL queries with collapsible results.
- **SQL Autocomplete**: Intelligent code completion for SQL keywords, table names, and column names.

### ⚡ Improvements
- Improved SQL Editor sizing and rendering.
- Added pagination state per tab.

## [v1.0.0] - 2025-12-18

- Initial Release
- Device detection (Root status check)
- Package listing
- Database discovery and pulling
- Table data browsing with pagination
- Basic SQL Editor
