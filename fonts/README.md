# フォント

ロゴと数字のフォントは、このサイトに置いています。外部のサーバー（Google Fontsなど）には接続しません。本文は、端末に入っているフォント（iPhoneならヒラギノ、AndroidならNoto）で表示します。

| ファイル | フォント | 使うところ | 出どころ |
| --- | --- | --- | --- |
| `dela-gothic-one-subset.woff2` | Dela Gothic One | ロゴ「追いつきリスト」と、メーターの大きな%の数字 | [google/fonts](https://github.com/google/fonts/tree/main/ofl/delagothicone) の `DelaGothicOne-Regular.ttf` から、`display-text.txt` の文字だけを残したもの |
| `IBMPlexMono-Medium-Latin1.woff2` | IBM Plex Mono（Medium） | 番号・日付・件数・リンク先のサイト名 | IBMの公式パッケージ `@ibm/plex-mono` 2.5.0 の `fonts/split/woff2/` にあるファイル。手を加えずにそのまま置いている |

## ライセンス

どちらも SIL Open Font License 1.1 です。フォントのファイルは、このライセンスで配布します（アプリの他のファイルとは別です）。

- Dela Gothic One：`OFL-DelaGothicOne.txt`（Copyright 2020 The Dela Gothic Project Authors）。予約フォント名はないので、文字を絞ったものも同じ名前のままにしています
- IBM Plex Mono：`OFL-IBMPlexMono.txt`（Copyright © 2017 IBM Corp. with Reserved Font Name "Plex"）。予約フォント名があるので、IBMが配っているファイルを手を加えずに使っています。作り直したり文字を絞ったりするときは、名前を変える必要があります

## ロゴの文字を変えるとき

Dela Gothic One には `display-text.txt` の文字しか入っていません。ロゴの文字を変えたときや、ほかの文字をこのフォントで表示するときは、`display-text.txt` に文字を足して作り直します。

```
pip install fonttools brotli
python3 tools/subset_display_font.py path/to/DelaGothicOne-Regular.ttf
```

`tests/smoke_test.py` は、このフォントで表示している文字が `display-text.txt` にない場合に失敗します。
