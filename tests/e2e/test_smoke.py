import os
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect


pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000").rstrip("/")


def _register(page, name, email, password):
    page.goto(f"{BASE_URL}/")
    page.get_by_role("button", name="Create account").click()
    page.get_by_label("Name").fill(name)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Create account", exact=True).last.click()
    expect(page.get_by_role("heading", name=f"Welcome, {name}")).to_be_visible(
        timeout=15000
    )


def test_register_search_add_friend_and_find_named_path():
    email_a = f"phase9-{uuid.uuid4().hex[:12]}@example.test"
    email_b = f"phase9-{uuid.uuid4().hex[:12]}@example.test"
    password = "phase-nine-test-password"
    hostile_name = '<img src=x onerror="alert(1)">'

    with playwright.sync_playwright() as playwright_context:
        browser = playwright_context.chromium.launch()
        page = browser.new_page()
        page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        try:
            _register(page, hostile_name, email_a, password)
            expect(page.locator("#welcome-name")).to_have_text(hostile_name)
            assert page.locator("#welcome-name img").count() == 0
            page.get_by_role("button", name="Sign out").click()

            _register(page, "Path Partner", email_b, password)
            page.get_by_role("button", name="Sign out").click()

            page.goto(f"{BASE_URL}/")
            page.get_by_label("Email").fill(email_a)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Sign in", exact=True).last.click()
            expect(
                page.get_by_role("heading", name=f"Welcome, {hostile_name}")
            ).to_be_visible(timeout=15000)

            page.get_by_role("button", name="Friends", exact=True).click()
            page.get_by_label("Find people by name").fill("Path Partner")
            page.get_by_role("button", name="Search", exact=True).click()
            partner_card = page.locator("article.user-card").filter(
                has_text="Path Partner"
            )
            expect(partner_card).to_be_visible(timeout=15000)
            partner_text = partner_card.inner_text()
            partner_id = (
                partner_text.split("ID ", 1)[1].splitlines()[0].split(" ·", 1)[0]
            )
            partner_card.get_by_role("button", name="Add friend").click()
            expect(partner_card.get_by_role("button", name="Added")).to_be_visible()

            page.get_by_role("button", name="Profile", exact=True).click()
            own_id_element = page.locator("#profile-id")
            expect(own_id_element).not_to_be_empty(timeout=15000)
            own_id = own_id_element.inner_text()
            page.get_by_role("button", name="Find a path", exact=True).click()
            page.get_by_label("From person (name or ID)").fill(own_id)
            page.get_by_label("To person (name or ID)").fill(partner_id)
            page.get_by_role("button", name="Find path", exact=True).click()
            expect(page.locator("#path-result")).to_contain_text(
                "Path Partner", timeout=15000
            )
            expect(page.locator("#path-result")).to_contain_text(hostile_name)
            assert page.locator("#path-result img").count() == 0
        except Exception:
            Path("test-results").mkdir(exist_ok=True)
            page.context.tracing.stop(path="test-results/playwright-trace.zip")
            raise
        else:
            page.context.tracing.stop()
        finally:
            browser.close()
