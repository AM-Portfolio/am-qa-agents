import pytest

from ui_evidence.browser.actions import _fill_labeled_input


@pytest.mark.asyncio
async def test_fill_labeled_input_rejects_empty_password():
    with pytest.raises(RuntimeError, match="empty text"):
        await _fill_labeled_input(page=None, label="Password", text="")
