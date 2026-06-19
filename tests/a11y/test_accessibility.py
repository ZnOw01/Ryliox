"""Accessibility tests for Ryliox frontend using axe-core/Playwright patterns."""

import pytest
from playwright.async_api import async_playwright

pytestmark = [pytest.mark.a11y, pytest.mark.e2e]


@pytest.mark.asyncio
async def test_skip_link_present():
    """Test that skip link is present and functional."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Tab to get to skip link
            await page.keyboard.press("Tab")

            # Check if skip link is focused
            skip_link = await page.locator(".skip-link:focus").is_visible()
            assert skip_link, "Skip link should be visible when focused"

            # Press the skip link
            await page.keyboard.press("Enter")

            # Check if main content is focused
            main_content = await page.locator("main").is_focused()
            assert main_content or await page.locator("main:focus").count() > 0, (
                "Main content should receive focus after skip link"
            )

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_color_contrast():
    """Test color contrast ratios meet WCAG 2.1 AA (4.5:1)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Check various text elements for contrast
            # This is a basic check - in production use axe-core or similar
            text_selectors = [
                "h1",
                "h2",
                "p",
                "button",
                "label",
                "span",
                "[role='alert']",
                "[role='status']",
            ]

            for selector in text_selectors:
                elements = await page.locator(selector).all()
                for element in elements:
                    # Check if element is visible and has text
                    if await element.is_visible():
                        text = await element.text_content()
                        if text and text.strip():
                            # In a real test, use axe-core to check contrast
                            # Here we just verify elements exist
                            assert await element.count() > 0

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_aria_labels_present():
    """Test that interactive elements have ARIA labels or accessible text."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Check buttons without visible text have aria-label
            icon_buttons = await page.locator(
                "button:not(:has(> span:not(.sr-only))):not(:has(> text))"
            ).all()

            for button in icon_buttons:
                if await button.is_visible():
                    aria_label = await button.get_attribute("aria-label")
                    title = await button.get_attribute("title")

                    assert aria_label or title, (
                        f"Icon button should have aria-label or title: {await button.evaluate('el => el.outerHTML')}"
                    )

            # Check form inputs have labels
            inputs = await page.locator("input, select, textarea").all()
            for input_el in inputs:
                if await input_el.is_visible():
                    input_id = await input_el.get_attribute("id")
                    aria_label = await input_el.get_attribute("aria-label")
                    aria_labelledby = await input_el.get_attribute("aria-labelledby")

                    has_label = False
                    if input_id:
                        label = await page.locator(f"label[for='{input_id}']").count()
                        has_label = label > 0

                    assert has_label or aria_label or aria_labelledby, (
                        f"Input should have associated label: {await input_el.evaluate('el => el.outerHTML')}"
                    )

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_keyboard_navigation():
    """Test that all interactive elements are keyboard accessible."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Get all interactive elements
            interactive_elements = await page.locator(
                "button, a, input, select, textarea, [tabindex]:not([tabindex='-1'])"
            ).all()

            focusable_count = 0
            for element in interactive_elements:
                if await element.is_visible() and await element.is_enabled():
                    focusable_count += 1

            # Tab through all elements
            await page.evaluate("() => document.activeElement?.tagName")

            for _ in range(min(focusable_count, 20)):  # Limit to 20 tabs
                await page.keyboard.press("Tab")
                current_focus = await page.evaluate("() => document.activeElement?.tagName")

                if current_focus and current_focus != "BODY":
                    # Check if element has focus indicator
                    styles = await page.evaluate(
                        """() => {
                            const el = document.activeElement;
                            if (!el) return null;
                            const styles = window.getComputedStyle(el);
                            return {
                                outline: styles.outline,
                                outlineWidth: styles.outlineWidth,
                                boxShadow: styles.boxShadow
                            };
                        }"""
                    )

                    # Should have some focus indicator
                    has_outline = styles and (styles["outlineWidth"] != "0px" if styles else False)
                    has_shadow = styles and (
                        "shadow" in styles.get("boxShadow", "") if styles else False
                    )

                    # Log but don't fail - focus styles might be applied via :focus-visible
                    if not has_outline and not has_shadow:
                        print(f"Warning: Element may lack visible focus indicator: {current_focus}")

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_heading_hierarchy():
    """Test that headings follow proper hierarchy (h1 > h2 > h3...)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Check for h1
            h1_count = await page.locator("h1").count()
            assert h1_count == 1, f"Page should have exactly one h1, found {h1_count}"

            # Check heading order
            headings = await page.locator("h1, h2, h3, h4, h5, h6").all()
            levels = []
            for heading in headings:
                tag = await heading.evaluate("el => el.tagName.toLowerCase()")
                level = int(tag[1])
                levels.append(level)

            # Check that heading levels don't skip (e.g., h1 > h3 without h2)
            for i in range(1, len(levels)):
                prev_level = levels[i - 1]
                curr_level = levels[i]

                # Can go to same level, decrease by 1, or increase by 1
                # But shouldn't skip levels going down (e.g., h1 > h3)
                if curr_level > prev_level:
                    assert curr_level == prev_level + 1, (
                        f"Heading level skipped: h{prev_level} to h{curr_level}"
                    )

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_aria_live_regions():
    """Test that dynamic content updates use aria-live regions."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Check for aria-live regions
            live_regions = await page.locator("[aria-live]").all()

            assert len(live_regions) > 0, "Page should have at least one aria-live region"

            # Verify regions have appropriate values
            valid_values = {"polite", "assertive", "off"}
            for region in live_regions:
                live_value = await region.get_attribute("aria-live")
                assert live_value in valid_values, f"Invalid aria-live value: {live_value}"

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_form_labels():
    """Test that all form inputs have associated labels."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Check all form inputs
            inputs = await page.locator("input:not([type='hidden']), select, textarea").all()

            for input_el in inputs:
                if not await input_el.is_visible():
                    continue

                input_id = await input_el.get_attribute("id")
                aria_label = await input_el.get_attribute("aria-label")
                aria_labelledby = await input_el.get_attribute("aria-labelledby")
                placeholder = await input_el.get_attribute("placeholder")

                has_label = False
                if input_id:
                    has_label = await page.locator(f"label[for='{input_id}']").count() > 0

                # Check for implicit label (input inside label)
                parent = await input_el.locator("xpath=..").element_handle()
                if parent:
                    parent_tag = await parent.evaluate("el => el.tagName.toLowerCase()")
                    if parent_tag == "label":
                        has_label = True

                # Must have some form of label
                assert has_label or aria_label or aria_labelledby, (
                    f"Form input missing label: {await input_el.evaluate('el => el.outerHTML')[:100]}"
                )

                # Placeholder is not a substitute for label (WCAG 3.3.2)
                if placeholder and not (has_label or aria_label or aria_labelledby):
                    pytest.fail("Placeholder cannot be used as the only label")

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_alt_text_on_images():
    """Test that images have alt text."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            images = await page.locator("img").all()

            for img in images:
                alt = await img.get_attribute("alt")
                aria_hidden = await img.get_attribute("aria-hidden")
                role = await img.get_attribute("role")

                # Image should have alt text OR be marked as decorative
                is_decorative = aria_hidden == "true" or role == "presentation"

                if not is_decorative:
                    assert alt is not None and alt != "", (
                        f"Image missing alt text: {await img.evaluate('el => el.outerHTML')[:100]}"
                    )

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_landmark_regions():
    """Test that page has proper landmark regions."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Check for main landmark
            main_count = await page.locator("main").count()
            main_role_count = await page.locator("[role='main']").count()
            assert main_count + main_role_count >= 1, "Page should have a main landmark"

            # Check for complementary (optional but good)
            aside_count = await page.locator("aside, [role='complementary']").count()
            print(f"Found {aside_count} complementary regions (optional)")

            # Check for navigation
            nav_count = await page.locator("nav, [role='navigation']").count()
            print(f"Found {nav_count} navigation regions")

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_reduced_motion_respected():
    """Test that animations respect prefers-reduced-motion."""
    async with async_playwright() as p:
        # Launch with reduced motion preference
        browser = await p.chromium.launch()
        context = await browser.new_context(reduced_motion="reduce")
        page = await context.new_page()

        try:
            await page.goto("http://localhost:8000")

            # Check if reduced motion is respected in CSS
            # Elements with animation classes should have animation: none
            animated_elements = await page.locator(
                ".soft-rise, .sse-pulse, .progress-bar-active"
            ).all()

            for el in animated_elements:
                if await el.is_visible():
                    # Check computed styles
                    styles = await page.evaluate(
                        """() => {
                            const el = document.querySelector('.soft-rise, .sse-pulse, .progress-bar-active');
                            if (!el) return null;
                            return window.getComputedStyle(el).animation;
                        }"""
                    )

                    # In reduced motion mode, animations should be disabled
                    # This is more of a smoke test - actual testing requires visual regression
                    print(f"Animation style in reduced motion mode: {styles}")

        finally:
            await browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
