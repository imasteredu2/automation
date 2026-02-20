# automation

AI-powered desktop automation with multi-monitor viewport, overlay HUD, and Hugging Face mini vision-language bot.

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

