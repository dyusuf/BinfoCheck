# T06 bounded live capture — 19 September 2026

**Capture passed; usable-corpus acceptance remains blocked by the site parser profile.**

The user authorized one robots GET plus up to five allowlisted page GETs under
policy SHA-256 `78de13b54502cf2c8395d9be1301f66c74bbe0d8b8cf5a931f58e71c1aad5d18`.
This allowance was consumed once: **6 GETs, all complete HTTP 200; zero retries,
redirects, assets, model/provider calls, or paid API usage (USD 0).**
No further request is authorized by that consumed allowance. Infrastructure cost is not measured.

Capture code: `ab202a682350fda19f27ae36755b9a8365d1cf65` (exact-head hosted CI green).
Batch: `t06-live-20260919T114133Z`.
Private T11A store: `/tmp/binfocheck-t06-live-20260919T114133Z` (directory mode 0700).
This is a local `/tmp` store, not an off-machine backup; retain it for the next offline step.
Raw captures are restricted artifacts outside Git. Supplementary private files include
`live-audit.json`, `replay-request.json`, and page HTML/tree inspection copies.

Authorization artifact: `t06-live-20260919T114133Z.authorization.v1`.
It preserves the explicit user-message reference, batch, approved digest, robots URL,
ordered page URLs and complete FetchPolicy, and is linked from the capture-start marker.
The envelope was validated and persisted/read back before that marker and dispatch.
The completion dependency graph includes it; offline reopen/load verified it.

## Actual responses

| Page | UTC start → finish | HTTP | Complete body bytes | SHA-256 of body bytes |
|---|---|---|---|---|
| Robots | 2026-09-19T11:42:05.340908Z → 2026-09-19T11:42:05.433204Z | 200 | 1049 | `b9b1b507f5da47e711f368b78ebf04fffd8e94997109646adc7624792c5ba227` |
| Driving | 2026-09-19T11:42:07.341070Z → 2026-09-19T11:42:07.765643Z | 200 | 150189 | `3f60f20f4c6ea60c422ef0d4f084bf1a7ce25b2ef9e4c99e8c85c05a56a28d99` |
| Ramadan | 2026-09-19T11:42:09.341211Z → 2026-09-19T11:42:09.849305Z | 200 | 148668 | `8730ea878ffba196a129c7feb6728ed92531b48a272ec01e9c98ffb37a331afd` |
| Travel | 2026-09-19T11:42:11.341313Z → 2026-09-19T11:42:11.855425Z | 200 | 164899 | `e697d33561df1f21c894c9d1469e0587a340f2f39771f994ee7796869644b7a1` |
| Risk-test FAQ | 2026-09-19T11:42:13.341412Z → 2026-09-19T11:42:13.822577Z | 200 | 208412 | `e5e4d4e6958ff38b4a528d68686a3e81cacc025c5f740a1cb4ddfc3e24092c62` |
| Motivation | 2026-09-19T11:42:15.341537Z → 2026-09-19T11:42:18.201049Z | 200 | 157321 | `9b85cee3e71ee696a667dd23dcb81a708201b567d6f9503ccf087b16328c97f6` |

Minimum observed interval between request starts: `2.000099 s`.
Robots returned UTF-8 text allowing these exact paths; no applicable longer crawl delay
or rate was declared. Every page returned UTF-8 HTML. Raw artifacts preserve complete
content-decoded bytes before charset decoding; all content hashes were verified.

## Snapshot identities

- **Robots** — https://www.diabinfo.de/robots.txt
  Receipt: `corpus-receipt-520c8faf33eb7e1741811d30c1497eb9d136b0df9d579628e94a40c504f24fd2`.
  Body artifact: `corpus-robots-body-192361076cb2a96cc2bedf1e14ef1223c2be1280e9f2bbe1f9e37e331c960ab1`.
- **Driving** — https://www.diabinfo.de/leben/diabetes-im-alltag/strassenverkehr.html
  Receipt: `corpus-receipt-763a7b841efe034c454bea103edd1efe98b2cc5fa131ee9120ad25411ee64c19`.
  Body artifact: `corpus-raw-html-b88fee4b5e77adbdb5abf43524b30e4fb892ef181f1cb18aa79c5c9e90b32e58`.
- **Ramadan** — https://www.diabinfo.de/leben/diabetes-im-alltag/ramadan.html
  Receipt: `corpus-receipt-abb2a865088b99cc804407db03a7403fbf9a4874fd3351780f0acbf17d45277f`.
  Body artifact: `corpus-raw-html-b20f8e3b1f9ab0f136d75089f503ec43eb717090a9b7e93a2652aa164cda39d2`.
- **Travel** — https://www.diabinfo.de/leben/diabetes-im-alltag/reisen.html
  Receipt: `corpus-receipt-26ba8e7807830394dec227f103bf7c63e61a4ffd38fa0d06e4745a9c0d7eb896`.
  Body artifact: `corpus-raw-html-50e27792b20ab24cd0e9f4bd68684187efe86308c81d554674000a9abdaad0a3`.
- **Risk-test FAQ** — https://www.diabinfo.de/vorbeugen/diabetes/wie-hoch-ist-mein-risiko-fuer-diabetes-typ-2/haeufig-gestellte-fragen.html
  Receipt: `corpus-receipt-54d86703ab6eb3c7430563895a43a5bf07151cef635d3f9d477f0d2720a89d13`.
  Body artifact: `corpus-raw-html-252cad6f5db2f7a5b8eff062a091c652e38e3721df3320ac84b89a603d9b6e27`.
- **Motivation** — https://www.diabinfo.de/vorbeugen/was-kann-ich-tun/so-erreichen-sie-ihre-ziele.html
  Receipt: `corpus-receipt-fd2f5693aeac93a7d807246e5a1df52244079aa2288efa2b77cbcf35f10d3594`.
  Body artifact: `corpus-raw-html-c37f0ac65e03161451e1116793642b06f68e3e82855a1c754f811428f8e643cb`.

## Offline replay and remaining gate

All five pages have zero `<article>` elements. The inspected title/content container
is `main#main > .container`; it also contains chrome, TOC, related links and images.
The FAQ additionally uses `button.accordion-headline`. These are observations from
saved HTML, not a validated replacement extraction profile.

Default-profile replay records all five as **unusable**, reason
`ambiguous_article_root` (the existing zero-or-multiple-root error). Manifest
`corpus-manifest-9b2788ec22042b1bdb1c0a93d3b8432348d61635f474d7c1d5b8e78fad415e6c` is **failed**, with **0 passages**.
HTTP capture success is distinct from corpus readiness. Complete raw HTML and decoded
raw TextRecords are retained despite the extraction failure; no source was overwritten.

- Driving: `corpus-article-e590d6aa7bd9534217ecc31acfd9b9ecf9f2d3a475e0c47a1356d735a1594d3b`; raw text `corpus-raw-text-aca197e1cf4a01e042547d734632975d794736558978afcff80347ae32d719a0`.
- Ramadan: `corpus-article-8aab24eb5f3b55d2213d9550782f5e7b7073ac338c42c76934cb76cd0a28a8e7`; raw text `corpus-raw-text-f83dd0753620bbc2fc4d3b84f356ed3a717535096eb67be8a2f5269f8ee34243`.
- Travel: `corpus-article-a0b260fb6cdf9d7ff2ce1ef69dfb28f743d9557b182c1e04fe3413863b62beb5`; raw text `corpus-raw-text-5df6e633623591daa8d744e5f92eaa818d19a410ee64b74a60f9bdcd213442b9`.
- Risk-test FAQ: `corpus-article-f0e086c38541ac41ec9f74d6ec16691b00e5edeaf19f8b2582c8078bc29a8acf`; raw text `corpus-raw-text-b9cc011b8dcbc840a4d8d5f63aec8b32c064d75cd603d7a46ab08ca792ca0caa`.
- Motivation: `corpus-article-8aed706a5fd3427ca9845dd4e5d5d8cc23923a76c352fead4e6525b199b60c21`; raw text `corpus-raw-text-bb190c0d7719d3ee3ed960658b62a62d9d6174c9792bdd96b45607e7467df129`.

Fresh-process replay used socket construction, DNS and connection blockers.
Store reopen/load and repeat ingestion returned identical records and manifest.
Authorization linkage, artifact hashes, all six receipt counts/statuses, and minimum
spacing were checked. No live calls occurred during inspection or replay.
An initial inspection script had an import-incompatible socket stub; it failed before
reading pages and was corrected to a socket subclass. The successful offline runs
above used the corrected blocker. The capture was never rerun.

Next work is offline: define and test the narrowly scoped site profile from these
saved bodies, distinguish article content/references from chrome/media, preserve FAQ
headings, then inspect all five cleaned articles and exact spans. Append new parser
versions with these failed versions as predecessors; do not overwrite or refetch.
T06 is not accepted. T07, retrieval, models, PDF/video fetching and corpus expansion
remain outside scope. No shared schema, dependency, parser or transport code changed
during this capture gate. No deployment or PR merge occurred.

## Delivery checks

Latest `origin/main` remained `80b35c95daaf06bfe9149551068d609e39d4ab58`,
already included in this branch. Ruff lint/format, schema drift and whitespace
checks passed for this documentation-only delivery. The unchanged capture code's
hosted CI passed with 732 tests; those tests are historical regression evidence,
not proof of real-page extraction. Live inspection/replay results above are the
checks performed for this gate. Full regression tests were not repeated locally
because no runtime code, dependency or synthetic fixture changed.
