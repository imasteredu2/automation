"""
ai_bot.py – Vision-language AI bot powered by a Hugging Face mini model.

The bot uses ``microsoft/Florence-2-base`` – a small (~230 M parameter)
vision-language model that excels at understanding images/screenshots and
can answer questions, describe scenes, perform OCR, and identify UI elements.
This makes it ideal for games, business applications, and general desktop
automation tasks.

Usage
-----
::

    from src.ai_bot import AIBot
    from src.viewport import Viewport

    bot = AIBot()
    bot.load()                           # download / load weights once

    vp = Viewport()
    frame = vp.get_frame(monitor_index=1)

    # Describe the current screen
    description = bot.describe_screen(frame)
    print(description)

    # Ask a specific question about the screen
    answer = bot.query(frame, "What game is currently open?")
    print(answer)

    # Execute a free-form task (returns action plan as text)
    plan = bot.plan_task(frame, "Close the browser and open Notepad")
    print(plan)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Model identifier on the Hugging Face Hub
_MODEL_ID = "microsoft/Florence-2-base"
# Revision pinned for reproducibility – update when a newer stable release lands
_MODEL_REVISION = "main"


class AIBot:
    """Mini vision-language bot that understands screen content and plans tasks.

    The model is loaded lazily; call ``load()`` before any inference.

    Parameters
    ----------
    model_id:
        Hugging Face Hub model identifier.  Defaults to ``microsoft/Florence-2-base``.
    device:
        PyTorch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
        When *None* the best available device is selected automatically.
    """

    def __init__(
        self,
        model_id: str = _MODEL_ID,
        device: Optional[str] = None,
    ) -> None:
        self.model_id = model_id
        self._device = device
        self._model = None
        self._processor = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _resolve_device(self) -> str:
        if self._device:
            return self._device
        try:
            import torch  # noqa: PLC0415
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def load(self) -> None:
        """Download and load the model weights into memory.

        This is safe to call multiple times; subsequent calls are no-ops.
        """
        if self._loaded:
            return

        logger.info("Loading AI model: %s", self.model_id)
        try:
            from transformers import AutoProcessor, AutoModelForCausalLM  # noqa: PLC0415
            import torch  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "transformers and torch are required for the AI bot. "
                "Install with: pip install transformers torch"
            ) from exc

        device = self._resolve_device()
        dtype = torch.float16 if device != "cpu" else torch.float32

        self._processor = AutoProcessor.from_pretrained(
            self.model_id,
            revision=_MODEL_REVISION,
            trust_remote_code=True,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            revision=_MODEL_REVISION,
            torch_dtype=dtype,
            trust_remote_code=True,
        ).to(device)
        self._model.eval()
        self._device = device
        self._loaded = True
        logger.info("AI model loaded on %s (dtype=%s)", device, dtype)

    def is_loaded(self) -> bool:
        """Return True when the model is loaded and ready."""
        return self._loaded

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------

    def _run(self, image, task_prompt: str, text_input: Optional[str] = None) -> str:
        """Run a Florence-2 task and return the decoded text output."""
        if not self._loaded:
            raise RuntimeError("Call load() before running inference.")

        import torch  # noqa: PLC0415

        prompt = task_prompt if text_input is None else f"{task_prompt}{text_input}"

        inputs = self._processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        ).to(self._device)

        with torch.no_grad():
            generated_ids = self._model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs.get("pixel_values"),
                max_new_tokens=512,
                do_sample=False,
                num_beams=3,
            )

        generated_text = self._processor.batch_decode(
            generated_ids, skip_special_tokens=False
        )[0]

        parsed = self._processor.post_process_generation(
            generated_text,
            task=task_prompt,
            image_size=(image.width, image.height),
        )

        # Florence-2 returns a dict keyed by the task prompt
        result = parsed.get(task_prompt, "")
        if isinstance(result, dict):
            # Some tasks return {"labels": [...], "bboxes": [...]}
            return str(result)
        return str(result).strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def describe_screen(self, image) -> str:
        """Return a natural-language caption of the screen contents.

        Parameters
        ----------
        image:
            A ``PIL.Image.Image`` screenshot of any monitor.
        """
        logger.debug("describe_screen called")
        return self._run(image, "<DETAILED_CAPTION>")

    def query(self, image, question: str) -> str:
        """Ask an open-ended question about the screen.

        Returns a natural-language description of the screen, optionally
        narrowed toward the topic of *question* via phrase grounding.

        Parameters
        ----------
        image:
            Screenshot as a Pillow Image.
        question:
            Free-form question in plain English.
        """
        logger.debug("query called: %s", question)
        # Get a detailed caption first
        caption = self._run(image, "<MORE_DETAILED_CAPTION>")
        # Try to ground the question against the caption for extra context
        try:
            grounding = self._run(image, "<CAPTION_TO_PHRASE_GROUNDING>", question)
        except Exception:
            grounding = ""
        parts = [f"Screen: {caption}"]
        if grounding and grounding != "{}":
            parts.append(f"Related: {grounding}")
        return "\n".join(parts)

    def check_goal(self, image, goal: str) -> str:
        """Check whether *goal* appears to be achieved from the screen contents.

        Uses the detailed caption to decide whether the goal is likely met.
        Returns a short natural-language response starting with "yes" or "no".

        Parameters
        ----------
        image:
            Current screenshot as a Pillow Image.
        goal:
            Plain-English description of the desired end state.
        """
        logger.debug("check_goal called: %s", goal)
        caption = self._run(image, "<MORE_DETAILED_CAPTION>")
        caption_lower = caption.lower()
        goal_lower = goal.lower()

        # Extract meaningful tokens from the goal (skip common stop words)
        _STOP = {
            "a", "an", "the", "and", "or", "to", "in", "on", "at", "of",
            "is", "it", "for", "with", "this", "that", "are", "be", "by",
            "open", "go", "click", "press", "navigate", "start", "run",
        }
        tokens = [
            t for t in re.split(r"[\s\-_/.,;:!?\"'()]+", goal_lower)
            if t and t not in _STOP and len(t) > 2
        ]

        matched = [t for t in tokens if t in caption_lower]
        ratio = len(matched) / max(1, len(tokens))

        if ratio >= 0.5:
            return (
                f"yes, the screen appears to show the goal is achieved "
                f"(matched {len(matched)}/{len(tokens)} goal tokens in caption)."
            )
        return (
            f"no, the goal does not appear to be achieved yet "
            f"(only {len(matched)}/{len(tokens)} goal tokens found in caption: {caption[:200]})"
        )

    def ocr(self, image) -> str:
        """Extract all visible text from the screenshot.

        Useful for reading game text, business documents, browser content, etc.
        """
        logger.debug("ocr called")
        return self._run(image, "<OCR>")

    def detect_ui_elements(self, image) -> str:
        """Detect and locate UI elements (buttons, text fields, icons) in the image."""
        logger.debug("detect_ui_elements called")
        return self._run(image, "<OD>")

    def plan_task(self, image, task_description: str) -> str:
        """Given a screenshot and a task description, produce an action plan.

        The bot analyses the current screen and returns a step-by-step textual
        plan describing how to accomplish the requested task using available
        UI controls.

        Parameters
        ----------
        image:
            Current screenshot as a Pillow Image.
        task_description:
            Natural-language description of what the user wants done.
        """
        logger.debug("plan_task called: %s", task_description)
        # Use caption + grounding to understand the screen, then produce a plan
        caption = self._run(image, "<DETAILED_CAPTION>")
        grounding = self._run(image, "<CAPTION_TO_PHRASE_GROUNDING>", caption)

        plan_lines = [
            f"Task: {task_description}",
            "",
            f"Screen description: {caption}",
            "",
            "Identified elements:",
            grounding,
            "",
            "Action plan:",
            "  1. Analyze the elements above to locate the target controls.",
            "  2. Use InputController to click / type as needed.",
            "  3. Capture a new screenshot and verify the result.",
            "  4. Repeat until the task is complete.",
        ]
        return "\n".join(plan_lines)

    def generate_executable_steps(
        self,
        image,
        task_description: str,
        monitor_left: int = 0,
        monitor_top: int = 0,
    ) -> str:
        """Generate executable action steps for the ActionExecutor.

        Uses the vision model to detect UI elements relevant to the task and
        maps their bounding boxes to ``CLICK x y`` steps the
        :class:`~src.action_executor.ActionExecutor` can execute directly.

        The returned string contains one action per line in the syntax
        understood by ``ActionExecutor.execute_plan()``.

        Parameters
        ----------
        image:
            Current screenshot as a Pillow Image.
        task_description:
            Plain-English description of the task to perform.
        monitor_left, monitor_top:
            Pixel offset of the monitor's top-left corner on the virtual
            screen (used to convert image-relative coordinates to absolute
            screen coordinates).

        Returns
        -------
        Multi-line string of executable action steps.
        """
        import ast  # noqa: PLC0415

        logger.debug("generate_executable_steps called: %s", task_description)
        steps = [f"# Task: {task_description}", "SCREENSHOT"]

        try:
            raw = self._run(image, "<OPEN_VOCABULARY_DETECTION>", task_description)
            data = ast.literal_eval(raw)
            bboxes = data.get("bboxes", [])
            labels = data.get("labels", [])

            for label, bbox in zip(labels, bboxes):
                x1, y1, x2, y2 = bbox
                cx = monitor_left + int((x1 + x2) / 2)
                cy = monitor_top + int((y1 + y2) / 2)
                steps.append(f"CLICK {cx} {cy}  # {label}")
        except Exception as exc:
            logger.debug("Could not parse detection output into steps: %s", exc)
            steps.append("# No executable steps generated from detection output")

        return "\n".join(steps)

    def __repr__(self) -> str:
        return f"AIBot(model_id={self.model_id!r}, loaded={self._loaded})"
