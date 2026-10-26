# リストのデータの形（version 1）

1つのリストは、次の形のJSONです。共有リンクにも、記録の保存にも、この形がそのまま入ります。

```json
{
  "format": "oikake-list",
  "version": 1,
  "id": "l3k9x0abc",
  "title": "学マス 追いつきリスト",
  "work": "学園アイドルマスター",
  "author": "作者の名前",
  "checkedAt": "2026-10-26",
  "description": "どんな人向けの追い方か",
  "unofficial": true,
  "reportUrl": "https://docs.google.com/forms/d/e/.../viewform?entry.123={title}",
  "links": [
    { "label": "公式サイト", "url": "https://example.com/" }
  ],
  "types": [
    { "id": "song", "label": "曲" },
    { "id": "story", "label": "ストーリー" }
  ],
  "items": [
    {
      "id": "i8f2k1m0q",
      "type": "song",
      "title": "曲名",
      "date": "2024-05-16",
      "url": "https://example.com/song",
      "note": "短い説明（自分の言葉で）",
      "spoiler": false
    }
  ],
  "routes": [
    { "id": "main", "label": "作者のおすすめ順", "order": ["i8f2k1m0q"] }
  ],
  "terms": [
    { "id": "w1", "word": "用語", "note": "用語の説明", "after": "i8f2k1m0q" }
  ]
}
```

## 決まりごと

| 項目 | 決まり |
| --- | --- |
| `id`（リスト・項目） | 一度決めたら変えない。チェックの記録は項目の `id` にひもづくので、タイトルを直してもリストを更新しても記録は消えない |
| `checkedAt` | リストの中身を最後に確かめた日（`YYYY-MM-DD`）。画面に「最終確認」として出る |
| `unofficial` | `true` なら「非公式」の表示を出す。ファンが作るリストは `true` のままにする |
| `reportUrl` | 間違いの報告先。`{title}` は項目のタイトルに置き換わる。空なら報告リンクを出さない |
| `types` | 種類（入り口）。画面の「曲から」「ストーリーから」の絞り込みに使う |
| `items[].url` | 公式ページへのリンク。`https://` か `http://` だけを受け付け、それ以外は読み込み時に捨てる |
| `items[].date` | 公開日（`YYYY-MM-DD`）。わからなければ空でよい |
| `items[].spoiler` | `true` の項目は、チェックするまで説明を隠す |
| `routes` | 並び順。先頭は必ず `main`（作者のおすすめ順）。「公開順」は `date` から自動で作るので入れない |
| `terms[].after` | その項目をチェックするまで、用語の説明を隠す。空ならいつでも表示する |
| 上限 | 項目は1,000件まで。長すぎる文字は読み込み時に切る |

## チェックの記録（端末にだけ保存）

```json
{
  "progress": {
    "l3k9x0abc": {
      "checked": { "i8f2k1m0q": "2026-10-26" },
      "route": "main",
      "filter": "all"
    }
  }
}
```

共有リンクには記録を入れません。記録の保存（コピーやファイル）には、リストと記録の両方が入ります。

## 共有リンク

リストのJSONを `deflate-raw` で圧縮し、URLで使える Base64（`-` と `_` を使う形）にして、先頭に `z` を付けたものを `#list=` のあとに入れます。圧縮が使えないブラウザでは、圧縮せずに先頭へ `j` を付けます。`#` より後ろはサーバーに送られないので、リストの中身がサーバーに残ることはありません。
