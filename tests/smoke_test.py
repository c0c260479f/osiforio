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


# the offline copy made by sw.js holds the app.
# The app registers sw.js only over https, so the test registers it itself (127.0.0.1 counts as secure).
SW_APP_JS = """async () => {
  const timeout = new Promise(r => setTimeout(() => r('timeout'), 5000));
  const work = (async () => {
    await navigator.serviceWorker.register('sw.js');
    await navigator.serviceWorker.ready;
    const key = (await caches.keys()).find(k => k.startsWith('oikake-list'));
    if (!key) return 'no cache';
    const c = await caches.open(key);
    const a = await c.match('index.html');
    const b = await c.match('icons/icon-192.png');
    return !!(a && b);
  })();
  return Promise.race([work, timeout]);
}"""

# WCAG contrast between an element's text and the first solid background behind it
CONTRAST_JS = r"""sel => {
  const el = document.querySelector(sel);
  if (!el) return 0;
  const rgb = s => (s.match(/[\d.]+/g) || []).map(Number);
  let node = el, bg = null;
  while (node) {
    const c = rgb(getComputedStyle(node).backgroundColor);
    if (c.length === 3 || (c.length === 4 && c[3] > 0)) { bg = c; break; }
    node = node.parentElement;
  }
  bg = bg || [255, 255, 255];
  const lum = c => {
    const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const a = lum(rgb(getComputedStyle(el).color)), b = lum(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}"""
STYLE_JS = "sel => (document.querySelector(sel) || {getAttribute: () => ''}).getAttribute('style') || ''"
SAMPLE_COLOR = "#3cc4f0"


def list_json(**extra):
    """A one-item list, as a share link's plain JSON (j) code."""
    data = {"format": "oikake-list", "version": 1, "id": "x-list", "title": "テスト用の共有リスト",
            "types": [{"id": "song", "label": "曲"}], "items": [{"id": "x1", "type": "song", "title": "一曲目"}],
            "routes": [{"id": "main", "label": "作者のおすすめ順", "order": ["x1"]}]}
    data.update(extra)
    return "j" + base64.urlsafe_b64encode(json.dumps(data, ensure_ascii=False).encode()).decode().rstrip("=")


def main():
    httpd, url = serve()
    SHOTS.mkdir(parents=True, exist_ok=True)
    errors = []
    requests = []

    def watch(page, tag=""):
        page.on("pageerror", lambda e: errors.append(f"{tag}{e}"))
        page.on("console", lambda m: errors.append(f"{tag}{m.text}")
                if m.type == "error" and "Failed to load resource" not in m.text else None)
        page.on("request", lambda r: requests.append((r.method, r.url, r.post_data)))

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
        check("home card counts toward the break", "あと5つ" in page.inner_text(".list-card .lc-pct"),
              page.inner_text(".list-card .lc-pct"))

        # only the phone's own fonts; the app's own screens stay plain, and a list's card shows its 推しカラー
        check("no web fonts", page.evaluate("document.fonts.size") == 0, str(page.evaluate("document.fonts.size")))
        home_btn = page.evaluate("getComputedStyle(document.querySelector('.btn.primary')).backgroundColor")
        check("app buttons stay plain", home_btn == "rgb(27, 30, 45)", home_btn)
        check("list card shows its 推しカラー", SAMPLE_COLOR in page.evaluate(STYLE_JS, ".list-card"))

        check("no in-app notice in a usual browser", page.locator(".in-app").count() == 0)
        page.click(".list-card")
        check("next is the first item", "はじまりの一番星" in page.inner_text(".next"))
        steps = page.locator(".step-title").all_inner_texts()
        check("sample shows the three steps", len(steps) == 3 and "まずこの1つ" in steps[0]
              and "ここまで見れば話がわかる" in steps[1] and "もっと知りたくなったら" in steps[2], " / ".join(steps))
        check("goal note after step 2", page.locator(".step").nth(1).locator(".step-goal").count() == 1)
        # not homework: the meter counts only up to the break, and 「もっと知りたくなったら」 starts folded
        meter = page.inner_text("[aria-label=追いつき度]")
        check("meter starts at the break", "話がわかるまで" in meter and "あと5つ" in page.inner_text(".pct"), meter[:40])
        rest = page.locator(".step").nth(2)
        check("the rest starts folded", rest.locator(".item").count() == 0 and "ほかの5項目を見る" in rest.inner_text(),
              rest.inner_text()[:80])
        check("link shows its site", page.locator(".items .host").first.text_content() == "example.com",
              page.locator(".items .host").first.text_content())
        check("next shows its site", "example.com" in page.inner_text(".next"))
        check("version shown", "2026.11.12版" in page.inner_text(".meta"), page.inner_text(".meta"))
        page.click("[data-action=check-next]")
        page.wait_for_timeout(150)
        check("meter counts toward the break", "あと4つ" in page.inner_text(".pct"), page.inner_text(".pct"))
        seg = page.evaluate("getComputedStyle(document.querySelector('.seg.on')).backgroundColor")
        check("sample list is shown in its 推しカラー", seg == "rgb(60, 196, 240)", seg)
        pct_ratio = page.evaluate(CONTRAST_JS, ".pct")
        check("the light-blue number still reads", pct_ratio >= 4.5, f"{pct_ratio:.2f}")
        check("next moves on", "第1章" in page.inner_text(".next-title"), page.inner_text(".next-title"))
        page.locator(".item .check").nth(2).click()
        check("two items checked", "2 / 5" in page.inner_text(".count"), page.inner_text(".count"))

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
        check("saved on the other phone", "0 / 5" in p2.inner_text(".count"), p2.inner_text(".count"))
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
        check("item added, checks kept", "2 / 5" in page.inner_text(".count")
              and "ほかの6項目を見る" in page.locator(".step").nth(2).inner_text(), page.inner_text(".count"))
        check("steps kept after editing", page.locator(".step").count() == 3)
        if page.locator("[data-action=show-rest]").count():
            page.click("[data-action=show-rest]")
        check("opening shows the rest", page.locator(".step").nth(2).locator(".item").count() == 6)
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
        check("update kept checks", "2 / 5" in page.inner_text(".count"), page.inner_text(".count"))

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
        check("the rest opens at the break", p5.locator(".step").nth(2).locator(".item").count() == 5)
        meter5 = p5.inner_text("[aria-label=追いつき度]")
        check("meter shows the whole list after the break", "追いつきました" in meter5 and "リスト全体 5 / 10" in meter5
              and p5.inner_text(".pct").startswith("50"), meter5[:80])
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
        check("old sample keeps checks", "1 / 5" in p6.inner_text(".count"), p6.inner_text(".count"))
        # the unedited sample from 11/5 (before 推しカラー) is replaced too
        p6.evaluate("""() => {
            const st = JSON.parse(localStorage.getItem('oikake-list:v1'));
            const s = st.lists['sample-hoshizora'];
            s.goal = 's06'; s.updatedAt = '2026-11-05'; delete s.color;
            localStorage.setItem('oikake-list:v1', JSON.stringify(st));
        }""")
        p6.goto(url)
        check("the 11/5 sample gets its 推しカラー", SAMPLE_COLOR in p6.evaluate(STYLE_JS, ".list-card"))

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

        # 推しカラー: every color reads at 4.5:1 (text, gray notes, buttons, the break note), in light and dark
        for scheme in ("light", "dark"):
            pc = browser.new_context(**phone, color_scheme=scheme).new_page()
            watch(pc, f"color-{scheme}: ")
            pc.goto(url)
            pc.click(".list-card")
            pc.click("[data-action=edit-list]")
            swatches = pc.locator(".swatch:not(.none)")
            low = []
            for sw in swatches.all():
                hex_, name = sw.get_attribute("data-color"), sw.get_attribute("aria-label")
                sw.click()
                if hex_ not in pc.evaluate(STYLE_JS, "#app"):
                    low.append(f"{name}: not applied")
                for sel in ("#color-preview .eyebrow", "#color-preview .next-title", "#color-preview .next-sub",
                            ".wrap .btn.primary", ".edit-goal-note"):
                    ratio = pc.evaluate(CONTRAST_JS, sel)
                    if ratio < 4.5:
                        low.append(f"{name} {sel} {ratio:.2f}")
            check(f"every 推しカラー reads ({scheme})", swatches.count() == 10 and not low, "; ".join(low[:4]))
            pc.locator(".swatch[aria-label='黄']").click()
            pc.locator("#color-preview").scroll_into_view_if_needed()
            pc.screenshot(path=str(SHOTS / f"edit-color-{scheme}.png"))

        # a chosen color is saved with the list and travels in the share link
        pk = browser.new_context(**phone).new_page()
        watch(pk, "color-share: ")
        pk.goto(url)
        pk.click(".list-card")
        pk.click("[data-action=edit-list]")
        pk.click(".swatch[aria-label='黄']")
        pk.locator("[data-action=save-edit]").first.click()
        btn_ratio = pk.evaluate(CONTRAST_JS, ".next .btn.primary")
        check("saved list takes the new 推しカラー", "#ffd21f" in pk.evaluate(STYLE_JS, "#app") and btn_ratio >= 4.5,
              f"{btn_ratio:.2f}")
        pk.screenshot(path=str(SHOTS / "list-yellow.png"), full_page=True)
        pk.click("[data-action=open-share]")
        pk.wait_for_selector("#share-url", timeout=5000)
        shared = pk.input_value("#share-url")
        pr = browser.new_context(**phone).new_page()
        watch(pr, "color-receive: ")
        pr.goto(shared)
        pr.wait_for_selector(".preview", timeout=5000)
        in_sheet = "#ffd21f" in pr.evaluate(STYLE_JS, ".sheet")
        pr.click("[data-action=save-import]")
        check("the share link carries the 推しカラー", in_sheet and "#ffd21f" in pr.evaluate(STYLE_JS, "#app"))

        # a color that is not #rrggbb is dropped, so nothing else reaches the style attribute
        pb = browser.new_context(**phone).new_page()
        watch(pb, "bad-color: ")
        pb.goto(url + "#list=" + list_json(color="red;background:url(https://example.com/x.png)"))
        pb.wait_for_selector(".preview", timeout=5000)
        sheet_style = pb.evaluate(STYLE_JS, ".sheet")
        pb.click("[data-action=save-import]")
        check("a strange 推しカラー is dropped", not sheet_style and not pb.evaluate(STYLE_JS, "#app"),
              sheet_style or pb.evaluate(STYLE_JS, "#app"))

        # a long list without a break shows only its first 3; the rest opens on demand, or after the first 3
        long_items = [{"id": f"y{i}", "type": "song", "title": f"曲{i}"} for i in range(1, 9)]
        long_code = list_json(id="y-list", title="区切りのない長いリスト", items=long_items,
                              routes=[{"id": "main", "label": "作者のおすすめ順", "order": [it["id"] for it in long_items]}])
        pl = browser.new_context(**phone).new_page()
        watch(pl, "long: ")
        pl.goto(url + "#list=" + long_code)
        pl.wait_for_selector(".preview", timeout=5000)
        pl.click("[data-action=save-import]")
        more = pl.locator("[data-action=show-rest]")
        check("a long list shows its first 3", pl.locator(".items .item").count() == 3
              and more.count() == 1 and "ほかの5項目を見る" in more.inner_text())
        if pl.locator("[data-action=show-rest]").count():
            pl.click("[data-action=show-rest]")
        check("the rest opens on demand", pl.locator(".items .item").count() == 8)
        focused = pl.evaluate("document.activeElement.getAttribute('aria-label') || ''")
        check("focus moves to the first new item", focused.startswith("曲4"), focused)
        pl.goto(url)
        pl.click(".list-card:has-text('区切りのない長いリスト')")
        for _ in range(3):
            pl.click("[data-action=check-next]")
            pl.wait_for_timeout(80)
        check("the rest opens after the first 3", pl.locator(".items .item").count() == 8)

        # the offline copy keeps the app (a fresh page, so the service worker changes nothing above)
        p10 = browser.new_context(**phone).new_page()
        watch(p10, "offline: ")
        p10.goto(url)
        cached = p10.evaluate(SW_APP_JS)
        check("offline copy keeps the app", cached is True, str(cached))

        # nothing about the visitor goes to another site: every request stays on the app's own site
        origin = url.rsplit("/", 1)[0] + "/"
        outside = [u for _, u, _ in requests if not u.startswith((origin, "blob:", "data:"))]
        check("the app connects to no other site", requests and not outside, "; ".join(outside[:3]))
        # and nothing is sent to the server: only reads, and the list never leaves the # part of a link
        sent = [f"{m} {u}" for m, u, body in requests if m != "GET" or body or "list=" in u]
        check("the app sends nothing to a server", requests and not sent, "; ".join(sent[:3]))

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
