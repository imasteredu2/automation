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

        Parameters
        ----------
        image:
            Screenshot as a Pillow Image.
        question:
            Free-form question in plain English.
        """
        logger.debug("query called: %s", question)
        return self._run(image, "<OPEN_VOCABULARY_DETECTION>", question)

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
            "  1. Analyse the elements above to locate the target controls.",
            "  2. Use InputController to click / type as needed.",
            "  3. Capture a new screenshot and verify the result.",
            "  4. Repeat until the task is complete.",
        ]
        return "\n".join(plan_lines)

    def __repr__(self) -> str:
        return f"AIBot(model_id={self.model_id!r}, loaded={self._loaded})"
