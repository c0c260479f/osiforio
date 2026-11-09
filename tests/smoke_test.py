"""Phone-width smoke test for 追いつきリスト.

Run from the repository root:
    pip install playwright && python -m playwright install chromium
    python tests/smoke_test.py
"""
import base64
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

        check("no in-app notice in a usual browser", page.locator(".in-app").count() == 0)
        page.click(".list-card")
        check("next is the first item", "はじまりの一番星" in page.inner_text(".next"))
        steps = page.locator(".step-title").all_inner_texts()
        check("sample shows the three steps", len(steps) == 3 and "まずこの1つ" in steps[0]
              and "ここまで見れば話がわかる" in steps[1] and "もっと知りたくなったら" in steps[2], " / ".join(steps))
        check("goal note after step 2", page.locator(".step").nth(1).locator(".step-goal").count() == 1)
        check("link shows its site", page.locator(".items .host").first.text_content() == "example.com",
              page.locator(".items .host").first.text_content())
        check("next shows its site", "example.com" in page.inner_text(".next"))
        check("version shown", "2026.11.05版" in page.inner_text(".meta"), page.inner_text(".meta"))
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

        spoiler = page.locator(".item", has_text="第2章「すれ違い」")
        spoiler.locator("summary").click()
        check("spoiler note hidden", "隠しています" in spoiler.inner_text())
        check("glossary entry locked", "チェックすると表示" in page.inner_text(".terms"))
        page.screenshot(path=str(SHOTS / "list.png"), full_page=True)
        sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check("no sideways scroll on the list", sw <= cw, f"{sw} > {cw}")

        # share link
        page.click("[data-action=open-share]")
        page.wait_for_selector("#share-url", timeout=5000)
        link = page.input_value("#share-url")
        check("share link has the list", "#list=z" in link or "#list=j" in link, link[:60])
        check("share link opens outside LINE", "?openExternalBrowser=1#list=" in link, link[:80])
        page.click(".sheet [data-action=close-modal]")

        # opening the link on another phone shows the list, ready to save
        other = browser.new_context(**phone)
        p2 = other.new_page()
        watch(p2, "other: ")
        p2.goto(link)
        p2.wait_for_selector(".preview", timeout=5000)
        check("link opens a preview", "ほしぞら組" in p2.inner_text(".preview"))
        check("link is removed from the address", "#list=" not in p2.url and "openExternalBrowser" not in p2.url, p2.url)
        p2.click("[data-action=save-import]")
        check("saved on the other phone", "0 / 10" in p2.inner_text(".count"), p2.inner_text(".count"))
        p2.screenshot(path=str(SHOTS / "opened-from-link.png"))

        # edit keeps checks
        page.click("[data-action=edit-list]")
        check("editor keeps the step break", page.input_value("#f-goal") == "s06", page.input_value("#f-goal"))
        rules = page.inner_text("#edit-rules")
        check("editor lists what not to write", "歌詞" in rules and "攻略" in rules and "ネタバレ" in rules)
        check("no switch to drop the 非公式 label", page.locator("#f-unofficial").count() == 0)
        heads = page.locator(".edit-step").all_inner_texts()
        check("editor shows the three steps among the items", len(heads) == 3 and "まずこの1つ" in heads[0]
              and "ここまで見れば話がわかる" in heads[1] and "もっと知りたくなったら" in heads[2], " / ".join(heads))
        page.screenshot(path=str(SHOTS / "edit-steps.png"), full_page=True)
        page.click("[data-action=add-item]")
        page.locator("input[id^=title-]").last.fill("3rdライブ「彗星」")
        sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check("no sideways scroll in the editor", sw <= cw, f"{sw} > {cw}")
        page.locator("[data-action=save-edit]").first.click()
        check("item added, checks kept", "2 / 11" in page.inner_text(".count"), page.inner_text(".count"))
        check("steps kept after editing", page.locator(".step").count() == 3)
        today = page.evaluate("(() => { const d = new Date(); return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`; })()")
        check("saving updates the version", f"{today}版" in page.inner_text(".meta"), page.inner_text(".meta"))

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
        report = page.inner_text("#bulk-report")
        check("paste report names the fixed line", "4件足しました" in report and "4行目" in report
              and "日付" in report and "URL" in report, report[:160])
        page.locator("[data-action=save-edit]").first.click()
        check("new list saved", "テスト用リスト" in page.inner_text("h1"))
        check("unsafe link dropped", page.locator(".items a[href^='javascript']").count() == 0)
        check("saved list is marked 非公式", "非公式" in page.inner_text(".meta"), page.inner_text(".meta"))

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

        # reaching the break says the rest is optional
        p5 = browser.new_context(**phone).new_page()
        watch(p5, "goal: ")
        p5.goto(url)
        p5.click(".list-card")
        for _ in range(5):
            p5.click("[data-action=check-next]")
            p5.wait_for_timeout(80)
        check("goal reached message", "ここまでで話がわかります" in p5.inner_text(".next"), p5.inner_text(".next")[:60])
        p5.screenshot(path=str(SHOTS / "goal-reached.png"), full_page=True)

        # an older copy of the sample gets the steps, and its checks stay
        p6 = browser.new_context(**phone).new_page()
        watch(p6, "upgrade: ")
        p6.goto(url)
        p6.click(".list-card")
        p6.click("[data-action=check-next]")  # saves the state once
        p6.evaluate("""() => {
            const st = JSON.parse(localStorage.getItem('oikake-list:v1'));
            delete st.lists['sample-hoshizora'].goal;
            localStorage.setItem('oikake-list:v1', JSON.stringify(st));
        }""")
        p6.goto(url)
        p6.click(".list-card")
        check("old sample gets the steps", p6.locator(".step").count() == 3)
        check("old sample keeps checks", "1 / 10" in p6.inner_text(".count"), p6.inner_text(".count"))

        # opened inside LINE's own browser: tell the viewer to switch
        line = browser.new_context(**phone, user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari Line/14.2.0")
        p7 = line.new_page()
        watch(p7, "line: ")
        p7.goto(link)
        p7.wait_for_selector(".preview", timeout=5000)
        check("in-app browser notice", p7.locator(".sheet .in-app").count() == 1)

        # pasting from an article: numbers and bullets go, a URL and a date are read anywhere, commas stay in titles
        p8 = browser.new_context(**phone).new_page()
        watch(p8, "paste: ")
        p8.goto(url)
        p8.click("[data-action=new-list]")
        p8.fill("#f-title", "貼り付けのテスト")
        p8.fill("#bulk-text", "1. Hello, world 2024年5月16日 https://example.com/b\n"
                              "・２ndライブ（夜） ２０２４／５／１６\n2024年5月16日の生配信\n曲,,\nRe:ステージ 2024-02-31")
        p8.click("[data-action=bulk-add]")
        values = lambda sel: p8.locator(sel).evaluate_all("els => els.map(e => e.value)")
        titles8, dates8, urls8 = values("input[id^=title-]"), values("input[id^=date-]"), values("input[id^=url-]")
        check("paste keeps commas and drops numbers",
              titles8 == ["Hello, world", "２ndライブ（夜）", "2024年5月16日の生配信", "Re:ステージ"], " / ".join(titles8))
        check("paste reads dates anywhere, only real days", dates8 == ["2024-05-16", "2024-05-16", "", ""], " / ".join(dates8))
        check("paste reads a URL anywhere", urls8[:1] == ["https://example.com/b"], " / ".join(urls8))
        report8 = p8.inner_text("#bulk-report")
        check("paste report lists skipped and fixed lines", "4行目" in report8 and "5行目" in report8, report8[:160])
        p8.screenshot(path=str(SHOTS / "edit-paste.png"), full_page=True)

        # the break can be set on an item, and the step headings follow it
        p8.locator("[data-action=set-goal]").nth(2).click()
        check("ここで区切る sets the break", p8.input_value("#f-goal") != "" and p8.locator(".edit-card.is-goal").count() == 1,
              p8.input_value("#f-goal"))
        check("steps follow the break", p8.locator(".edit-step").count() == 3)

        # a wrong URL is marked on its field, and the error message jumps to it
        p8.locator("input[id^=url-]").first.fill("abc")
        p8.locator("[data-action=save-edit]").first.click()
        check("wrong URL is marked", p8.locator("input[aria-invalid=true]").count() == 1)
        p8.click(".err-link")
        marked = p8.locator("input[aria-invalid=true]").first.get_attribute("id")
        check("error jumps to its field", p8.evaluate("document.activeElement.id") == marked, marked)

        # a list that calls itself official is still shown as 非公式
        claim = json.dumps({"format": "oikake-list", "version": 1, "id": "claims-official", "title": "公式を名乗るリスト",
                            "unofficial": False, "types": [{"id": "song", "label": "曲"}],
                            "items": [{"id": "x1", "type": "song", "title": "一曲目"}],
                            "routes": [{"id": "main", "label": "作者のおすすめ順", "order": ["x1"]}]}, ensure_ascii=False)
        code = "j" + base64.urlsafe_b64encode(claim.encode()).decode().rstrip("=")
        p9 = browser.new_context(**phone).new_page()
        watch(p9, "official: ")
        p9.goto(url + "#list=" + code)
        p9.wait_for_selector(".preview", timeout=5000)
        p9.click("[data-action=save-import]")
        check("a list cannot drop the 非公式 label", "非公式" in p9.inner_text(".meta"), p9.inner_text(".meta"))

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
