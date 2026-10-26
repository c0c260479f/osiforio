"""Phone-width smoke test for 追いつきリスト.

Run from the repository root:
    pip install playwright && python -m playwright install chromium
    python tests/smoke_test.py
"""
import functools
import http.server
import json
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "screenshots"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/index.html"


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def main():
    httpd, url = serve()
    SHOTS.mkdir(parents=True, exist_ok=True)
    errors = []

    def watch(page, tag=""):
        page.on("pageerror", lambda e: errors.append(f"{tag}{e}"))
        page.on("console", lambda m: errors.append(f"{tag}{m.text}")
                if m.type == "error" and "Failed to load resource" not in m.text else None)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        phone = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        ctx = browser.new_context(**phone, permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        watch(page)
        page.goto(url)
        page.wait_for_timeout(300)
        page.screenshot(path=str(SHOTS / "home.png"), full_page=True)
        check("home shows the sample list", page.locator(".list-card").count() == 1)

        page.click(".list-card")
        check("next is the first item", "はじまりの一番星" in page.inner_text(".next"))
        page.click("[data-action=check-next]")
        page.wait_for_timeout(150)
        check("meter moves to 10%", page.inner_text(".pct").startswith("10"), page.inner_text(".pct"))
        check("next moves on", "第1章" in page.inner_text(".next-title"), page.inner_text(".next-title"))
        page.locator(".item .check").nth(2).click()
        check("two items checked", "2 / 10" in page.inner_text(".count"), page.inner_text(".count"))

        page.click("button.chip:has-text('ライブから')")
        check("entry filter", "1stライブ" in page.inner_text(".next-title"), page.inner_text(".next-title"))
        page.click("button.chip:has-text('すべて')")
        page.click(".seg-ctl button:has-text('公開順')")
        titles = page.locator(".item .item-title").all_inner_texts()
        check("release order", titles.index("ラジオ 第1回") < titles.index("1stライブ「ファーストライト」"))
        page.click(".seg-ctl button:has-text('作者のおすすめ順')")

        page.locator(".item summary").nth(5).click()
        check("spoiler note hidden", "隠しています" in page.locator(".item").nth(5).inner_text())
        check("glossary entry locked", "チェックすると表示" in page.inner_text(".terms"))
        page.screenshot(path=str(SHOTS / "list.png"), full_page=True)
        sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check("no sideways scroll on the list", sw <= cw, f"{sw} > {cw}")

        # share link
        page.click("[data-action=open-share]")
        page.wait_for_selector("#share-url", timeout=5000)
        link = page.input_value("#share-url")
        check("share link has the list", "#list=z" in link or "#list=j" in link, link[:60])
        page.click(".sheet [data-action=close-modal]")

        # opening the link on another phone shows the list, ready to save
        other = browser.new_context(**phone)
        p2 = other.new_page()
        watch(p2, "other: ")
        p2.goto(link)
        p2.wait_for_selector(".preview", timeout=5000)
        check("link opens a preview", "ほしぞら組" in p2.inner_text(".preview"))
        check("link is removed from the address", "#list=" not in p2.url)
        p2.click("[data-action=save-import]")
        check("saved on the other phone", "0 / 10" in p2.inner_text(".count"), p2.inner_text(".count"))
        p2.screenshot(path=str(SHOTS / "opened-from-link.png"))

        # edit keeps checks
        page.click("[data-action=edit-list]")
        page.click("[data-action=add-item]")
        page.locator("input[id^=title-]").last.fill("3rdライブ「彗星」")
        sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check("no sideways scroll in the editor", sw <= cw, f"{sw} > {cw}")
        page.locator("[data-action=save-edit]").first.click()
        check("item added, checks kept", "2 / 11" in page.inner_text(".count"), page.inner_text(".count"))

        # pasting the old link updates the list and keeps checks
        page.click("[data-action=go-home]")
        page.click("[data-action=open-import]")
        page.fill("#import-text", link)
        page.click("[data-action=do-import]")
        page.wait_for_selector(".preview", timeout=5000)
        check("update offered", "更新" in page.inner_text(".sheet"))
        page.click("[data-action=save-import]")
        check("update kept checks", "2 / 10" in page.inner_text(".count"), page.inner_text(".count"))

        page.click("[data-action=go-home]")
        page.click("[data-action=open-import]")
        page.fill("#import-text", "https://example.com/#list=zzz")
        page.click("[data-action=do-import]")
        page.wait_for_timeout(200)
        check("broken link explained", page.locator(".sheet .errors").count() == 1)
        page.click(".sheet [data-action=close-modal]")

        # new list from pasted lines
        page.click("[data-action=new-list]")
        page.fill("#f-title", "テスト用リスト")
        page.fill("#bulk-text", "曲,一曲目,2024/5/16,https://example.com/a\nライブ,ライブ1\nタイトルだけ\nラジオ,番組,2024-13-40,javascript:alert(1)")
        page.click("[data-action=bulk-add]")
        check("pasted lines become items", page.locator("input[id^=title-]").count() == 4)
        page.locator("[data-action=save-edit]").first.click()
        check("new list saved", "テスト用リスト" in page.inner_text("h1"))
        check("unsafe link dropped", page.locator(".items a[href^='javascript']").count() == 0)

        # backup round trip
        page.click("[data-action=go-home]")
        page.click("[data-action=open-backup]")
        check("file save offered", page.locator("[data-action=download-backup]").count() == 1)
        backup = page.input_value("#backup-out")
        check("backup has both lists", len(json.loads(backup)["lists"]) == 2)
        third = browser.new_context(**phone)
        p3 = third.new_page()
        watch(p3, "restore: ")
        p3.goto(url)
        p3.click("[data-action=open-backup]")
        p3.fill("#backup-in", backup)
        p3.click("[data-action=restore]")
        check("backup restored", p3.locator(".list-card").count() == 2)

        page.reload()
        check("lists survive a reload", page.locator(".list-card").count() == 2)

        dark = browser.new_context(**phone, color_scheme="dark")
        p4 = dark.new_page()
        p4.goto(url)
        p4.click(".list-card")
        p4.screenshot(path=str(SHOTS / "list-dark.png"))

        check("no script errors", not errors, "; ".join(errors[:5]))
        browser.close()
    httpd.shutdown()

    failed = [r for r in results if not r[1]]
    for name, passed, detail in results:
        print(("PASS " if passed else "FAIL ") + name + (f"  [{detail}]" if detail and not passed else ""))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
