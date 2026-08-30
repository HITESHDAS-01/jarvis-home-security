# JARVIS Home

## What I Want to Build

I want to build **JARVIS Home**, an AI-powered security assistant for a home.

The main idea is simple:

**JARVIS watches the home's CCTV cameras, understands important activity, records everything locally, and communicates with the homeowner through Telegram.**

This is **not a general smart-home automation system in the MVP**. The first version should focus specifically on **home security and CCTV intelligence**.

## Core Concept

A PC at the home acts as the central JARVIS system.

All CCTV footage is **recorded and stored locally on the home PC**. The system should not continuously upload the home's full CCTV footage to the cloud.

JARVIS should identify important events from the cameras and send the homeowner useful alerts through Telegram.

The homeowner should be able to interact with JARVIS remotely through Telegram and ask questions about what is happening or what happened at home.

## What JARVIS Should Do

JARVIS should be able to:

* Monitor multiple home CCTV cameras.
* Show live camera feeds.
* Keep recording CCTV footage locally.
* Detect people and other relevant activity.
* Understand important security events.
* Detect activity in specific areas such as the front gate, backyard, driveway, or entrance.
* Detect unusual or suspicious activity.
* Maintain a timeline of important events.
* Capture snapshots and short clips for important events.
* Send security alerts to the homeowner through Telegram.
* Let the homeowner ask JARVIS questions about the home.
* Search past events and find relevant CCTV footage.
* Send the relevant picture or clip through Telegram.
* Provide daily or periodic security summaries.
* Notify the homeowner when something important happens.

## Example Experience

If someone enters the front gate at 2:13 AM, JARVIS should recognize the event and send a Telegram message such as:

**JARVIS Security Alert**

Person detected at the front gate.

Time: 2:13 AM

JARVIS should attach a relevant picture and a short clip.

The homeowner can then ask:

> "What happened?"

JARVIS should explain what it detected.

The homeowner can also ask:

> "What happened at my house in the last two hours?"

JARVIS should summarize the relevant events.

The homeowner should also be able to say:

> "Show me what happened at the backyard last night."

JARVIS should find the relevant event and send the appropriate footage.

## Telegram Interaction

Telegram is the primary interface for the homeowner in the MVP.

The user should be able to naturally communicate with JARVIS instead of relying only on predefined commands.

Examples:

> "JARVIS, is everything okay at home?"

> "Any unusual activity?"

> "What happened at the front gate?"

> "Show me the backyard."

> "Did anyone enter the house while I was away?"

> "What happened between 10 PM and midnight?"

> "Send me the latest activity from the front camera."

JARVIS should respond naturally and use the available home information to answer.

## Security Alerts

Alerts should be useful rather than generating unnecessary notifications.

Examples:

* Person detected at night.
* Person enters a restricted area.
* Someone remains in an area for an unusual amount of time.
* Multiple people detected.
* Suspicious activity detected.
* Camera goes offline.
* Other important security events.

Each important alert should contain enough context to understand the situation quickly:

* What happened.
* Which camera detected it.
* Time.
* Relevant picture.
* Relevant short clip.
* Severity or importance.

## CCTV Events

Every important event should become a searchable event.

For example:

**02:13 AM — Front Gate**

Person detected.

Stayed for approximately 47 seconds.

**11:42 PM — Backyard**

Person entered restricted area.

This event history should allow JARVIS to answer questions about the past.

## Camera Areas and Zones

The homeowner should be able to define meaningful areas for each camera.

Examples:

* Front Gate
* Main Door
* Backyard
* Driveway
* Balcony
* Living Room
* Parking Area

The homeowner should be able to tell JARVIS what these areas mean and use them in security rules.

For example:

> "If someone enters the backyard after 11 PM, alert me."

## Security Modes

The system should support simple home security modes such as:

**Home**

Normal monitoring.

**Away**

More aggressive security monitoring and alerts.

**Sleep**

Focus on important nighttime activity.

The user should be able to change the mode through Telegram.

For example:

> "JARVIS, I'm leaving."

JARVIS should switch to the appropriate security state.

## Footage and Privacy

The home's CCTV footage should remain **local by default**.

Cloud services should not become the permanent storage location for the home's full CCTV recordings.

Only information necessary for AI analysis, event processing, alerts, or remote viewing should leave the home.

Important security footage should remain available locally for later searching.

The user should be able to ask JARVIS for old footage without manually searching through hours of recordings.

## JARVIS Personality

JARVIS should behave like a **calm, reliable home security assistant**.

It should:

* Give concise answers.
* Clearly describe what it detected.
* Avoid unnecessary alerts.
* Distinguish between normal activity and potentially important activity.
* Be proactive when something genuinely important happens.
* Remember the home's camera names, locations, zones, and security preferences.

It should feel like an assistant that is **watching over the home**, not simply a CCTV viewer.

## MVP Scope

The first version should focus on these capabilities:

1. Home CCTV monitoring.
2. Local CCTV recording.
3. Important activity detection.
4. Security event history.
5. Camera zones.
6. Snapshots and short event clips.
7. Telegram security alerts.
8. Natural-language interaction with JARVIS through Telegram.
9. Searching past CCTV events.
10. Sending relevant footage through Telegram.
11. Basic home security modes.
12. Basic system/camera health alerts.

## Not Part of the MVP

Do not build these initially:

* Smart lights.
* Fans.
* Appliances.
* Sensors.
* Home electrical automation.
* Complex IoT hardware.
* Full smart-home control.
* Dedicated mobile application.
* Advanced face recognition.
* Large-scale predictive automation.

Those can be considered later.

## End Goal

The long-term vision is for JARVIS to become an intelligent home agent that understands what is happening inside and around the house.

But the MVP should stay focused:

**The homeowner should be able to leave the house, forget about the CCTV, and trust JARVIS to watch it, understand important events, and tell them what matters.**

The key product idea is:

**"Your CCTV stays at home. JARVIS watches it and tells you what matters."**
