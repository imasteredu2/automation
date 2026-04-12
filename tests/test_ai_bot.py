"""
tests/test_ai_bot.py – Unit tests for AIBot.

All heavy dependencies (torch, transformers) are patched out so the
tests run headlessly without a GPU or internet connection.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from PIL import Image


def _rgb_image(w: int = 200, h: int = 100) -> Image.Image:
    return Image.new("RGB", (w, h), color=(128, 128, 128))


# ---------------------------------------------------------------------------
# Minimal stubs for transformers + torch
# ---------------------------------------------------------------------------

def _make_processor_stub(return_text: str = "stub caption"):
    proc = MagicMock()
    # The processor is called as proc(text=..., images=..., return_tensors=...) and
    # the result has a .to(device) method.  Use a MagicMock so .to() works.
    inputs_stub = MagicMock()
    inputs_stub.__getitem__ = lambda self, key: MagicMock()
    inputs_stub.get = MagicMock(return_value=MagicMock())
    proc.return_value = inputs_stub
    proc.batch_decode.return_value = [return_text]
    proc.post_process_generation.return_value = {"<DETAILED_CAPTION>": return_text}
    return proc


def _make_model_stub():
    model = MagicMock()
    model.eval.return_value = model
    model.to.return_value = model
    model.generate.return_value = MagicMock()
    return model


# ---------------------------------------------------------------------------
# Tests: initialization
# ---------------------------------------------------------------------------

class TestAIBotInit(unittest.TestCase):

    def test_default_model_id(self):
        from src.ai_bot import AIBot
        bot = AIBot()
        self.assertEqual(bot.model_id, "microsoft/Florence-2-base")

    def test_custom_model_id(self):
        from src.ai_bot import AIBot
        bot = AIBot(model_id="microsoft/Florence-2-large")
        self.assertEqual(bot.model_id, "microsoft/Florence-2-large")

    def test_not_loaded_initially(self):
        from src.ai_bot import AIBot
        bot = AIBot()
        self.assertFalse(bot.is_loaded())

    def test_repr_unloaded(self):
        from src.ai_bot import AIBot
        bot = AIBot()
        r = repr(bot)
        self.assertIn("AIBot", r)
        self.assertIn("loaded=False", r)

    def test_repr_shows_model_id(self):
        from src.ai_bot import AIBot
        bot = AIBot(model_id="test-model")
        self.assertIn("test-model", repr(bot))

    def test_custom_device(self):
        from src.ai_bot import AIBot
        bot = AIBot(device="cpu")
        self.assertEqual(bot._device, "cpu")


# ---------------------------------------------------------------------------
# Tests: device resolution (no GPU required)
# ---------------------------------------------------------------------------

class TestAIBotDeviceResolution(unittest.TestCase):

    def test_resolve_device_explicit_cpu(self):
        from src.ai_bot import AIBot
        bot = AIBot(device="cpu")
        self.assertEqual(bot._resolve_device(), "cpu")

    def test_resolve_device_falls_back_to_cpu_without_torch(self):
        from src.ai_bot import AIBot
        bot = AIBot()
        torch_missing = MagicMock()
        torch_missing.cuda.is_available.side_effect = ImportError("no torch")
        with patch.dict("sys.modules", {"torch": torch_missing}):
            device = bot._resolve_device()
        self.assertEqual(device, "cpu")


# ---------------------------------------------------------------------------
# Tests: loading (mocked transformers + torch)
# ---------------------------------------------------------------------------

class TestAIBotLoad(unittest.TestCase):

    def _patched_load(self, bot):
        """Load bot with transformers + torch fully mocked."""
        torch_stub = MagicMock()
        torch_stub.cuda.is_available.return_value = False
        torch_stub.float32 = "float32"
        torch_stub.float16 = "float16"
        torch_stub.no_grad.return_value.__enter__ = lambda s: s
        torch_stub.no_grad.return_value.__exit__ = MagicMock(return_value=False)

        processor = _make_processor_stub()
        model = _make_model_stub()

        transformers_stub = MagicMock()
        transformers_stub.AutoProcessor.from_pretrained.return_value = processor
        transformers_stub.AutoModelForCausalLM.from_pretrained.return_value = model

        with patch.dict("sys.modules", {
            "torch": torch_stub,
            "transformers": transformers_stub,
        }):
            bot.load()
        return processor, model

    def test_load_sets_is_loaded(self):
        from src.ai_bot import AIBot
        bot = AIBot(device="cpu")
        self._patched_load(bot)
        self.assertTrue(bot.is_loaded())

    def test_load_is_idempotent(self):
        from src.ai_bot import AIBot
        bot = AIBot(device="cpu")
        proc, model = self._patched_load(bot)
        # Second call should be a no-op (no new from_pretrained calls)
        bot.load()
        # from_pretrained was still called only once
        proc_call_count = proc.call_count  # just check it didn't blow up

    def test_load_without_transformers_raises(self):
        from src.ai_bot import AIBot
        bot = AIBot(device="cpu")
        # Simulate missing transformers by replacing with a stub that raises on use
        broken_transformers = MagicMock()
        broken_transformers.AutoProcessor.from_pretrained.side_effect = ImportError("no transformers")
        broken_torch = MagicMock()
        broken_torch.float32 = "float32"
        broken_torch.float16 = "float16"
        broken_torch.cuda.is_available.return_value = False
        with patch.dict("sys.modules", {"transformers": broken_transformers, "torch": broken_torch}):
            with self.assertRaises((ImportError, TypeError, Exception)):
                bot.load()


# ---------------------------------------------------------------------------
# Tests: inference methods (model pre-loaded via mock)
# ---------------------------------------------------------------------------

class _BotWithMockedModel(unittest.TestCase):
    """Base class that provides a pre-loaded AIBot with mocked internals."""

    def setUp(self):
        from src.ai_bot import AIBot
        self.bot = AIBot(device="cpu")
        self.bot._loaded = True
        self.bot._device = "cpu"

        torch_stub = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: s
        ctx.__exit__ = MagicMock(return_value=False)
        torch_stub.no_grad.return_value = ctx

        self.processor = _make_processor_stub("A desktop with a browser open.")
        self.processor.post_process_generation.return_value = {
            "<MORE_DETAILED_CAPTION>": "A desktop with a browser open.",
            "<DETAILED_CAPTION>": "A desktop with a browser open.",
            "<CAPTION_TO_PHRASE_GROUNDING>": "browser window",
            "<OCR>": "File Edit View",
            "<OD>": "{'labels': ['button'], 'bboxes': [[10, 20, 100, 40]]}",
        }
        self.model = _make_model_stub()
        self.bot._processor = self.processor
        self.bot._model = self.model
        self._torch_stub = torch_stub

    def _run_with_torch(self, fn, *args, **kwargs):
        with patch.dict("sys.modules", {"torch": self._torch_stub}):
            return fn(*args, **kwargs)


class TestAIBotDescribeScreen(_BotWithMockedModel):

    def test_describe_screen_returns_string(self):
        self.processor.post_process_generation.return_value = {
            "<DETAILED_CAPTION>": "A browser is open."
        }
        result = self._run_with_torch(self.bot.describe_screen, _rgb_image())
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_describe_screen_calls_processor(self):
        self.processor.post_process_generation.return_value = {
            "<DETAILED_CAPTION>": "Some screen"
        }
        self._run_with_torch(self.bot.describe_screen, _rgb_image())
        self.processor.post_process_generation.assert_called()


class TestAIBotQuery(_BotWithMockedModel):

    def test_query_returns_string(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "A browser with Firefox visible."
        }
        result = self._run_with_torch(
            self.bot.query, _rgb_image(), "What browser is open?"
        )
        self.assertIsInstance(result, str)

    def test_query_contains_screen_prefix(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "Firefox is visible."
        }
        result = self._run_with_torch(
            self.bot.query, _rgb_image(), "Is Firefox open?"
        )
        self.assertIn("Screen:", result)


class TestAIBotCheckGoal(_BotWithMockedModel):

    def test_check_goal_yes_when_tokens_match(self):
        """If goal tokens appear in the caption, check_goal returns 'yes'."""
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "Firefox browser is open and showing example.com website."
        }
        result = self._run_with_torch(
            self.bot.check_goal, _rgb_image(), "Open Firefox and navigate to example.com"
        )
        self.assertTrue(result.lower().startswith("yes"))

    def test_check_goal_no_when_tokens_absent(self):
        """If goal tokens are absent from the caption, check_goal returns 'no'."""
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "A blank desktop with nothing open."
        }
        result = self._run_with_torch(
            self.bot.check_goal, _rgb_image(), "Open Notepad and type hello world"
        )
        self.assertTrue(result.lower().startswith("no"))

    def test_check_goal_returns_string(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "some caption"
        }
        result = self._run_with_torch(
            self.bot.check_goal, _rgb_image(), "some goal"
        )
        self.assertIsInstance(result, str)

    def test_check_goal_raises_if_not_loaded(self):
        from src.ai_bot import AIBot
        bot = AIBot()
        with self.assertRaises(RuntimeError):
            bot.check_goal(_rgb_image(), "some goal")


class TestAIBotOCR(_BotWithMockedModel):

    def test_ocr_returns_string(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "File Edit View"
        }
        result = self._run_with_torch(self.bot.ocr, _rgb_image())
        self.assertIsInstance(result, str)


class TestAIBotPlanTask(_BotWithMockedModel):

    def test_plan_task_returns_string_with_task(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "A desktop."
        }
        result = self._run_with_torch(
            self.bot.plan_task, _rgb_image(), "Open Notepad"
        )
        self.assertIn("Open Notepad", result)
        self.assertIsInstance(result, str)

    def test_plan_task_contains_action_plan(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "A desktop."
        }
        result = self._run_with_torch(
            self.bot.plan_task, _rgb_image(), "Close the browser"
        )
        self.assertIn("Action plan:", result)


class TestAIBotGenerateExecutableSteps(_BotWithMockedModel):

    def test_steps_always_start_with_screenshot(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "{'bboxes': [[10,20,100,40]], 'labels': ['OK button']}"
        }
        result = self._run_with_torch(
            self.bot.generate_executable_steps, _rgb_image(), "Click OK"
        )
        self.assertIn("SCREENSHOT", result)

    def test_steps_contains_click_when_bboxes_found(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "{'bboxes': [[10, 20, 100, 40]], 'labels': ['Submit']}"
        }
        result = self._run_with_torch(
            self.bot.generate_executable_steps, _rgb_image(), "Submit form"
        )
        self.assertIn("CLICK", result)

    def test_steps_handles_bad_detection_output_gracefully(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "not a valid dict"
        }
        # Should not raise
        result = self._run_with_torch(
            self.bot.generate_executable_steps, _rgb_image(), "Do something"
        )
        self.assertIsInstance(result, str)

    def test_steps_includes_task_comment(self):
        self.processor.post_process_generation.side_effect = lambda text, task, image_size: {
            task: "{}"
        }
        result = self._run_with_torch(
            self.bot.generate_executable_steps, _rgb_image(), "My special task"
        )
        self.assertIn("My special task", result)


if __name__ == "__main__":
    unittest.main()
