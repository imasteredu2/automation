# automation

AI-powered desktop automation with multi-monitor viewport, overlay HUD, live viewport window, chat log, screenshot manager, autonomous execution loop, task scheduler, and Hugging Face mini vision-language bot.

---

## Features

| Feature | Details |
|---|---|
| **Bot input control** | Simulate mouse moves, clicks, drags, scroll and keyboard via `InputController` (pyautogui) |
| **Multi-monitor viewport** | Capture any or all connected monitors; build side-by-side mini-map thumbnails (mss + Pillow) |
| **Overlay HUD** | Always-on-top transparent window: input state, AI state, live minimap, and task-input field |
| **Viewport window** | Dedicated resizable window showing live per-monitor thumbnails (1 s refresh) |
| **Chat log window** | Scrollable conversation history: user tasks (blue), bot responses (green), system messages (grey) |
| **Screenshot manager** | Save timestamped screenshots with optional bounding-box overlays; rolling archive |
| **Autonomous loop** | Goal-seeking loop: capture → AI goal-check → execute step → repeat until done |
| **Task scheduler** | Schedule one-shot, recurring, and daily tasks (stdlib only, no extra deps) |
| **Global hotkeys** | `Ctrl+L` toggle overlay · `Ctrl+Alt+Home` enable · `Ctrl+Alt+End` disable input |
| **AI bot** | `microsoft/Florence-2-base` (~230 M params): describe screens, OCR, detect UI elements, plan tasks |
| **Action executor** | Parse structured AI steps (`CLICK x y`, `TYPE text`, `PRESS key`, …) → real events |
| **Task runner** | Background thread: capture → AI plan → execute steps → task history (last 50) |
| **Persistent config** | `~/.automation/config.json` remembers your settings across sessions |

---

## Requirements

- Python 3.10+
- Linux / Windows / macOS (display required at runtime; tests run headless)

```bash
pip install -r requirements.txt
# Also: sudo apt install python3-tk   (Debian/Ubuntu)
```

---

## Quick start

```bash
# Start the full system (overlay + viewport + chat + hotkeys + AI bot)
python main.py

# No AI model (overlay, viewport, chat, scheduler still work)
python main.py --no-ai

# Live viewport window only
python main.py --viewport-only

# One-shot task
python main.py --task "Close all open browser tabs"

# Autonomous goal-seeking loop
python main.py --goal "Open Firefox and navigate to https://example.com"

# List detected monitors and exit
python main.py --list-monitors

# Use a custom config file
python main.py --config /path/to/config.json
```

---

## Hotkeys

| Keys | Action |
|---|---|
| `Ctrl+L` | Toggle overlay HUD visibility |
| `Ctrl+Alt+Home` | **Enable** bot keyboard & mouse control |
| `Ctrl+Alt+End` | **Disable** bot keyboard & mouse control |

---

## Project layout

```
automation/
├── main.py                         Entry point
├── requirements.txt
└── src/
    ├── config.py                   Persistent JSON settings (~/.automation/config.json)
    ├── input_controller.py         Bot-driven mouse & keyboard (pyautogui)
    ├── viewport.py                 Multi-monitor screen capture (mss + Pillow)
    ├── viewport_window.py          Resizable live viewport window (tkinter)
    ├── overlay.py                  Transparent status HUD + task input (tkinter)
    ├── chat_window.py              Scrollable bot interaction log (tkinter)
    ├── screenshot_manager.py       Save / annotate / archive screenshots
    ├── autonomous_loop.py          Continuous goal-seeking execution loop
    ├── scheduler.py                One-shot, recurring, and daily task scheduler
    ├── hotkey_manager.py           Global hotkey listener (pynput)
    ├── ai_bot.py                   HuggingFace vision-language bot (Florence-2)
    ├── action_executor.py          Parse & execute structured AI action steps
    └── task_runner.py              Orchestration: viewport → AI → executor + history
```

---

## Configuration

Saved at `~/.automation/config.json`; created with defaults on first run.

| Key | Default | Description |
|---|---|---|
| `monitor_index` | `1` | Primary monitor for AI captures |
| `model_id` | `microsoft/Florence-2-base` | Hugging Face model |
| `overlay_alpha` | `0.82` | Overlay transparency |
| `thumbnail_width` | `320` | Minimap thumbnail width (px) |
| `minimap_interval_ms` | `3000` | Overlay minimap refresh interval |
| `viewport_refresh_ms` | `1000` | Viewport window refresh interval |
| `input_enabled_on_start` | `true` | Start with input control active |
| `log_level` | `INFO` | Logging verbosity |
| `screenshot_dir` | `~/.automation/screenshots` | Screenshot save directory |
| `screenshot_max_count` | `200` | Max screenshots before oldest pruned |
| `autonomous_max_iterations` | `20` | Autonomous loop iteration cap |
| `autonomous_step_delay` | `1.0` | Seconds between autonomous steps |

---

## Running tests

```bash
python -m pytest tests/ -v
```

**191 tests, all headless** (no display / GPU needed).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            main.py                                  │
│                                                                      │
│  HotkeyManager ──► InputController  (activate / deactivate)         │
│                    ActionExecutor   (execute structured steps)       │
│                    ScreenshotManager (save/annotate/archive)         │
│                                                                      │
│  Overlay HUD      status + minimap + task-input field               │
│  ViewportWindow   live per-monitor thumbnails (1 s)                 │
│  ChatWindow       scrollable bot interaction log                    │
│                                                                      │
│  TaskRunner ──────► Viewport.get_frame() [always active]            │
│               │    AIBot.plan_task()                                 │
│               │    AIBot.generate_executable_steps()                 │
│               │    ActionExecutor.execute_plan()                     │
│               └──► task_history (last 50) + overlay/chat updates    │
│                                                                      │
│  AutonomousLoop ──► Viewport → AIBot.query(goal check?)             │
│                 └── TaskRunner.submit(step) until goal or max iter  │
│                                                                      │
│  Scheduler ──────── once() / every() / daily() → TaskRunner.submit  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Action step syntax

`AIBot.generate_executable_steps()` returns step strings that
`ActionExecutor.execute_plan()` executes directly:

```
CLICK <x> <y>                  left click at screen position
CLICK <x> <y> right            right-click
DOUBLE_CLICK <x> <y>           double-click
RIGHT_CLICK <x> <y>            right-click (alias)
DRAG <x1> <y1> <x2> <y2>      click-and-drag
SCROLL <n>                     scroll n clicks (positive=up)
TYPE <text>                    type text
PRESS <key>                    press a key (enter, escape, tab …)
HOTKEY <key1> <key2> ...       key combination (ctrl c, alt f4 …)
WAIT <seconds>                 pause
SCREENSHOT                     capture and store a screenshot
# comment                      ignored
```

---

## AI model

[`microsoft/Florence-2-base`](https://huggingface.co/microsoft/Florence-2-base) — ~230 M params:

- Screen description, OCR, UI element detection, open-vocabulary detection
- Task planning + structured executable step generation
- Goal-check queries for the autonomous loop

Weights are downloaded automatically on first run and cached locally.


