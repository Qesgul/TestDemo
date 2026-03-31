from playwright.sync_api import expect


def expect_text(locator, expected_text: str) -> None:
    expect(locator).to_have_text(expected_text)
