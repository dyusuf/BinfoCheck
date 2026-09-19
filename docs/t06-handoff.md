# T06 final textual-corpus handoff

**Task / assignee / status:** T06 / Codex / **live_acceptance_passed / merge_ready**.
Branch: `codex/t06-corpus`. Delivery: draft [PR #7](https://github.com/dyusuf/BinfoCheck/pull/7),
not merged. Reviewed starting head: `6a4f39b5e170d55e9676ce00d50f2f7e13849237`.
Exact delivery commit and hosted CI are recorded in the overwritten
`/tmp/binfocheck-t06-handoff.txt` and PR. This document describes that commit's result.

The original saved batch now yields **five usable ArticleVersions, 228 passages,
one coherent parser version and a ready manifest**. This derivation made **zero
external corpus/provider/model requests** and spent **USD 0** on providers.
Git/GitHub delivery synchronization is separate. No new live capture, package
download, OCR, image interpretation, vector-path inference, fabricated text,
retrieval or T07 work occurred. Deployed checks are not applicable.

## Approved D06 rule and implementation

The user explicitly approved: **usable means all deterministically extractable
textual evidence is represented; captured non-text informational visuals remain
explicit audited limitations**. Ramadan's SVG is informational, not decorative.
Its previously saved inspection reports `no_deterministic_text_extractable`.
No new SVG text is invented. The inspection's historical blocked acceptance
decision remains immutable; the new companion records the subsequent approved rule.

New `nontext.py` and `nontext_evidence_v1.json` implement the fixed evidence case.
Thirteen exact restricted artifact IDs/body hashes pin the original parent HTML,
batch/start/approval/Ramadan receipt/robots and the SVG approval/start/HTTP/asset
receipt/raw bytes/inspection. Validation reuses `asset.load_asset`, verifies URL,
parent, authorization, receipts, body hash/size and the exact inspection outcome.
Inspections with machine-readable text or accessibility wording cannot use this rule.
Nothing invokes asset capture or external XML resources during derivation.

Before any parser-5 derived record is published, ingestion validates this evidence.
The frozen evidence/policy identity is also in the parser hash. Failed preflight
returns a failed Outcome with no article writes; recovery cannot conflict with an
immutable failed ArticleVersion. Completion includes every evidence artifact plus
the restricted article-specific media companion. Loading requires graph membership,
hashes, restriction, full chain and reconstructed companion equality. Missing,
corrupt or mismatched evidence makes a formerly ready corpus fail load.

The informational gallery must exactly match its inspected URL and complete
structure/metadata signature. Its structure exclusion is distinctly
`captured_nontext_informational`; the companion links the original HTML DOM locator
and exact asset/inspection evidence. Unknown media still fails closed.
Decorative removal retains the parser-4 positive policy: page/kind plus exact
element/all-attributes/ordered-content subtree hash must match one of 16 deliberately
reviewed signatures (14 stock galleries and travel podcast icon/audio structure).
Copyright credit or absence of “Infografik” alone never permits removal.

No T00/domain/storage schema or shared contract changed. Existing fetch/settings/
passage versions remain 1. No dependencies or lockfile changed.
Pins remain Beautiful Soup **4.15.0**, explicit **html5lib 1.1** and model-free
**llama-index-core 0.14.24**, with Python 3.13 and locked transitive dependencies.
LlamaIndex only checks passage/node text, offsets and source links.

## Versions, lineage and corpus

Current factory: `binfocheck.corpus.diabinfo.pilot_profile()`.
Profile **diabinfo-pilot/4**, parser **t06-corpus-parser/5**.
Parser SHA-256: `db6903268a38e67a07699495f73402e1d8fe911ab2a9c702acff0c2efdec9870`.
Non-text evidence-policy SHA-256: `9f8e55b1c116a651528b2d53f05a6d7c968b6ecf0c2645a46fa9e19ee70d834b`.

Historical versions retain their identities and remain loadable:

- parser 1: `c448c2e55730915600d812dd074b0f0787aae6270de7d06b4cab838a464d3898`;
  original five failures because saved pages have no `article` element;
- profile 1 / parser 2: `5a9e2078f27dd2e57f77fb76cc44581760f2c52ef9e7d119fd3040e4d9ac8584`;
  rejected diagnostic candidate that omitted the informational visual;
- profile 2 / parser 3: `b4cd5fdda187a0da1206547e17416f64eed93a767f8d4a0b5fa32808be13e85e`;
  four usable, Ramadan blocked;
- profile 3 / parser 4: `a21b5e2f13e5108af14ed504feda09415e191755d6ffdcef2685c700f7fd7037`;
  positive media guard, four usable and 201 passages.

All five new ArticleVersions use the parser-4 versions below as predecessors.
Original raw HTML artifact IDs/hashes and raw TextRecord IDs are identical.
The four unaffected cleaned texts and ordered passage wording are identical;
derived text/passage IDs differ because their ArticleVersion/parser changed.

Historical manifest IDs (also verified on reopen):

- Parser 1 failed: `corpus-manifest-9b2788ec22042b1bdb1c0a93d3b8432348d61635f474d7c1d5b8e78fad415e6c`.
- Parser 2 rejected diagnostic: `corpus-manifest-8368ed29181d0b1558acbe6a1269e9299d005d27c783a14065b3f20cf4c3d069`.
- Parser 3 incomplete: `corpus-manifest-056765aa650055fb61689247c4c3b31b620b5dea1b1e8295cf2558d0c359ac10`.

Batch: `t06-live-20260919T114133Z`.
Prior parser-4 manifest:
`corpus-manifest-ec0a9377dbd14090a7edf1cecfe51a9a850280a44dcc65097bed446d4e4b8545`.
Final **ready** manifest:
`corpus-manifest-cca67f16867a3a37e37252c360e364e597a2cab368ac6cc52ee5d6b693d41e69`.
Completion: final manifest ID plus `.completion.v1`.
Ramadan media-evidence artifact:
`corpus-article-64852ee4c0341e95b60af5e3cf7721e83cd7786e68d50c225b87c46862898f3d.media-evidence.v1`.

| Page | Cleaned code points | Passages | Headings | List items | Links |
|---|---:|---:|---:|---:|---:|
| Straßenverkehr | 14,029 | 41 | 18 | 29 | 14 |
| Ramadan | 11,144 | 27 | 14 | 44 | 31 |
| Reisen | 20,965 | 39 | 22 | 25 | 29 |
| FAQ | 38,979 | 97 | 34 | 4 | 102 |
| Ziele | 10,285 | 24 | 18 | 51 | 14 |

### Straßenverkehr

- URL: `https://www.diabinfo.de/leben/diabetes-im-alltag/strassenverkehr.html`
- ArticleVersion: `corpus-article-b5ff7e8c4fc68d8feca70c71065de5700554256db55c635dc56af9683898a9de`
- Parser-4 predecessor: `corpus-article-f320f1f52eeccc98768df42e3504e9b1f0a5f8ded795cf8619531de6380dea34`
- Raw HTML artifact: `corpus-raw-html-b88fee4b5e77adbdb5abf43524b30e4fb892ef181f1cb18aa79c5c9e90b32e58`
- Raw byte SHA-256: `3f60f20f4c6ea60c422ef0d4f084bf1a7ce25b2ef9e4c99e8c85c05a56a28d99`
- Raw TextRecord: `corpus-raw-text-aca197e1cf4a01e042547d734632975d794736558978afcff80347ae32d719a0`
- Cleaned TextRecord: `corpus-clean-text-e8fd4bad2f3ab8e7ad03c65c8e6db148bfa6ebc5f6a960e37f9e6dca4320b667`
- Cleaned UTF-8 SHA-256: `2fdc2f33a8e94ed686a522b54db2b4d492aa9274be577524d671ae45b70182fb`
- Passages: **41**; exact source coverage and all spans passed.

### Ramadan

- URL: `https://www.diabinfo.de/leben/diabetes-im-alltag/ramadan.html`
- ArticleVersion: `corpus-article-64852ee4c0341e95b60af5e3cf7721e83cd7786e68d50c225b87c46862898f3d`
- Parser-4 predecessor: `corpus-article-fce0eeaf180f7f607c2d99c558f77a0c7b85f25f73be37c677e65515f66d1bf1`
- Raw HTML artifact: `corpus-raw-html-b20f8e3b1f9ab0f136d75089f503ec43eb717090a9b7e93a2652aa164cda39d2`
- Raw byte SHA-256: `8730ea878ffba196a129c7feb6728ed92531b48a272ec01e9c98ffb37a331afd`
- Raw TextRecord: `corpus-raw-text-f83dd0753620bbc2fc4d3b84f356ed3a717535096eb67be8a2f5269f8ee34243`
- Cleaned TextRecord: `corpus-clean-text-143b34ad94f798e3dcb1e0daca756cedb7de3797543300c3031f1a4451a7e788`
- Cleaned UTF-8 SHA-256: `c1695edce5958b17efa7660f3f03c2c24933521ecb599640c5360fe37c7725ee`
- Passages: **27**; exact source coverage and all spans passed.

### Reisen

- URL: `https://www.diabinfo.de/leben/diabetes-im-alltag/reisen.html`
- ArticleVersion: `corpus-article-eb2af5d31e98eb7ff287db5e4fff8c56286245a87ecb3ed4a40edd2d3c1ece5f`
- Parser-4 predecessor: `corpus-article-99fac2f987603b8e25ef3835afd9da73574c97351e56a697c79738f073f494bd`
- Raw HTML artifact: `corpus-raw-html-50e27792b20ab24cd0e9f4bd68684187efe86308c81d554674000a9abdaad0a3`
- Raw byte SHA-256: `e697d33561df1f21c894c9d1469e0587a340f2f39771f994ee7796869644b7a1`
- Raw TextRecord: `corpus-raw-text-5df6e633623591daa8d744e5f92eaa818d19a410ee64b74a60f9bdcd213442b9`
- Cleaned TextRecord: `corpus-clean-text-c8f7d258d0e8efc06921593b29c76bab9fe44022791586e6aa7a7b2157570c70`
- Cleaned UTF-8 SHA-256: `2473123bd91a8d51bae07dc8f42e0b1ca0b5560af6e13f294b9f1d158e00b355`
- Passages: **39**; exact source coverage and all spans passed.

### FAQ

- URL: `https://www.diabinfo.de/vorbeugen/diabetes/wie-hoch-ist-mein-risiko-fuer-diabetes-typ-2/haeufig-gestellte-fragen.html`
- ArticleVersion: `corpus-article-7a7e1fcc86535301fae3d0f16c735cb4a077d5459e2dd300c68703c0c2a2dd34`
- Parser-4 predecessor: `corpus-article-f4c8c130bc6bf4b76cb1ce02d64a359ce7f7d448cf05c40f52ca03c618f74007`
- Raw HTML artifact: `corpus-raw-html-252cad6f5db2f7a5b8eff062a091c652e38e3721df3320ac84b89a603d9b6e27`
- Raw byte SHA-256: `e5e4d4e6958ff38b4a528d68686a3e81cacc025c5f740a1cb4ddfc3e24092c62`
- Raw TextRecord: `corpus-raw-text-b9cc011b8dcbc840a4d8d5f63aec8b32c064d75cd603d7a46ab08ca792ca0caa`
- Cleaned TextRecord: `corpus-clean-text-22a0d0a4ddd4d697fc734aac7d1ce27f5a98028696bf127a084779ce0e2852d2`
- Cleaned UTF-8 SHA-256: `b6be1c8523262b3845ecd2421672b2e054c556dedf66cb5953c93b0ed9e7d888`
- Passages: **97**; exact source coverage and all spans passed.

### Ziele

- URL: `https://www.diabinfo.de/vorbeugen/was-kann-ich-tun/so-erreichen-sie-ihre-ziele.html`
- ArticleVersion: `corpus-article-6dbb5c44ddcd66b55cab28c0ea733af8ea4279df56ef20a2557c6df19c37fd10`
- Parser-4 predecessor: `corpus-article-423dc0fa3de666d289ed738473fc4cd490b0957d681c442eb7b637223cd12f04`
- Raw HTML artifact: `corpus-raw-html-c37f0ac65e03161451e1116793642b06f68e3e82855a1c754f811428f8e643cb`
- Raw byte SHA-256: `9b85cee3e71ee696a667dd23dcb81a708201b567d6f9503ccf087b16328c97f6`
- Raw TextRecord: `corpus-raw-text-bb190c0d7719d3ee3ed960658b62a62d9d6174c9792bdd96b45607e7467df129`
- Cleaned TextRecord: `corpus-clean-text-c1eb4abc61587e2a381a0a793e7c1cc347126cef14a2aa9aec7caa56b88494e9`
- Cleaned UTF-8 SHA-256: `26b9956aa666b98f66aa2fdcd0ffc82fbe4809e4bda7d2d8e97c5a1e77b65e1c`
- Passages: **24**; exact source coverage and all spans passed.

## Media evidence and limitation

- Exact URL: `https://www.diabinfo.de/fileadmin/diabinfo/Grafiken/0511_diabinfo_Ramadan_DE_ohne-Titel.svg`.
- Raw SVG: `corpus-raw-svg-1201b0c36772982079a76330da05f79bf236b6f30105dda898a30bbd38ac33ad`.
- Complete body: **313,754 bytes**, SHA-256
  `36dac445d2a67c53105b125a86a576d597b3544ed3f634146466f0862fc909de`.
- Inspection: `t06-ramadan-svg-1.inspection.v1`, SHA-256
  `6f1f81165037e45c44b7851b4aec1b723dda4b944a909b73e998e22032a2e1c1`.
- Evidence chain: `t06-ramadan-svg-1.authorization.v1`, `.start.v1`,
  `.http.v1`, `.receipt.v1`; original page approval
  `t06-live-20260919T114133Z.authorization.v1` remains linked.
- Disposition: **captured_nontext_informational**.
- Persisted limitation: “Informational visual captured and preserved; no deterministic
  machine-readable text is extractable. Visual content is not represented by textual
  passages. No OCR, image interpretation, SVG path inference or fabricated text.”

The 587-element SVG contains no text/tspan/title/desc or accessibility wording.
Its vectors were not interpreted. This is an explicit limitation of the textual
corpus, not a claim that the visual lacks information. Both historical request
allowances (six GETs plus one separate SVG GET) remain fully consumed.
No further network request is authorized.

## Complete inspection and replay

Four explicit title/scientific-credit/introduction/article roots are unchanged.
They bound `main#main > .container` rather than extracting the whole container.
Navigation/sidebar/footer, TOC, related-news modules, approved decorative media and
media controls are excluded. References, editorial links, qualifiers, heading
ancestry, ordered/unordered nested lists and FAQ answer content remain.

The full Ramadan cleaned representation was read this turn: title and scientific
credit, introduction, all six numbered sections, risk groups and nested therapies,
risk assessment/control/nutrition/exercise/medication subsections, fasting-interruption
thresholds and their warning, pregnancy, benefits/risks, sources and dated ending.
Numbers, German qualifiers and punctuation remain unchanged apart from the existing
deterministic structural whitespace/list markers. No visual wording was added.
The other four complete representations were previously inspected; byte-for-byte
cleaned-text equality and ordered passage-content equality were reverified.
Driving retains its licence/risk sections and references; travel retains preparation,
medication/time-zone guidance and references; FAQ preserves all 29 questions beneath
four topic headings and all answers; goals retains its ordered steps, sublists,
callouts and sources.

Independent source-DOM coverage checks passed for all five: every retained nonblank
text node belongs to exactly one block; wording matches after defined whitespace/
list-marker treatment; original links match the structure companion. Every block,
heading, list item, link and passage SpanRef slices exactly to the immutable clean
TextRecord. Passages resolve to their ArticleVersion and heading ancestry. Only a
colon-ended paragraph and following same-section list may form a joint passage.

SQLite was closed then reopened. Load and replay produced identical complete
records/manifests with socket construction, DNS and connections blocked by a Python
audit hook. Historical parsers 1–4 still load. The transitive urllib3 import attempted
its local IPv6 capability probe; the hook blocked construction before any socket
existed. No DNS or connection/request occurred. Tests also directly replace socket/
DNS and asset-dispatch functions with failing stubs during reopen/replay.

## Durable private preservation

Continuing store:
`/mnt/workspace/BinfoCheck-data/t06-live-20260919T114133Z`.

Original quiescent source:
`/tmp/binfocheck-t06-live-20260919T114133Z`.
Its **29 files / 2,826,449 bytes** remain unchanged by complete membership, size and
SHA-256 verification. Original durable payloads remain identical; all **717**
preexisting records compare equal after deriving **246** new records (**963 total**).
No capture, historical article or inspection record was rewritten.
Parent/store directories remain 0700, all descendants have no group/other access.
SQLite integrity check is `ok`. This is private local storage, not an off-machine backup.

Private `acceptance-textual-v1/` holds exact `request.json`, full cleaned text and
structure exports for all five pages, `report.json`, and `verification.json`.
The earlier preservation and inspection files remain. No real HTML, SVG, private
store or cleaned real article text enters Git; committed fixtures are hand-authored.

## Validation and delivery

All required checks passed on this derivation:

| Command | Result |
|---|---|
| `UV_OFFLINE=1 uv sync --locked --dev` | Passed; 103 locked packages, no downloads |
| `uv run --offline --locked pytest tests/corpus` | **256 passed** |
| `uv run --offline --locked pytest` | **843 passed** |
| `uv run --offline --locked ruff check .` | Passed |
| `uv run --offline --locked ruff format --check .` | Passed; 156 files |
| `uv run --offline --locked pyright` | 0 errors / warnings |
| `uv run --offline --locked python -m binfocheck.domain.export_schemas --check` | Passed |
| `git diff --check` / `git diff --cached --check` | Passed |

The `uv run` commands used the private temporary uv cache setting; all were locked
and offline. Exact-head hosted CI is recorded separately in the final delivery
handoff after push; local results do not imply a hosted CI result.
New synthetic tests cover exact
permission, missing/corrupt/wrong evidence and semantic chain mismatches, unrelated
SVGs, no-text versus textual inspections, graph/companion corruption, preflight
no-write recovery, immutable identities, historical replay and socket-blocked reopen.
Existing fail-closed tests remain intact.

Final synchronization currently finds main unchanged at
`80b35c95daaf06bfe9149551068d609e39d4ab58`; no merge is necessary.
No T06 acceptance blocker remains under the explicit product decision.
The captured non-text visual limitation remains part of provenance.
PR #7 stays draft; **do not merge**. No T07 work.
