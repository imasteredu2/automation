# automation

AI-powered desktop automation with multi-monitor viewport, overlay HUD, live viewport window, action execution, and Hugging Face mini vision-language bot.

---

## Features

| Feature | Details |
|---|---|
| **Bot input control** | Simulate mouse moves, clicks, drags, scroll and keyboard via `InputController` (pyautogui) |
| **Multi-monitor viewport** | Capture any or all connected monitors; build side-by-side mini-map thumbnails (mss + Pillow) |
| **Overlay HUD** | Always-on-top transparent status window showing input control state, AI bot state, live minimap, and a task input field |
| **Viewport window** | Dedicated resizable window showing live per-monitor thumbnails refreshing every second |
| **Global hotkeys** | `Ctrl+L` – toggle overlay · `Ctrl+Alt+Home` – enable input · `Ctrl+Alt+End` – disable input |
| **AI bot** | `microsoft/Florence-2-base` (~230 M params) – describes screens, reads text (OCR), detects UI elements, and plans tasks |
| **Action executor** | Parses structured AI step output (`CLICK x y`, `TYPE text`, `PRESS key`, etc.) and drives real input events |
| **Task runner** | Background thread: captures frame → AI plan → structured execution → task history |
| **Persistent config** | `~/.automation/config.json` remembers your settings across sessions |

---

## Requirements

- Python 3.10+
- Linux / Windows / macOS (display required at runtime; tests run headless)

Install dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** `tkinter` is part of the Python standard library but may need a separate system package:
> ```bash
> sudo apt install python3-tk   # Debian/Ubuntu
> ```

---

## Quick start

```bash
# Start the full system (overlay + viewport window + hotkeys + AI bot)
python main.py

# Start without loading the AI model (overlay + viewport window still work)
python main.py --no-ai

# Open only the live viewport window
python main.py --viewport-only

# Submit a one-shot task and print the result
python main.py --task "Close all open browser tabs"

# Use a different monitor as the primary viewport
python main.py --monitor 2

# Use a custom Hugging Face model
python main.py --model "microsoft/Florence-2-large"
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
├── main.py                      Entry point
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py                Persistent JSON settings (~/.automation/config.json)
│   ├── input_controller.py      Bot-driven mouse & keyboard (pyautogui)
│   ├── viewport.py              Multi-monitor screen capture (mss + Pillow)
│   ├── viewport_window.py       Resizable live viewport window (tkinter)
│   ├── overlay.py               Transparent status HUD + task input (tkinter)
│   ├── hotkey_manager.py        Global hotkey listener (pynput)
│   ├── ai_bot.py                HuggingFace vision-language bot (Florence-2)
│   ├── action_executor.py       Parse & execute structured AI action steps
│   └── task_runner.py           Orchestration: viewport → AI → executor + history
└── tests/
    ├── test_config.py
    ├── test_input_controller.py
    ├── test_viewport.py
    ├── test_viewport_window.py
    ├── test_overlay.py
    ├── test_hotkey_manager.py
    ├── test_action_executor.py
    └── test_task_runner.py
```

---

## Configuration

Settings are stored at `~/.automation/config.json` and created with sensible defaults on first run.

| Key | Default | Description |
|---|---|---|
| `monitor_index` | `1` | Primary monitor for AI captures |
| `model_id` | `microsoft/Florence-2-base` | Hugging Face model |
| `overlay_alpha` | `0.82` | Overlay transparency |
| `thumbnail_width` | `320` | Minimap thumbnail width |
| `minimap_interval_ms` | `3000` | Overlay minimap refresh interval |
| `viewport_refresh_ms` | `1000` | Viewport window refresh interval |
| `input_enabled_on_start` | `true` | Start with input control active |
| `log_level` | `INFO` | Logging verbosity |

---

## Running tests

```bash
python -m pytest tests/ -v
```

136 tests, all headless (no display / GPU needed).

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                           main.py                                │
│                                                                  │
│  HotkeyManager ──► InputController (activate / deactivate)       │
│       │            ActionExecutor  (executes structured steps)   │
│       └──────────► Overlay (toggle visibility)                   │
│                     ├── Status labels (input / bot state)        │
│                     ├── Live minimap thumbnail strip             │
│                     └── Task input entry + submit button         │
│                                                                  │
│  ViewportWindow  ──── live per-monitor thumbnails (1 s refresh)  │
│                                                                  │
│  TaskRunner                                                       │
│   ├── Viewport ──► AIBot.plan_task(frame, task)                  │
│   │   (always on)  AIBot.generate_executable_steps(frame, task)  │
│   ├── ActionExecutor.execute_plan(steps)                         │
│   ├── task_history (last 50 tasks)                               │
│   └── Overlay ◄── minimap + last-result refresh                  │
└──────────────────────────────────────────────────────────────────┘
```

The viewport is **always active** regardless of whether input control is enabled or disabled.

---

## Action step syntax

`AIBot.generate_executable_steps()` produces step strings that
`ActionExecutor.execute_plan()` can run directly:

```
CLICK <x> <y>                  left click at screen position
CLICK <x> <y> right            right-click
DOUBLE_CLICK <x> <y>           double-click
RIGHT_CLICK <x> <y>            right-click (alias)
DRAG <x1> <y1> <x2> <y2>      click-and-drag
SCROLL <n>                     scroll n clicks (positive=up, negative=down)
TYPE <text>                    type text
PRESS <key>                    press a key (enter, escape, tab, …)
HOTKEY <key1> <key2> ...       key combination (ctrl c, alt f4, …)
WAIT <seconds>                 pause
SCREENSHOT                     capture and store a screenshot
# comment                      ignored
```

---

## AI model

The bot uses [`microsoft/Florence-2-base`](https://huggingface.co/microsoft/Florence-2-base) – a compact vision-language model (~230 M params) capable of:

- **Screen description** – natural-language captions of the current screen
- **OCR** – read all visible text (games, business apps, web pages)
- **UI element detection** – locate buttons, text fields, icons with bounding boxes
- **Open-vocabulary detection** – find specific objects/elements by description
- **Task planning** – produce a human-readable step-by-step action plan
- **Executable steps** – generate structured `CLICK / TYPE / PRESS` commands

Weights are downloaded automatically from the Hugging Face Hub on first run and cached locally.


---

## Features

| Feature | Details |
|---|---|
| **Bot input control** | Simulate mouse moves, clicks, drags, scroll and keyboard via `InputController` (pyautogui) |
| **Multi-monitor viewport** | Capture any or all connected monitors; build side-by-side mini-map thumbnails (mss + Pillow) |
| **Overlay HUD** | Always-on-top transparent status window showing input control and AI bot state |
| **Global hotkeys** | `Ctrl+L` – toggle overlay · `Ctrl+Alt+Home` – enable input · `Ctrl+Alt+End` – disable input |
| **AI bot** | `microsoft/Florence-2-base` mini vision-language model (~230 M params) – describes screens, reads text (OCR), detects UI elements, and plans tasks |
| **Task runner** | Background thread that feeds viewport frames to the AI bot and executes returned actions |

---

## Requirements

- Python 3.10+
- Linux / Windows / macOS (display required at runtime; tests run headless)

Install dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** `tkinter` is part of the Python standard library but may need a separate system package on some Linux distributions:
> ```bash
> sudo apt install python3-tk   # Debian/Ubuntu
> ```

---

## Quick start

```bash
# Start the full system (overlay + hotkeys + AI bot + minimap)
python main.py

# Start without loading the AI model (useful for low-memory machines)
python main.py --no-ai

# Submit a one-shot task and print the result
python main.py --task "Close all open browser tabs"

# Use a different monitor as the primary viewport
python main.py --monitor 2

# Use a custom Hugging Face model
python main.py --model "microsoft/Florence-2-large"
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
├── main.py                   Entry point
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── input_controller.py   Bot-driven mouse & keyboard (pyautogui)
│   ├── viewport.py           Multi-monitor screen capture (mss + Pillow)
│   ├── overlay.py            Transparent status HUD (tkinter)
│   ├── hotkey_manager.py     Global hotkey listener (pynput)
│   ├── ai_bot.py             HuggingFace vision-language bot (Florence-2)
│   └── task_runner.py        Orchestration: viewport → AI → input
└── tests/
    ├── test_input_controller.py
    ├── test_viewport.py
    ├── test_overlay.py
    ├── test_hotkey_manager.py
    └── test_task_runner.py
```

---

## Running tests

```bash
python -m pytest tests/ -v
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                        main.py                           │
│  HotkeyManager ──────► InputController (enable/disable)  │
│       │                                                   │
│       └──────────────► Overlay (toggle)                  │
│                                                           │
│  TaskRunner                                               │
│   ├── Viewport ──────► AIBot.plan_task(frame, task)       │
│   │   (always on)      (Florence-2 vision-language model) │
│   └── Overlay ──────── minimap refresh every 3 s         │
└──────────────────────────────────────────────────────────┘
```

The viewport is **always active** regardless of whether input control is enabled or disabled.

---

## AI model

The bot uses [`microsoft/Florence-2-base`](https://huggingface.co/microsoft/Florence-2-base) – a compact vision-language model capable of:

- **Screen description** – natural-language captions of the current screen
- **OCR** – read all visible text (useful for games, business apps, web pages)
- **UI element detection** – locate buttons, text fields, icons
- **Open-vocabulary detection** – find specific objects by description
- **Task planning** – combine the above to produce a step-by-step action plan

Weights are downloaded automatically from the Hugging Face Hub on first run and cached locally.

