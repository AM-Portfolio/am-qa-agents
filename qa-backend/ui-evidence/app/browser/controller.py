import logging
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import Browser, async_playwright

logger = logging.getLogger(__name__)


class BrowserController:
    def __init__(self):
        self.playwright = None
        self.browser: Browser | None = None

    async def start(self, headless: bool = True) -> Browser:
        logger.info("Launching Playwright Browser (headless=%s)...", headless)
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        return self.browser

    async def stop(self):
        if self.browser:
            logger.info("Stopping Playwright Browser...")
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Playwright Browser stopped.")

    @asynccontextmanager
    async def get_page(
        self,
        viewport_width: int = 1280,
        viewport_height: int = 800,
        *,
        trace_dir: str | Path | None = None,
        trace_mode: str = "off",
        console_sink: list | None = None,
        save_trace_ref: list | None = None,
    ):
        """Yield (page, trace_path). Set save_trace_ref[0]=True to force-save on-failure traces."""
        assert self.browser is not None
        context = await self.browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height}
        )
        trace_path = None
        if trace_mode in ("on", "on-failure") and trace_dir:
            Path(trace_dir).mkdir(parents=True, exist_ok=True)
            await context.tracing.start(screenshots=True, snapshots=True, sources=False)
            trace_path = Path(trace_dir) / "trace.zip"

        page = await context.new_page()
        if console_sink is not None:

            def _on_console(msg):  # type: ignore[no-untyped-def]
                if msg.type in ("error", "warning"):
                    console_sink.append(f"[{msg.type}] {msg.text}")

            page.on("console", _on_console)

        raised = False
        try:
            yield page, trace_path
        except Exception:
            raised = True
            raise
        finally:
            if trace_path is not None:
                force = bool(save_trace_ref and save_trace_ref[0])
                should_save = trace_mode == "on" or (
                    trace_mode == "on-failure" and (raised or force)
                )
                if should_save:
                    await context.tracing.stop(path=str(trace_path))
                else:
                    await context.tracing.stop()
                    if Path(trace_path).is_file():
                        Path(trace_path).unlink(missing_ok=True)
            await page.close()
            await context.close()


browser_controller = BrowserController()
