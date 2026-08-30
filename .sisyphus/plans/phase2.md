# JARVIS Home - Phase 2 Plan

## Current State
- Core modules working (camera, detection, storage, recording, events, zones, LLM, Telegram)
- All dependencies installed
- Basic functionality verified

## Phase 2: Critical Reliability (Next Steps)

### Priority 1: Auto-Reconnect System
**File:** `core/camera_manager.py`
- Add background watchdog thread
- Monitor each camera connection every 10 seconds
- Auto-reconnect on disconnect with exponential backoff
- Track reconnect attempts (max 5 before giving up)
- Reset attempt counter on successful connection

### Priority 2: Camera Health Alerts
**File:** `bot/telegram_bot.py`
- Send Telegram alert when camera goes offline
- Send Telegram alert when camera comes back online
- Include camera name, last seen time, connection mode

### Priority 3: Event Deduplication
**File:** `core/event_engine.py`
- Track recent events per camera
- Don't fire same event type within 60 seconds
- Allow zone violations to bypass dedup (important)
- Store last event time per camera+type combo

### Priority 4: Graceful Shutdown
**File:** `main.py`
- Handle SIGINT (Ctrl+C) gracefully
- Stop all threads cleanly
- Release all camera streams
- Close database connections
- Save any pending data

### Priority 5: Logging System
**New File:** `core/logger.py`
- Log to both console and file
- Log rotation (daily, keep 7 days)
- Log levels (DEBUG, INFO, WARNING, ERROR)
- Structured format: [TIMESTAMP] [LEVEL] [MODULE] message

### Priority 6: Enhanced Telegram Commands
**File:** `bot/telegram_bot.py`
- `/clip <camera>` - Get last event clip
- `/history <hours>` - Event history
- `/summary` - Daily summary
- Better error messages
- Typing indicator while processing

### Priority 7: Configuration Validation
**New File:** `core/config_validator.py`
- Validate camera configs on startup
- Check required fields (name, connection_mode, ip/rtsp_url)
- Validate RTSP URL format
- Validate zone coordinates
- Warn about missing optional fields

### Priority 8: Error Handling
**Files:** All core modules
- Wrap all external calls in try/except
- Log errors with full context
- Don't crash on individual camera failures
- Continue processing other cameras
- Graceful degradation

---

## Files to Modify
1. `core/camera_manager.py` - Add watchdog, auto-reconnect
2. `core/event_engine.py` - Add deduplication
3. `bot/telegram_bot.py` - Add new commands, alerts
4. `main.py` - Add graceful shutdown, logging
5. `core/logger.py` - New file
6. `core/config_validator.py` - New file

## Testing Plan
- Test camera disconnect/reconnect
- Test event deduplication
- Test graceful shutdown
- Test logging output
- Test Telegram alerts

## Estimated Time
- 2-3 hours for implementation
- 1 hour for testing
