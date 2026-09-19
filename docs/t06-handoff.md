# T06 final offline site-profile handoff

**Task / assignee / status:** T06 / Codex / **live_acceptance_blocked**.
Branch: `codex/t06-corpus`. Delivery: draft [PR #7](https://github.com/dyusuf/BinfoCheck/pull/7),
not merged. Reviewed starting head: `7ebc4249bfdae0077639a4e432aa64cd66745e54`.

The saved batch now replays as four usable articles and one unusable article.
**201 passages; incomplete corpus; T06 is not merge-ready.** No refetch, DNS lookup,
HTTP request, provider/model call or package download was made for this adaptation.
The separately requested Git/GitHub synchronization and delivery operations are
not corpus/provider traffic. New capture/provider request count: **0**; paid usage
**USD 0**. Deployed checks: not applicable. T07 was not started.

## Durable private preservation

Before code changes, the closed/quiescent source
`/tmp/binfocheck-t06-live-20260919T114133Z` was copied to:

`/mnt/workspace/BinfoCheck-data/t06-live-20260919T114133Z`

Verified identical file/directory membership, sizes and SHA-256 for **29 files,
2,826,449 bytes**; SQLite integrity check returned `ok`. No journal/WAL or process
holding source-store files was found. Parent and target directories are mode 0700;
all copied files are mode 0600. The source was not modified and its full inventory
was verified again after replay. All original destination payloads remain identical;
only the destination database and newly appended outputs changed. Existing destinations
would have been compared, not overwritten. No store or real HTML is committed.

The durable store contains `acceptance-final/store-preservation.json` (complete
per-file verification), `report.json`, `request.json`, `inspection.json`, four complete
cleaned-text exports, structure companions and the offline verification scripts.
All outputs remain private. This path is the continuing T11A store, not an off-machine
backup. The original failed records and rejected diagnostic outputs are retained.

## Scope, dependencies and versions

D06's site-profile portion is implemented in `corpus/diabinfo.py`, with small
version-selection and heading-scope changes in `config.py` and `parsing.py`.
Synthetic regressions live in `tests/corpus/test_diabinfo.py` and
`tests/fixtures/corpus/diabinfo-v1/`; fixtures are hand-authored, not copied HTML.
Documentation updates cover architecture, task status, capture history and corpus usage.
No T00/domain/storage schema, transport, package or lockfile change.

Pins remain Beautiful Soup **4.15.0**, explicit **html5lib 1.1**, core-only
LlamaIndex **0.14.24**, Python 3.13 and existing locked dependencies. LlamaIndex still
only checks exact passage/node provenance; no models, embeddings, lexical indexes,
retrieval, BM25/RRF, asset fetching, PDF/video extraction or generic readability.
Shared wire schema 1 / validation revision 1.1 and T11A version 1 are unchanged.
Fetch/settings/passage construction versions remain 1.

Current factory: `binfocheck.corpus.diabinfo.pilot_profile()`.
Current profile: **diabinfo-pilot/2**, parser **t06-corpus-parser/3**, SHA-256
`b4cd5fdda187a0da1206547e17416f64eed93a767f8d4a0b5fa32808be13e85e`.

The legacy default `article` profile remains parser version 1 with unchanged hash
`c448c2e55730915600d812dd074b0f0787aae6270de7d06b4cab838a464d3898`.
Its absent site-profile field is excluded from serialization, preserving old replay
identities and completion artifacts. All five original failures remain loadable.

An intermediate **diabinfo-pilot/1 / parser 2** candidate passed text-only checks
but was rejected during the complete media audit: its gallery removal omitted an
informational SVG. Its configuration and semantics remain available solely for
immutable historical replay; it is not the recommended/accepted profile.

## Bounded extraction rules

Four unique, nonoverlapping roots, in document order:

- `main#main > .container > .frame:has(> header > h1)`
- `main#main > .container > .frame.frame-space-before-extra-small`
- `main#main > .container > .frame-type-gddiabinfo_diabinfobackground > .background-container > .frame > .row.grid-container > .col-lg-9`
- `main#main > .container > .frame-type-gddiabinfo_diabinfocolumns > .row.grid-container > .col-lg-9`

These select title, scientific credit, introduction text, and main article text.
They do not select the whole outer container. Outer navigation, cookie/header/footer
material and the main promotional sidebar are outside the roots. New unselected
outer content frames/text fail explicitly instead of silently disappearing.

The TOC must have its exact structural heading, local links and unique existing
article targets; FAQ group labels must correspond to actual headings. Remove only
the validated TOC, templated news modules, credit-only image galleries, podcast icon
and audio-only module, separator rules, empty accordion controls, decorative SVG
chevrons, and the exact hidden email anti-spam marker. Substantive captions,
unknown structures, missing roots/TOC/references, changed rules and broken FAQ
associations fail explicitly. Informational/uncaptioned imagery is not blindly
excluded. The current media guard is limited to the observed pilot structure.

Retain scientific credits, substantive callouts, all paragraphs, nested lists,
editorial further-reading links, source bibliographies/links and update dates.
Source wording, numbers, punctuation, duplicates and apparent typos are preserved;
only established structural whitespace/list markers and the hidden anti-spam
marker change. No link is followed, and no email obfuscation script executes.

FAQ `button.accordion-headline > h2.h3` questions become semantic level-3 headings
under their level-2 topic. Validate one question/answer pair and ARIA references,
including collapsed answers. Callout headings end at their box boundary; questions
end at their accordion-item boundary. This prevents following article paragraphs
from inheriting unrelated callout/question headings. Natural passages remain whole
paragraphs/lists, optionally joining an immediately preceding colon paragraph in
the same section. Every source location uses the original pre-removal DOM locator.

## Five-page complete inspection

Complete diagnostic cleaned text was read for **each** page, from title/scientific
credit through its ending. Every retained text node was independently accounted for
against source DOM blocks after explicit exclusions; non-whitespace character order
and link order/targets match the saved HTML. All heading/block/list/link/passage
spans slice exactly. Block membership and heading paths were checked for every
passage; no passage crosses a heading or unrelated FAQ answer.

| Page | Inspection result | Final passages |
|---|---|---|
| Driving | Six substantive sections, advisory boxes, 29 list items, 18 headings, 14 links; source list/update ending retained. Navigation, TOC and news/sidebar absent. | 41 |
| Ramadan | Full diagnostic text includes six sections, three risk groups with nested lists, qualifiers and references. **Rejected** because the informational SVG cannot be verified from saved HTML; no final cleaned TextRecord/passages. | 0 |
| Travel | Six sections, checklist and direction-specific options, 25 list items, 22 headings, 29 links; sources/update retained. Only podcast promotion/icon omitted, not nearby guidance. | 39 |
| Risk-test FAQ | All **29 questions under four groups**, collapsed answers, 34 headings, 102 links, embedded references and footnotes retained; final answer ending preserved. Empty controls/icons and hidden anti-spam marker excluded. | 97 |
| Motivation | All 13 numbered tips, conclusion, editorial further-reading list and bibliography/update; 51 list items, 18 headings, 14 links. Thirteen decorative credit-only galleries and templated promotions excluded. | 24 |

The FAQ's source repetitions and motivation text's adjacent bold-word spelling are
preserved rather than edited. Media attributes were inspected offline: the Ramadan
image is specifically labeled an infographic, unlike stock photos/podcast icon.
No assumption that all five share the same substantive structure was used.

## Exact immutable lineage and current corpus

Saved batch: `t06-live-20260919T114133Z`.
Final manifest: `corpus-manifest-056765aa650055fb61689247c4c3b31b620b5dea1b1e8295cf2558d0c359ac10` — **incomplete**.
Each final ArticleVersion uses the corresponding original failed ArticleVersion as
its predecessor. Raw artifact ID, raw TextRecord ID and byte hash are unchanged;
no capture, authorization, receipt or old output record was rewritten.

### Driving

URL: https://www.diabinfo.de/leben/diabetes-im-alltag/strassenverkehr.html

- article_id: `corpus-article-90e99e0d46bd0bf8d1a1883e703ce8180caa7503983f854a8fd2e0e0fd84dffd`
- previous_version_id: `corpus-article-e590d6aa7bd9534217ecc31acfd9b9ecf9f2d3a475e0c47a1356d735a1594d3b`
- raw_artifact_id: `corpus-raw-html-b88fee4b5e77adbdb5abf43524b30e4fb892ef181f1cb18aa79c5c9e90b32e58`
- raw_text_id: `corpus-raw-text-aca197e1cf4a01e042547d734632975d794736558978afcff80347ae32d719a0`
- raw_sha256: `3f60f20f4c6ea60c422ef0d4f084bf1a7ce25b2ef9e4c99e8c85c05a56a28d99`
- cleaned_text_id: `corpus-clean-text-d383263fd510f84d167d3298da687c0feb47a4f3ac177f4a3d4eb65eb0b80199`
- cleaned_sha256: `2fdc2f33a8e94ed686a522b54db2b4d492aa9274be577524d671ae45b70182fb`
- Status: usable; passages: 41.

### Ramadan

URL: https://www.diabinfo.de/leben/diabetes-im-alltag/ramadan.html

- article_id: `corpus-article-f73f841a06718d9189c450b634b385f8c8c14dbbed5849054f4ce09611ad0617`
- previous_version_id: `corpus-article-8aab24eb5f3b55d2213d9550782f5e7b7073ac338c42c76934cb76cd0a28a8e7`
- raw_artifact_id: `corpus-raw-html-b20f8e3b1f9ab0f136d75089f503ec43eb717090a9b7e93a2652aa164cda39d2`
- raw_text_id: `corpus-raw-text-f83dd0753620bbc2fc4d3b84f356ed3a717535096eb67be8a2f5269f8ee34243`
- raw_sha256: `8730ea878ffba196a129c7feb6728ed92531b48a272ec01e9c98ffb37a331afd`
- cleaned_text_id: unavailable (unusable page)
- cleaned_sha256: unavailable (unusable page)
- Status: unusable; passages: 0.

### Travel

URL: https://www.diabinfo.de/leben/diabetes-im-alltag/reisen.html

- article_id: `corpus-article-2c14816c92138f467ebb04a22d22e215dca69166901dc73704fd67a6743a4f64`
- previous_version_id: `corpus-article-a0b260fb6cdf9d7ff2ce1ef69dfb28f743d9557b182c1e04fe3413863b62beb5`
- raw_artifact_id: `corpus-raw-html-50e27792b20ab24cd0e9f4bd68684187efe86308c81d554674000a9abdaad0a3`
- raw_text_id: `corpus-raw-text-5df6e633623591daa8d744e5f92eaa818d19a410ee64b74a60f9bdcd213442b9`
- raw_sha256: `e697d33561df1f21c894c9d1469e0587a340f2f39771f994ee7796869644b7a1`
- cleaned_text_id: `corpus-clean-text-4bf0586d43f78089a09e53bcc2415eabf981a0b1a1631dda0dfd82e1e7a66f37`
- cleaned_sha256: `2473123bd91a8d51bae07dc8f42e0b1ca0b5560af6e13f294b9f1d158e00b355`
- Status: usable; passages: 39.

### Risk-test FAQ

URL: https://www.diabinfo.de/vorbeugen/diabetes/wie-hoch-ist-mein-risiko-fuer-diabetes-typ-2/haeufig-gestellte-fragen.html

- article_id: `corpus-article-f0fbe24c5e57b947a215f82c7129a871edfb777306cb7262c2a6841190d27423`
- previous_version_id: `corpus-article-f0e086c38541ac41ec9f74d6ec16691b00e5edeaf19f8b2582c8078bc29a8acf`
- raw_artifact_id: `corpus-raw-html-252cad6f5db2f7a5b8eff062a091c652e38e3721df3320ac84b89a603d9b6e27`
- raw_text_id: `corpus-raw-text-b9cc011b8dcbc840a4d8d5f63aec8b32c064d75cd603d7a46ab08ca792ca0caa`
- raw_sha256: `e5e4d4e6958ff38b4a528d68686a3e81cacc025c5f740a1cb4ddfc3e24092c62`
- cleaned_text_id: `corpus-clean-text-eabc9e9eca81abb9fcf05e15c0a94719d4a8a53a4f73b9f8c51dae52cbf0567d`
- cleaned_sha256: `b6be1c8523262b3845ecd2421672b2e054c556dedf66cb5953c93b0ed9e7d888`
- Status: usable; passages: 97.

### Motivation

URL: https://www.diabinfo.de/vorbeugen/was-kann-ich-tun/so-erreichen-sie-ihre-ziele.html

- article_id: `corpus-article-c8cee093cf2d403c8045f2fb11a006267d2f6d9305d24a5aea15f418c9ccaf39`
- previous_version_id: `corpus-article-8aed706a5fd3427ca9845dd4e5d5d8cc23923a76c352fead4e6525b199b60c21`
- raw_artifact_id: `corpus-raw-html-c37f0ac65e03161451e1116793642b06f68e3e82855a1c754f811428f8e643cb`
- raw_text_id: `corpus-raw-text-bb190c0d7719d3ee3ed960658b62a62d9d6174c9792bdd96b45607e7467df129`
- raw_sha256: `9b85cee3e71ee696a667dd23dcb81a708201b567d6f9503ccf087b16328c97f6`
- cleaned_text_id: `corpus-clean-text-58ca9420962f9ffddf2e6a1cac7345ca460ffd5604a8c964def16f4381b24cd2`
- cleaned_sha256: `26b9956aa666b98f66aa2fdcd0ffc82fbe4809e4bda7d2d8e97c5a1e77b65e1c`
- Status: usable; passages: 24.

Original failed manifest:
`corpus-manifest-9b2788ec22042b1bdb1c0a93d3b8432348d61635f474d7c1d5b8e78fad415e6c`.

Rejected diagnostic manifest (do not select as accepted corpus):
`corpus-manifest-8368ed29181d0b1558acbe6a1269e9299d005d27c783a14065b3f20cf4c3d069`.

Restricted T11A inspection artifact:
`t06-live-20260919T114133Z.site-profile-review.v1` records the diagnostic rejection and current
blocked acceptance. A stored diagnostic `ready` status is not an accepted inspection.

## Reopen, integrity and network evidence

Original 27 records were unchanged after candidate replay; all 277 then-existing
records were unchanged after final replay. The loader validated completion hashes,
all shared links, raw/cleaned lineage, reconstructed structure/passages and the
persisted authorization companion `t06-live-20260919T114133Z.authorization.v1`.
Closing and reopening SQLite, loading, and rerunning the same final request returned
identical records/manifest. The original failed corpus also still loads.

A fresh process installed audit guards before imports: socket construction, DNS,
bind/connect and other socket events raise. The dependency `urllib3` attempted only
its import-time IPv6 capability probe; construction was blocked before any socket
existed. No DNS or connection attempt occurred. This caught probe is recorded, not
misreported as zero attempted socket construction. No model/resource download ran.
The scripts can replay from `acceptance-final/request.json`; no capture call is made.

## Remaining blocker and authorization boundary

**live_acceptance_blocked**: Ramadan references the external image
`/fileadmin/diabinfo/Grafiken/0511_diabinfo_Ramadan_DE_ohne-Titel.svg`.
Its saved alt label describes an infographic about fasting with diabetes, but the
SVG bytes/complete text are not in the six saved response bodies. No complete
transcript or duplication guarantee is present. Treating it as decorative would
silently drop potentially substantive content. Final reason:
`unsupported_informational_media`. The parser has not been loosened to force readiness.

The nearby HTML text was fully inspected, but cannot establish equivalence to an
unavailable graphic. Completing five-page acceptance requires sufficient offline
source evidence for that informational content; none is available in the store.
No further fetch is authorized or attempted. The prior live allowance remains
consumed: exactly six historical GETs, all HTTP 200, under policy digest
`78de13b54502cf2c8395d9be1301f66c74bbe0d8b8cf5a931f58e71c1aad5d18`.
See [capture history](t06-live-capture.md) for exact receipt times and raw hashes.
No merge, T07 work or MVP-completion claim.

## Regression checks and delivery

All final checks passed with `UV_OFFLINE=1` (including sync); no package downloads.
Earlier exploratory runs are superseded; a type-import issue was corrected without
weakening tests. The final conservative media rule is included in these results.

| Command | Result |
|---|---|
| `uv sync --locked --dev` | Passed; 103 packages audited |
| `uv run --offline --locked pytest tests/corpus` | 168 passed |
| `uv run --offline --locked pytest` | 755 passed |
| `uv run --offline --locked ruff check .` | Passed |
| `uv run --offline --locked ruff format --check .` | Passed; 150 files formatted |
| `uv run --offline --locked pyright` | Zero errors/warnings |
| `uv run --offline --locked python -m binfocheck.domain.export_schemas --check` | Schemas match |
| `git diff --check` | Passed |
| `git diff --cached --check` | Passed |

Final fetch confirmed `origin/main` remained
`80b35c95daaf06bfe9149551068d609e39d4ab58`, already merged into this branch;
no additional merge was needed. Draft PR #7 remains the delivery location.
Exact commit and new-head hosted CI status are appended to the external final
handoff after push; local checks above are separate from hosted CI.
