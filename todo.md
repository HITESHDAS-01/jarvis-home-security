# JARVIS Home - Development Todo

## Phase 1: Core Foundation (Current)
- [x] Project structure created
- [x] Camera manager with RTSP, HTTP, MJPEG, ONVIF, WiFi, LAN, USB modes
- [x] YOLOv8 detection pipeline
- [x] SQLite event storage
- [x] Video recording (hybrid mode)
- [x] Zone manager
- [x] LLM integration (Gemini, OpenAI, Ollama)
- [x] Telegram bot basic setup
- [x] Config files (cameras, zones, settings)
- [x] Dependencies installed
- [x] YOLOv8n model downloaded

---

## Phase 2: Camera & Detection Improvements

### Camera Reliability
- [ ] Auto-reconnect on camera disconnect
- [ ] Camera health monitoring (ping/stream check)
- [ ] Camera offline alerts
- [ ] Frame rate monitoring per camera
- [ ] Camera connection retry with exponential backoff
- [ ] Handle corrupted frames gracefully
- [ ] Support camera PTZ (Pan-Tilt-Zoom) control
- [ ] Camera stream quality switching (auto/low/medium/high)

### Detection Improvements
- [ ] Track objects across frames (person ID persistence)
- [ ] Motion detection (background subtraction) as lightweight alternative
- [ ] Configurable detection intervals per camera
- [ ] Detection confidence thresholds per object type
- [ ] Custom object classes (pets, packages, vehicles)
- [ ] Face detection (not recognition - just "person with face")
- [ ] License plate detection placeholder
- [ ] Line crossing detection
- [ ] Region entry/exit counting

### Zone Improvements
- [ ] Visual zone editor (web UI or Telegram)
- [ ] Polygon zones with multiple points
- [ ] Time-based zone rules (different rules for day/night)
- [ ] Zone nesting (sub-zones within zones)
- [ ] Zone entry/exit logging
- [ ] Per-zone detection sensitivity

---

## Phase 3: Event System

### Event Processing
- [ ] Event deduplication (don't spam same event)
- [ ] Event clustering (group related events)
- [ ] Event severity auto-classification
- [ ] Event confidence scoring
- [ ] Pre-event buffer recording (10-15 seconds before)
- [ ] Post-event buffer recording (5-10 seconds after)
- [ ] Event timeline visualization
- [ ] Event export (JSON, CSV)

### Event History
- [ ] Event search by time range
- [ ] Event search by camera
- [ ] Event search by type
- [ ] Event search by zone
- [ ] Event search by severity
- [ ] Event search by description (text search)
- [ ] Event statistics dashboard
- [ ] Event aggregation (daily/weekly/monthly)

---

## Phase 4: Telegram Bot

### Basic Commands
- [x] /start - Welcome message
- [x] /help - Help text
- [x] /status - System status
- [x] /mode - Change security mode
- [x] /events - Recent events
- [x] /cameras - Camera status
- [x] /snapshot - Get camera snapshot

### Advanced Commands
- [ ] /clip <camera> - Get last event clip
- [ ] /live <camera> - Get live stream link
- [ ] /history <hours> - Event history
- [ ] /search <query> - Search events
- [ ] /summary - Daily/weekly summary
- [ ] /zones - List zones
- [ ] /rules - List security rules
- [ ] /add_rule <rule> - Add security rule
- [ ] /mute <minutes> - Mute alerts temporarily
- [ ] /test_alert - Test alert delivery

### Natural Language
- [x] Basic question answering
- [ ] Context-aware responses (remember conversation)
- [ ] Multi-turn conversations
- [ ] Handle ambiguous queries
- [ ] Handle commands in Hindi/Hinglish
- [ ] Handle commands with typos
- [ ] Quick reply buttons
- [ ] Inline keyboard for actions

### Alert System
- [x] Person detected alert
- [x] Zone violation alert
- [ ] Night activity alert
- [ ] Camera offline alert
- [ ] Multiple people alert
- [ ] Loitering alert
- [ ] Vehicle detected alert
- [ ] Unusual activity alert
- [ ] Daily summary alert
- [ ] Alert with snapshot image
- [ ] Alert with short video clip
- [ ] Alert with location/zone info
- [ ] Alert severity levels (low/medium/high/critical)
- [ ] Alert acknowledgment
- [ ] Alert escalation (if no response)
- [ ] Alert grouping (batch similar alerts)

---

## Phase 5: LLM Integration

### Chat Improvements
- [x] Basic Q&A
- [ ] Context window management
- [ ] Conversation history (last N messages)
- [ ] Home-specific system prompt
- [ ] Personality tuning (calm, reliable, concise)
- [ ] Handle multiple languages
- [ ] Fallback responses when LLM unavailable
- [ ] Response caching (avoid repeated API calls)
- [ ] Token usage tracking

### Event Summarization
- [x] Basic event summary
- [ ] Time-range summaries
- [ ] Camera-specific summaries
- [ ] Severity-based summaries
- [ ] Natural language summaries ("Someone was at your door for 2 minutes")
- [ ] Pattern detection ("Your backyard has had 3 intrusions this week")

### Smart Features
- [ ] Anomaly detection ("This is unusual for this time")
- [ ] Trend analysis ("Activity has increased 20% this week")
- [ ] Predictive alerts ("Based on patterns, watch for...")
- [ ] Recommendation engine ("Consider adding a camera here")

---

## Phase 6: Recording & Storage

### Recording
- [x] Continuous recording
- [x] Event-based recording
- [x] Hybrid mode
- [ ] Recording quality auto-adjustment (based on disk space)
- [ ] Recording compression (H.264/H.265)
- [ ] Recording segmentation (split long recordings)
- [ ] Recording index (fast seek)
- [ ] Recording backup to external drive
- [ ] Recording upload to cloud (optional, for important events only)

### Storage Management
- [ ] Disk space monitoring
- [ ] Auto-cleanup of old recordings
- [ ] Configurable retention per camera
- [ ] Storage usage statistics
- [ ] Storage alerts (low disk space)
- [ ] Event clip compression
- [ ] Snapshot compression

### Database
- [x] Basic event storage
- [ ] Database migrations
- [ ] Database backup/restore
- [ ] Database optimization (VACUUM)
- [ ] Database WAL mode for performance
- [ ] Database encryption (optional)

---

## Phase 7: Security Modes

### Mode Implementation
- [x] Home mode
- [x] Away mode
- [x] Sleep mode
- [ ] Custom modes (user-defined)
- [ ] Mode-specific detection sensitivity
- [ ] Mode-specific alert rules
- [ ] Mode auto-switch (time-based)
- [ ] Mode auto-switch (location-based, future)
- [ ] Mode history/log

### Security Rules
- [x] Basic rule engine
- [ ] Rule conditions (time, zone, object type)
- [ ] Rule actions (alert, record, notify)
- [ ] Rule priority
- [ ] Rule conflicts resolution
- [ ] Rule templates (preset security rules)
- [ ] Rule testing ("what would happen if...")

---

## Phase 8: Web Interface (Optional but Recommended)

### Live Dashboard
- [ ] Camera grid view (all cameras live)
- [ ] Single camera full-screen view
- [ ] Event timeline
- [ ] Alert feed
- [ ] System status panel
- [ ] Storage usage panel

### Controls
- [ ] Camera snapshot button
- [ ] Camera recording controls
- [ ] Security mode switcher
- [ ] Zone editor (visual)
- [ ] Settings panel
- [ ] User management (multi-user)

### Historical View
- [ ] Event browser
- [ ] Recording playback
- [ ] Event search
- [ ] Export events

---

## Phase 9: Performance & Reliability

### Performance
- [ ] Multi-threaded frame processing
- [ ] GPU acceleration for YOLO (if available)
- [ ] Frame buffering (ring buffer)
- [ ] Memory management (prevent leaks)
- [ ] CPU usage optimization
- [ ] Network bandwidth optimization
- [ ] Database query optimization

### Reliability
- [ ] Graceful shutdown
- [ ] Crash recovery
- [ ] Watchdog (auto-restart on crash)
- [ ] Health check endpoint
- [ ] Logging system (file + console)
- [ ] Log rotation
- [ ] Error reporting
- [ ] Crash reporting (optional)

### Testing
- [ ] Unit tests for core modules
- [ ] Integration tests
- [ ] Camera connection tests
- [ ] Detection accuracy tests
- [ ] Telegram bot tests
- [ ] Load testing (multiple cameras)
- [ ] Stress testing (long running)

---

## Phase 10: Deployment & Setup

### Installation
- [ ] Setup script (automated installation)
- [ ] Requirements.txt (pinned versions)
- [ ] Docker support (Dockerfile + docker-compose)
- [ ] Windows service (auto-start)
- [ ] Linux systemd service
- [ ] Configuration wizard (first run)
- [ ] Camera auto-discovery wizard

### Configuration
- [ ] Environment variables support (.env)
- [ ] Configuration validation
- [ ] Configuration backup/restore
- [ ] Remote configuration (via Telegram)
- [ ] Configuration encryption (for secrets)

### Documentation
- [ ] README.md with setup instructions
- [ ] Configuration guide
- [ ] Camera setup guide (per brand)
- [ ] Troubleshooting guide
- [ ] API documentation
- [ ] Contributing guidelines
- [ ] License file

---

## Phase 11: Production Hardening

### Security
- [ ] Telegram bot token encryption
- [ ] Camera password encryption
- [ ] API key rotation
- [ ] Rate limiting (Telegram API)
- [ ] Input validation (all user inputs)
- [ ] SQL injection prevention
- [ ] File path traversal prevention
- [ ] Secure file permissions

### Monitoring
- [ ] System health metrics
- [ ] Performance metrics
- [ ] Alert delivery confirmation
- [ ] Uptime tracking
- [ ] Error rate tracking
- [ ] Disk usage alerts
- [ ] Memory usage alerts
- [ ] CPU usage alerts

### Backup & Recovery
- [ ] Automated database backup
- [ ] Automated config backup
- [ ] Backup rotation (keep last N)
- [ ] Restore from backup
- [ ] Disaster recovery guide

---

## Phase 12: Polish & UX

### User Experience
- [ ] First-run setup wizard
- [ ] Camera setup wizard
- [ ] Zone setup wizard
- [ ] Security rule presets
- [ ] Helpful error messages
- [ ] Progress indicators
- [ ] Status notifications
- [ ] Quick start guide

### Telegram UX
- [ ] Welcome message with buttons
- [ ] Quick reply keyboards
- [ ] Inline action buttons
- [ ] Image/video previews
- [ ] Message formatting (bold, italic, code)
- [ ] Message splitting (for long responses)
- [ ] Typing indicators
- [ ] Read receipts

### Notifications
- [ ] Notification sounds (optional)
- [ ] Notification grouping
- [ ] Notification priority
- [ ] Notification scheduling
- [ ] Notification preferences per user
- [ ] Do Not Disturb mode
- [ ] Notification history

---

## Phase 13: Future Features (Post-MVP)

### Advanced Detection
- [ ] Face recognition (known/unknown persons)
- [ ] Pet detection
- [ ] Package detection
- [ ] Vehicle make/model detection
- [ ] License plate recognition
- [ ] Gesture detection
- [ ] Fall detection
- [ ] Crowd detection

### Smart Home Integration
- [ ] Smart light control
- [ ] Smart lock integration
- [ ] Smart alarm integration
- [ ] Voice assistant integration (Alexa, Google)
- [ ] Home Assistant integration
- [ ] IFTTT integration

### Advanced Features
- [ ] Multi-home support
- [ ] Multi-user support
- [ ] Role-based access control
- [ ] Audit logging
- [ ] Compliance features (GDPR)
- [ ] Mobile app (React Native)
- [ ] Cloud sync (optional)
- [ ] Remote access (without cloud)

---

## Priority Order (Suggested)

### Critical (Do First)
1. Auto-reconnect on camera disconnect
2. Camera offline alerts
3. Event deduplication
4. Alert with snapshot image
5. Alert with video clip
6. Graceful shutdown
7. Logging system

### High Priority
1. Camera health monitoring
2. Event search functionality
3. Natural language improvements
4. Disk space monitoring
5. Auto-cleanup of old recordings
6. Configuration validation
7. Error handling improvements

### Medium Priority
1. Web dashboard
2. Advanced zone editor
3. Security rule engine
4. Performance optimization
5. Docker support
6. Documentation
7. Unit tests

### Low Priority
1. Mobile app
2. Cloud sync
3. Face recognition
4. Smart home integration
5. Multi-home support
6. Advanced analytics

---

## Detailed Implementation Plan: Next Major Features

Use this section when picking the next coding task. Each feature includes the practical steps, likely files to update, and checks to run after implementation.

---

### 1. Camera Reliability

#### Auto-reconnect on camera disconnect
- [ ] Add per-camera connection state: `online`, `offline`, `reconnecting`, `last_seen`, `last_error`
- [ ] Detect failed reads in `core/camera_manager.py` when `cap.read()` returns false or frame is empty
- [ ] Add retry loop with exponential backoff: 1s, 2s, 5s, 10s, 30s max
- [ ] Rebuild the stream URL before reconnecting so config changes can be picked up
- [ ] Keep serving the last good snapshot while reconnecting
- [ ] Add tests for reconnect state transitions in `tests/test_camera_manager.py`

#### Camera health monitoring
- [ ] Add a health check method in `core/camera_manager.py` that checks stream readability and last frame age
- [ ] Store per-camera health metrics: uptime, failures, reconnect count, fps, last frame timestamp
- [ ] Expose health data through `web/app.py` API, for example `/api/cameras/health`
- [ ] Show health status in the web dashboard camera cards
- [ ] Add Telegram `/cameras` output fields for online/offline and last seen

#### Camera offline alerts
- [ ] Add offline event type in `core/event_engine.py`
- [ ] Trigger alert only after a grace period, for example 30-60 seconds offline
- [ ] Avoid repeated offline spam by deduplicating offline alerts per camera
- [ ] Send recovery alert when the camera comes back online
- [ ] Add tests for offline alert cooldown and recovery alert

#### Frame-rate monitoring
- [ ] Track frames received per rolling window, for example last 10 seconds
- [ ] Add `fps` field to camera status response
- [ ] Add warning threshold in `config/settings.yaml`, for example `camera.min_fps_warning`
- [ ] Show low-FPS warning in dashboard and Telegram status

#### Corrupted frame handling
- [ ] Validate frames before detection: frame is not `None`, has shape, has non-zero size
- [ ] Count corrupted frames per camera
- [ ] Skip corrupted frames without crashing detector/recorder loops
- [ ] Mark camera degraded if corrupted frame rate stays high
- [ ] Add a regression test with invalid frame inputs

---

### 2. Alert Polish

#### Snapshot with alerts
- [ ] Save event snapshot in `data/snapshots/` when detection triggers an event
- [ ] Store snapshot path in SQLite event record
- [ ] Update `bot/telegram_bot.py` to send image with alert text
- [ ] Add fallback text alert if snapshot write/send fails
- [ ] Show snapshot thumbnail in web event feed

#### Video clip with alerts
- [ ] Add pre-event and post-event recording buffer in `core/recorder.py`
- [ ] Save short event clips in `data/recordings/events/`
- [ ] Store clip path in event record
- [ ] Add Telegram `/clip <camera>` command to send latest clip
- [ ] Add web playback link in event timeline

#### Alert deduplication and grouping
- [ ] Create a dedupe key: camera + zone + object type + severity
- [ ] Add cooldown config, for example `alerts.dedupe_seconds`
- [ ] Suppress repeated alerts inside cooldown window
- [ ] Group similar events and update count, for example "person detected 5 times in 2 minutes"
- [ ] Add tests in `tests/test_telegram_bot.py` or new `tests/test_event_engine.py`

#### Mute and acknowledge
- [ ] Add muted-until timestamp to runtime state or SQLite
- [ ] Add `/mute <minutes>` Telegram command
- [ ] Add alert acknowledge action through Telegram inline button
- [ ] Add acknowledged status to events table
- [ ] Hide or visually mark acknowledged alerts in web dashboard

#### Severity levels
- [ ] Define severity enum: `low`, `medium`, `high`, `critical`
- [ ] Add rules for severity mapping: mode, time, zone, object type
- [ ] Store severity in events table
- [ ] Color-code severity in web dashboard
- [ ] Include severity in Telegram alert title

---

### 3. Telegram Advanced Commands

#### Clip, live, history, search, summary, zones, mute
- [ ] Implement `/clip <camera>` to send latest event clip
- [ ] Implement `/live <camera>` to return web dashboard stream link or snapshot refresh link
- [ ] Implement `/history <hours>` to list events in a time range
- [ ] Implement `/search <query>` to search event type, camera, zone, and description
- [ ] Implement `/summary` to generate daily/weekly event summary
- [ ] Implement `/zones` to list configured zones per camera
- [ ] Implement `/mute <minutes>` to suppress alerts temporarily

#### Hinglish and typo handling
- [ ] Add alias map for common phrases: "status batao", "camera dikhao", "last clip bhejo"
- [ ] Add fuzzy matching for simple command typos
- [ ] Route natural language requests to command handlers before calling the LLM
- [ ] Add tests for Hinglish phrases and typos

#### Buttons and better UX
- [ ] Add Telegram inline buttons for mode change, latest snapshot, latest clip, acknowledge
- [ ] Add quick reply keyboard for common actions
- [ ] Split long event/history responses into multiple messages
- [ ] Add typing indicator while generating summaries

---

### 4. Web Dashboard Completion

#### Live camera grid
- [ ] Add streaming/snapshot refresh endpoint in `web/app.py`
- [ ] Build all-camera grid in `web/templates/index.html`
- [ ] Add online/offline/FPS badges per camera
- [ ] Add snapshot refresh and open full-screen controls
- [ ] Handle missing camera stream with a clear empty state

#### Single camera full-screen view
- [ ] Add route or front-end state for selected camera
- [ ] Show large live feed/snapshot
- [ ] Add controls: snapshot, record, latest clip, health details
- [ ] Add keyboard escape/back behavior

#### Event timeline and alert feed
- [ ] Add API endpoint to fetch paginated events
- [ ] Add filters for camera, event type, zone, severity, and time range
- [ ] Display snapshot thumbnails and clip links
- [ ] Add acknowledge/mute controls
- [ ] Add empty/loading/error states

#### Storage and status panels
- [ ] Expose disk usage, DB size, recording count, oldest/newest recording
- [ ] Show bot status, LLM status, camera status, and model/detector status
- [ ] Highlight warnings for low disk, offline camera, bot disconnected, LLM failure

#### Zone editor
- [ ] Add visual editor over a camera snapshot
- [ ] Support polygon draw/edit/delete
- [ ] Save zones to `config/zones.yaml`
- [ ] Validate zone points before saving
- [ ] Add preview mode to test if detections fall inside zones

---

### 5. Storage and Cleanup

#### Disk monitoring
- [ ] Use `core/disk_monitor.py` to calculate free/used space for recording path
- [ ] Add thresholds in `config/settings.yaml`: warning percent, critical percent
- [ ] Add dashboard status and Telegram `/status` output
- [ ] Trigger low disk alerts with dedupe cooldown

#### Auto-cleanup and retention
- [ ] Add retention config per camera and global default
- [ ] Delete oldest recordings when disk is below threshold
- [ ] Protect important/critical event clips from automatic cleanup
- [ ] Log every cleanup action
- [ ] Add dry-run mode for cleanup testing

#### Database maintenance
- [ ] Add SQLite migrations system with schema version table
- [ ] Enable WAL mode for better concurrent reads/writes
- [ ] Add periodic `VACUUM` or scheduled maintenance command
- [ ] Add DB backup and restore commands
- [ ] Add tests for migration from old schema to new schema

---

### 6. Production Hardening

#### Secrets and config safety
- [ ] Move bot token, LLM keys, and camera passwords to `.env` or encrypted local store
- [ ] Keep sample config files without real secrets
- [ ] Add config validation for required fields and unsafe defaults
- [ ] Prevent secrets from being returned by web APIs
- [ ] Update `.gitignore` for generated secret files

#### Input validation and security
- [ ] Validate all Telegram command arguments
- [ ] Validate web API payloads before writing config files
- [ ] Prevent path traversal when serving snapshots/clips
- [ ] Add rate limiting storage backend instead of Flask-Limiter memory storage
- [ ] Add authentication checks to every sensitive route

#### Logging and reliability
- [ ] Add rotating file logs for app, security events, and errors
- [ ] Add graceful shutdown for camera, recorder, Telegram bot, and web server
- [ ] Add watchdog process or service restart strategy
- [ ] Add health endpoint for uptime checks
- [ ] Add crash recovery notes to README

---

### 7. Docs and Config Cleanup

#### Sync README and todo status
- [ ] Compare README feature list with completed checkboxes in this file
- [ ] Mark implemented features as done only after tests or manual verification
- [ ] Move future features out of README feature list into roadmap section
- [ ] Add current MVP status section to README

#### Improve setup docs
- [ ] Add camera setup guide with RTSP, HTTP, MJPEG, USB, and IP Webcam examples
- [ ] Add Telegram bot setup steps with BotFather and chat ID instructions
- [ ] Add troubleshooting guide for camera stream, Telegram, LLM, and YOLO issues
- [ ] Add Windows service and Docker verification steps
- [ ] Add sample config files for safe defaults

#### Config cleanup
- [ ] Keep `config/settings.yaml`, `config/cameras.yaml`, and `config/zones.yaml` schemas documented
- [ ] Add config backup before dashboard/setup wizard writes changes
- [ ] Add config validation on startup
- [ ] Add tests for invalid config handling

---

### 8. Health Monitor

#### System health model
- [ ] Create a central health service, for example `core/health_monitor.py`
- [ ] Track camera online/offline, disk usage, Telegram bot status, LLM status, detector status, and recorder status
- [ ] Assign component status: `ok`, `warning`, `critical`, `unknown`
- [ ] Store latest health snapshot in memory and optionally SQLite

#### Health alerts
- [ ] Alert when camera goes offline
- [ ] Alert when disk usage crosses warning/critical thresholds
- [ ] Alert when Telegram bot fails to send messages
- [ ] Alert when LLM API fails repeatedly
- [ ] Alert when detector/model loading fails
- [ ] Deduplicate health alerts and send recovery alerts

#### Health dashboard and commands
- [ ] Add `/health` Telegram command
- [ ] Add health summary to `/status`
- [ ] Add `/api/health` endpoint in `web/app.py`
- [ ] Add web dashboard health panel
- [ ] Add tests for degraded and recovered states

---

## Phase 8: Multi-Agent System (Future)

### Architecture
```
User message → Orchestrator Agent → routes to specialized agent
                                    ├→ Camera Agent (add/remove/status/snapshot)
                                    ├→ Security Agent (modes/zones/alerts)
                                    ├→ System Agent (disk/restart/logs/settings)
                                    ├→ Recording Agent (recordings/path/cleanup)
                                    ├→ Chat Agent (general questions/LLM)
                                    └→ Home Agent (IoT/smart devices)
```

### Implementation Steps
1. **Orchestrator Agent**
   - Intent classification (fast, no LLM needed)
   - Context-aware routing
   - Parallel execution support

2. **Camera Agent**
   - Camera CRUD operations
   - Snapshot/stream management
   - Health monitoring
   - Auto-reconnect logic

3. **Security Agent**
   - Mode management
   - Zone CRUD
   - Alert rules
   - Event classification

4. **System Agent**
   - Disk management
   - Config management
   - Log viewing
   - Restart control

5. **Recording Agent**
   - Recording path management
   - Storage cleanup
   - Clip retrieval
   - Archive management

6. **Chat Agent**
   - Natural language understanding
   - Context memory
   - Multi-turn conversations
   - Command suggestions

### Benefits
- Better separation of concerns
- Parallel task execution
- Easier to test individual agents
- Scalable architecture
- Can add new agents without affecting others

### Complexity
- Inter-agent communication
- State management
- Error handling across agents
- Testing coordination

### Estimated Time: 1-2 weeks

---

## Notes

- Each checkbox represents a task that should be implemented
- Tasks can be broken down further during implementation
- Some tasks may depend on others (check dependencies)
- Estimated time per task: 1-8 hours depending on complexity
- Total estimated tasks: 200+
- Recommended team size: 1-2 developers
- Estimated time to MVP: 2-4 weeks (full-time)
- Estimated time to production: 2-3 months (full-time)
