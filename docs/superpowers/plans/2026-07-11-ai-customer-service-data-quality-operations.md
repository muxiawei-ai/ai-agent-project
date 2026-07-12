# AI Customer Service Data Quality Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only, auditable pipeline that extracts already-anonymized AI customer-service interactions, enforces deterministic data-quality gates, creates complete audit exports and strong-model analysis batches, and produces reviewed monthly PDF/Excel reports without modifying production systems. Confirmed single-turn findings may be exported as *draft* UAT regression candidates only after human review.

**Architecture:** A Python 3.11 command-line application reads paginated records through an adapter interface, records checkpoints and run state in SQLite, writes immutable Parquet/CSV artifacts, and blocks release when hard quality gates fail. Separate modules create model batches, import strong-model JSONL findings as unconfirmed candidates, build Excel/PDF reports, and send email through company SMTP; scheduling remains an external IT responsibility.

**Tech Stack:** Python 3.11, Pydantic 2, HTTPX, pandas, PyArrow, openpyxl, ReportLab, PyYAML, SQLite, pytest, respx, GitHub Actions.

## Global Constraints

- Production access is read-only; no module may accept knowledge-base, customer-service configuration, or compliance-policy write credentials.
- Input is already anonymized by the upstream system; this application only quarantines obvious contract violations and does not claim to implement the corporate anonymization standard.
- Monthly volume is 10,000–100,000 interaction records.
- All records receive deterministic checks; all exception records enter model batches; normal records use reproducible stratified sampling.
- Strong-model findings enter the system with status `PENDING_BUSINESS_REVIEW` and cannot affect confirmed-error KPIs until a human changes the status through an approved import file.
- “公司强模型”（strong model）仅指业务人员人工调用的高能力公司模型；数据管线不得调用弱模型或把模型服务嵌入自动运行链路。
- Complete interaction exports never travel as email attachments; email contains PDF/Excel reports and a company-controlled storage location.
- Daily deterministic checks remain active after the weekly strong-model review is reduced to monthly.
- File and schema versions are explicit; silent field drops, coercions, or API schema changes are release-blocking failures.
- The UAT execution package is currently a **single-turn** contract. A multi-turn interaction finding is evidence for analysis and remediation, but must never be projected directly into a single-turn UAT case; it requires a separately approved multi-turn UAT design.
- A post-launch finding never changes the production knowledge base, UAT expected answer, UAT approval status, or compliance rule. It can only create a reviewable draft with evidence and a proposed action.
- Any regression export must use the UAT v1.4 Candidate_Cases contract, contain a unique `generator_run_id`, and require business/compliance approvals before it can enter `04_Frozen_Cases`.

---

## 1. Scope and Repository Layout

The repository currently contains documentation, prompts, examples, and the UAT v1.4 Excel workbook but no executable application. Add the operations pipeline as a focused Python package. It may create a review-only UAT-candidate export, but must not overwrite the UAT workbook, freeze cases, or modify existing UAT rules.

```text
pyproject.toml
config/
  cs_ops.example.yml
schemas/
  interaction-v1.schema.json
  finding-candidate-v1.schema.json
prompts/
  ops-analysis-v1.md
src/cs_ops/
  __init__.py
  config.py
  models.py
  source.py
  state.py
  extract.py
  quality.py
  export.py
  batching.py
  dq_workbook.py
  findings.py
  monthly_report.py
  alerts.py
  pipeline.py
  cli.py
tests/
  fixtures/
    source_page_1.json
    source_page_2.json
    finding_candidates.jsonl
  unit/
  integration/
  load/
docs/runbooks/
  ai-customer-service-operations.md
.github/workflows/
  cs-ops-tests.yml
```

### Locked interfaces

These signatures are the contract between tasks and must not be renamed without updating every later task and test.

```python
class InteractionSource(Protocol):
    async def count(self, start: datetime, end: datetime) -> int: ...
    async def iter_pages(self, start: datetime, end: datetime) -> AsyncIterator[SourcePage]: ...

class KnowledgeBaseSource(Protocol):
    async def snapshot(self, effective_at: datetime) -> list[KnowledgeBaseRecord]: ...

class RunStateStore:
    def start_run(self, run_type: str, start: datetime, end: datetime) -> str: ...
    def mark_success(self, run_id: str, checkpoint: datetime) -> None: ...
    def mark_failure(self, run_id: str, error_code: str, message: str) -> None: ...
    def last_checkpoint(self, run_type: str) -> datetime | None: ...

class Extractor:
    async def run(self, run_id: str, start: datetime, end: datetime) -> ExtractionResult: ...

class QualityEngine:
    def evaluate(self, extraction: ExtractionResult) -> QualityResult: ...

class AuditExporter:
    def publish(
        self,
        period: str,
        extraction: ExtractionResult,
        quality: QualityResult,
        kb_snapshot: Sequence[KnowledgeBaseRecord],
    ) -> ExportManifest: ...

class BatchPlanner:
    def build(self, period: str, manifest: ExportManifest, quality: QualityResult) -> BatchManifest: ...

class DataQualityWorkbookBuilder:
    def build(self, manifest: ExportManifest, quality: QualityResult, output_path: Path) -> Path: ...

class FindingImporter:
    def import_jsonl(self, files: Sequence[Path], output_path: Path) -> FindingsImportResult: ...

class MonthlyReportBuilder:
    def build(self, period: str, inputs: MonthlyReportInputs, output_dir: Path) -> MonthlyReportArtifacts: ...
```

## Task 1: Package Scaffold, Configuration, and Canonical Models

**Files:**
- Create: `pyproject.toml`
- Create: `config/cs_ops.example.yml`
- Create: `src/cs_ops/__init__.py`
- Create: `src/cs_ops/config.py`
- Create: `src/cs_ops/models.py`
- Create: `tests/unit/test_config.py`
- Create: `tests/unit/test_models.py`

**Interfaces:**
- Consumes: none.
- Produces: `AppConfig`, `InteractionRecord`, `KnowledgeBaseRecord`, `SourcePage`, `ExtractionResult`, `QualityFinding`, `QualityResult`, `FileEntry`, `ExportManifest`, `BatchManifest`, `FindingCandidate`, and report artifact models used by every later task.

- [ ] **Step 1: Create the package metadata and exact dependency floors**

Create `pyproject.toml` with this content:

```toml
[build-system]
requires = ["setuptools>=69", "wheel>=0.43"]
build-backend = "setuptools.build_meta"

[project]
name = "cs-ops"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
  "httpx>=0.27,<1",
  "pandas>=2.2,<3",
  "pyarrow>=16,<20",
  "pydantic>=2.7,<3",
  "PyYAML>=6,<7",
  "openpyxl>=3.1,<4",
  "reportlab>=4.2,<5",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "pytest-asyncio>=0.23,<1",
  "pypdf>=4.2,<6",
  "respx>=0.21,<1",
  "ruff>=0.5,<1",
]

[project.scripts]
cs-ops = "cs_ops.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100
```

Run: `python -m pip install -e '.[dev]'`

Expected: installation completes and `python -c "import pydantic, pyarrow, pandas"` exits 0.

- [ ] **Step 2: Write failing configuration tests**

Create `tests/unit/test_config.py`:

```python
from pathlib import Path

import pytest

from cs_ops.config import AppConfig


def test_config_requires_read_only_source_and_environment_secret(tmp_path: Path):
    path = tmp_path / "config.yml"
    path.write_text(
        """
source:
  base_url: https://internal.example.invalid
  endpoint: /v1/interactions
  count_endpoint: /v1/interactions/count
  kb_snapshot_endpoint: /v1/knowledge-base/snapshot
  auth_token_env: CS_OPS_API_TOKEN
  page_size: 1000
  read_only: true
storage:
  root: ./var/cs-ops
  publication_uri: smb://internal.example.invalid/cs-ops
mail:
  smtp_host: smtp.example.invalid
  smtp_port: 465
  password_env: CS_OPS_SMTP_PASSWORD
  sender: cs-ops@example.invalid
  recipients: [business@example.invalid, it@example.invalid]
alerts:
  baseline_days: 28
  strict_whitelist_mode: true
  empty_or_system_error_rate_max: 0.01
  fallback_rate_increase_pp_max: 0.10
  handoff_rate_increase_pp_max: 0.10
  negative_feedback_rate_increase_pp_max: 0.05
  prohibited_qa_by_intent:
    SENSITIVE_INTENT: [QA-BLOCKED]
""".strip(),
        encoding="utf-8",
    )
    config = AppConfig.from_yaml(path)
    assert config.source.read_only is True
    assert config.source.auth_token_env == "CS_OPS_API_TOKEN"


def test_config_rejects_write_enabled_source(tmp_path: Path):
    path = tmp_path / "config.yml"
    path.write_text(
        """
source:
  base_url: https://internal.example.invalid
  endpoint: /v1/interactions
  count_endpoint: /v1/interactions/count
  kb_snapshot_endpoint: /v1/knowledge-base/snapshot
  auth_token_env: CS_OPS_API_TOKEN
  page_size: 1000
  read_only: false
storage:
  root: ./var/cs-ops
  publication_uri: smb://internal.example.invalid/cs-ops
mail:
  smtp_host: smtp.example.invalid
  smtp_port: 465
  password_env: CS_OPS_SMTP_PASSWORD
  sender: cs-ops@example.invalid
  recipients: [business@example.invalid, it@example.invalid]
alerts:
  baseline_days: 28
  strict_whitelist_mode: true
  empty_or_system_error_rate_max: 0.01
  fallback_rate_increase_pp_max: 0.10
  handoff_rate_increase_pp_max: 0.10
  negative_feedback_rate_increase_pp_max: 0.05
  prohibited_qa_by_intent:
    SENSITIVE_INTENT: [QA-BLOCKED]
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="read_only must be true"):
        AppConfig.from_yaml(path)
```

- [ ] **Step 3: Run the configuration tests and confirm the expected failure**

Run: `pytest tests/unit/test_config.py -q`

Expected: FAIL during import because `cs_ops.config` does not exist.

- [ ] **Step 4: Implement typed configuration with a hard read-only validator**

Create `src/cs_ops/config.py` with Pydantic models `SourceConfig`, `StorageConfig`, `MailConfig`, `QualityConfig`, `BatchConfig`, `AlertConfig`, and `AppConfig`. `SourceConfig` requires `endpoint`, `count_endpoint`, and `kb_snapshot_endpoint`; `StorageConfig` requires `root` and `publication_uri`; `MailConfig` requires `smtp_host`, `smtp_port`, `password_env`, `sender`, and at least two recipients. Implement:

```python
@classmethod
def from_yaml(cls, path: Path) -> "AppConfig":
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = cls.model_validate(payload)
    if not config.source.read_only:
        raise ValueError("source.read_only must be true")
    return config
```

Use these defaults:

```python
page_size: int = 1000
lookback_hours: int = 48
normal_sample_rate: float = 0.05
min_normal_samples_per_qa: int = 30
max_turns_per_batch: int = 3000
time_valid_rate_min: float = 0.999
baseline_days: int = 28
empty_or_system_error_rate_max: float = 0.01
fallback_rate_increase_pp_max: float = 0.10
handoff_rate_increase_pp_max: float = 0.10
negative_feedback_rate_increase_pp_max: float = 0.05
```

Create `config/cs_ops.example.yml` using the `.invalid` hostnames from the test and add `quality` and `batch` sections with the defaults above. Do not put a token, password, production hostname, or email credential in the file.

- [ ] **Step 5: Write failing canonical model tests**

Create `tests/unit/test_models.py`:

```python
from datetime import datetime, timezone

import pytest

from cs_ops.models import FeedbackValue, InteractionRecord, MessageStatus


def valid_record() -> dict:
    return {
        "record_id": "R-1",
        "event_time": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "session_id_anon": "S-1",
        "user_input_masked": "How do I reset my password?",
        "assistant_output_masked": "Use the password reset page.",
        "message_status": "SUCCESS",
        "fallback_type": "NONE",
        "handoff_flag": False,
        "feedback_value": "NO_FEEDBACK",
        "source_record_ref_hash": "sha256:abc",
    }


def test_interaction_record_accepts_canonical_enums():
    record = InteractionRecord.model_validate(valid_record())
    assert record.message_status is MessageStatus.SUCCESS
    assert record.feedback_value is FeedbackValue.NO_FEEDBACK


def test_success_record_requires_assistant_output():
    payload = valid_record()
    payload["assistant_output_masked"] = None
    with pytest.raises(ValueError, match="SUCCESS requires assistant_output_masked"):
        InteractionRecord.model_validate(payload)
```

- [ ] **Step 6: Implement the canonical models and rerun Task 1 tests**

In `src/cs_ops/models.py`, implement string enums for `MessageStatus`, `FallbackType`, `FeedbackValue`, `FindingSeverity`, `FindingSource`, and `FindingStatus`. Implement `InteractionRecord` with the required and recommended fields from the design, including:

```python
turn_no: int | None = None
matched_qa_id: str | None = None
intent_id: str | None = None
kb_version: str | None = None
response_time_ms: int | None = None
channel: str = "UNKNOWN"
    language: str | None = None
    interaction_scope: str = "UNKNOWN"  # SINGLE_TURN / MULTI_TURN / UNKNOWN
    conversation_turn_count: int | None = None
    sequence_inferred: bool = False
qa_id_inferred: bool = False
kb_version_inferred: bool = False
```

Add a model validator that rejects `SUCCESS` records without `assistant_output_masked`. Define `KnowledgeBaseRecord` with `qa_id`, `kb_version`, `standard_question`, `approved_answer`, `effective_from`, `effective_to`, and `status`. Define the remaining locked-interface models as typed Pydantic containers; use `Path` for file paths, `datetime` for timestamps, and `Decimal` for rates.

Run: `pytest tests/unit/test_config.py tests/unit/test_models.py -q`

Expected: all Task 1 tests PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add pyproject.toml config/cs_ops.example.yml src/cs_ops tests/unit/test_config.py tests/unit/test_models.py
git commit -m "build: scaffold customer service operations package"
```

## Task 2: Read-Only Interaction and Knowledge-Base API Adapters

**Files:**
- Create: `src/cs_ops/source.py`
- Create: `tests/fixtures/source_page_1.json`
- Create: `tests/fixtures/source_page_2.json`
- Create: `tests/unit/test_source.py`

**Interfaces:**
- Consumes: `AppConfig`, `InteractionRecord`, `SourcePage`.
- Produces: `InteractionSource`, `KnowledgeBaseSource`, `HttpInteractionSource.count()` / `iter_pages()`, and `HttpKnowledgeBaseSource.snapshot()`.

- [ ] **Step 1: Add two deterministic paginated fixtures**

Create `tests/fixtures/source_page_1.json` with two valid records, `next_cursor` set to `cursor-2`, and `schema_version` set to `interaction-v1`. Create `source_page_2.json` with one valid record and `next_cursor` set to null. Add a knowledge-base fixture in the test module containing `QA-001`, version `KB-RC1-202607`, a fictional reset question, an approved reset answer, and an active effective-time window. Use only fictional anonymized values.

- [ ] **Step 2: Write failing adapter tests**

Create `tests/unit/test_source.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from cs_ops.config import AppConfig
from cs_ops.source import HttpInteractionSource


@pytest.mark.asyncio
async def test_iter_pages_uses_cursor_without_write_requests(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CS_OPS_API_TOKEN", "test-token")
    config = AppConfig.from_yaml(Path("config/cs_ops.example.yml"))
    page1 = Path("tests/fixtures/source_page_1.json").read_text(encoding="utf-8")
    page2 = Path("tests/fixtures/source_page_2.json").read_text(encoding="utf-8")
    with respx.mock(base_url=config.source.base_url) as router:
        first = router.get(config.source.endpoint, params__contains={"cursor": ""}).mock(
            return_value=httpx.Response(200, text=page1)
        )
        second = router.get(config.source.endpoint, params__contains={"cursor": "cursor-2"}).mock(
            return_value=httpx.Response(200, text=page2)
        )
        source = HttpInteractionSource(config.source)
        pages = [page async for page in source.iter_pages(
            datetime(2026, 7, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 2, tzinfo=timezone.utc),
        )]
    assert first.called and second.called
    assert sum(len(page.records) for page in pages) == 3
    assert all(call.request.method == "GET" for call in router.calls)
```

- [ ] **Step 3: Run the adapter test and verify it fails**

Run: `pytest tests/unit/test_source.py -q`

Expected: FAIL because `HttpInteractionSource` is not implemented.

- [ ] **Step 4: Implement the protocol, count request, pagination, and schema guard**

Implement `InteractionSource` and `KnowledgeBaseSource` as `typing.Protocol` types. In `HttpInteractionSource`:

- Read the bearer token only from `os.environ[auth_token_env]`.
- Use `GET` for both count and interaction endpoints.
- Send ISO-8601 UTC `start` and `end` query parameters.
- Send an empty cursor on the first page and the returned cursor on later pages.
- Validate `schema_version == "interaction-v1"` before parsing records.
- Reject repeated cursors with error code `SOURCE_CURSOR_LOOP`.
- Use connect/read/write/pool timeouts of 10/60/10/10 seconds.
- Retry HTTP 429 and 5xx responses three times with waits of 1, 2, and 4 seconds.
- Never implement POST, PUT, PATCH, or DELETE helpers.

Implement `HttpKnowledgeBaseSource.snapshot(effective_at)` as one authenticated GET to `kb_snapshot_endpoint` with the `effective_at` UTC parameter. Validate response contract `{"schema_version":"knowledge-base-v1","items":[...]}` and parse every item as `KnowledgeBaseRecord`.

The count endpoint response contract is `{"count": 123}`. The interaction endpoint contract is `{"schema_version": "interaction-v1", "items": [...], "next_cursor": null}`.

- [ ] **Step 5: Add tests for schema drift, repeated cursors, and retry exhaustion**

Add four tests that assert:

- unknown schema raises `SourceContractError("SOURCE_SCHEMA_VERSION")`;
- repeated `next_cursor` raises `SourceContractError("SOURCE_CURSOR_LOOP")`;
- three 503 responses raise `SourceUnavailableError("SOURCE_RETRY_EXHAUSTED")`.
- the knowledge-base snapshot uses GET, validates `knowledge-base-v1`, and returns the fictional `QA-001` record.

Run: `pytest tests/unit/test_source.py -q`

Expected: all adapter tests PASS and every recorded request method is GET.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/cs_ops/source.py tests/fixtures/source_page_1.json tests/fixtures/source_page_2.json tests/unit/test_source.py
git commit -m "feat: add read-only source adapters"
```

## Task 3: SQLite Run State, Checkpoints, and Incremental Extraction

**Files:**
- Create: `src/cs_ops/state.py`
- Create: `src/cs_ops/extract.py`
- Create: `tests/unit/test_state.py`
- Create: `tests/integration/test_extraction.py`

**Interfaces:**
- Consumes: `InteractionSource`, `RunStateStore`, `SourcePage`, `ExtractionResult`.
- Produces: idempotent run state and Parquet staging parts for `QualityEngine`.

- [ ] **Step 1: Write failing state-store tests**

Create `tests/unit/test_state.py` to assert that a new SQLite store:

- returns no checkpoint;
- creates a run with status `RUNNING`;
- records `SUCCESS` with a UTC checkpoint;
- records `FAILED` with an error code and message;
- refuses to move a completed run back to `RUNNING`.

Use a temporary database path in every test.

- [ ] **Step 2: Implement the SQLite schema and state transitions**

In `src/cs_ops/state.py`, create tables:

```sql
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  window_start TEXT NOT NULL,
  window_end TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCESS','FAILED')),
  error_code TEXT,
  error_message TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS checkpoints (
  run_type TEXT PRIMARY KEY,
  checkpoint TEXT NOT NULL,
  run_id TEXT NOT NULL
);
```

Use transactions and UTC ISO strings. Generate run IDs as `RUN-<UTC timestamp>-<8 hex chars>`.

Run: `pytest tests/unit/test_state.py -q`

Expected: all state tests PASS.

- [ ] **Step 3: Write a failing incremental extraction integration test**

Create a fake `InteractionSource` yielding the two fixture pages. Test that `Extractor.run()`:

- calls `source.count(start, end)` once;
- writes one Parquet staging file per source page;
- returns `source_count=3`, `extracted_count=3`, and the maximum event time;
- does not update the checkpoint itself;
- preserves every canonical field.

- [ ] **Step 4: Implement page-by-page extraction**

In `src/cs_ops/extract.py`:

- Create `staging/<run_id>/` beneath configured storage.
- Convert each page to a PyArrow table using a stable column order defined in `models.py`.
- Write `part-00001.parquet`, `part-00002.parquet`, and so on with Zstandard compression.
- Calculate a SHA-256 for each staging part.
- Return `ExtractionResult` with the exact source count, extracted count, file entries, start/end window, and maximum event time.
- If a page contains zero records but has a cursor, continue; if the complete run extracts zero records while source count is nonzero, raise `ExtractionError("SOURCE_EXPORT_COUNT_MISMATCH")`.

- [ ] **Step 5: Verify extraction and restart behavior**

Run: `pytest tests/unit/test_state.py tests/integration/test_extraction.py -q`

Expected: all tests PASS. Delete one staging part in a test and rerun the same window with a new run ID; the new run must regenerate all parts without reading the old incomplete directory.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/cs_ops/state.py src/cs_ops/extract.py tests/unit/test_state.py tests/integration/test_extraction.py
git commit -m "feat: add checkpointed incremental extraction"
```

## Task 4: Deterministic Data-Quality Engine and Release Gates

**Files:**
- Create: `src/cs_ops/quality.py`
- Create: `tests/unit/test_quality.py`
- Create: `tests/integration/test_quality_release_gate.py`

**Interfaces:**
- Consumes: `ExtractionResult` and staged Parquet files.
- Produces: `QualityResult` with `release_allowed`, metrics, hard failures, warnings, and row-level exception records.

- [ ] **Step 1: Write failing quality-rule tests**

Create test tables covering:

- duplicate `record_id`;
- invalid timestamp;
- missing required field;
- unknown enum;
- successful row without answer;
- inferred recommended fields;
- source count mismatch;
- valid records passing all hard gates.

Assert exact codes: `DUPLICATE_RECORD_ID`, `INVALID_EVENT_TIME`, `MISSING_REQUIRED_FIELD`, `UNKNOWN_ENUM`, `SUCCESS_WITHOUT_OUTPUT`, `SOURCE_COUNT_MISMATCH`.

- [ ] **Step 2: Implement quality evaluation with no silent coercion**

`QualityEngine.evaluate()` must:

- scan all staging parts;
- calculate total rows, unique rows, required-field null rates, timestamp validity, enum validity, recommended-field coverage, inferred-field rates, and source/export reconciliation;
- write row-level exceptions to `quality/exceptions.parquet`;
- set `release_allowed=False` if any hard code occurs;
- set `release_allowed=False` if timestamp validity is below `0.999`;
- treat missing recommended fields as warnings, not hard failures;
- return Decimal rates rounded to six decimal places.

- [ ] **Step 3: Add the upstream anonymization contract guard**

Implement a narrow detector for obvious contract violations only: email addresses, Chinese mainland mobile numbers, and 18-character Chinese ID patterns. It must quarantine matching records with `UPSTREAM_ANONYMIZATION_CONTRACT_VIOLATION` and block release. Document in code that this check is not the corporate anonymization solution.

Tests must use fictional patterns and prove that placeholders such as `[PHONE_1]` and `[EMAIL_1]` are not flagged.

- [ ] **Step 4: Run rule and release-gate tests**

Run: `pytest tests/unit/test_quality.py tests/integration/test_quality_release_gate.py -q`

Expected: all tests PASS; every hard-failure fixture returns `release_allowed=False`, and the valid fixture returns true.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/cs_ops/quality.py tests/unit/test_quality.py tests/integration/test_quality_release_gate.py
git commit -m "feat: enforce deterministic data quality gates"
```

## Task 5: Immutable Audit Export, Weekly CSV Partitions, and Manifest

**Files:**
- Create: `src/cs_ops/export.py`
- Create: `schemas/interaction-v1.schema.json`
- Create: `tests/unit/test_export.py`
- Create: `tests/integration/test_manifest.py`

**Interfaces:**
- Consumes: release-allowed `QualityResult`, `ExtractionResult`, and `Sequence[KnowledgeBaseRecord]` from the monthly snapshot endpoint.
- Produces: `ExportManifest`, full Parquet audit data, weekly UTF-8 CSV partitions, a knowledge-base snapshot CSV, and JSON manifest.

- [ ] **Step 1: Write failing export tests**

Assert that `AuditExporter.publish()`:

- refuses a `QualityResult` with `release_allowed=False`;
- creates one complete Parquet file;
- partitions CSV by Monday-starting business week without splitting a session;
- writes UTF-8 with a header and RFC 4180 quoting;
- includes every file in the manifest with row count, byte size, and SHA-256;
- writes `kb_snapshot_<period>.csv` with version and effective-time fields;
- does not overwrite an existing successful `export_id` directory.

- [ ] **Step 2: Implement the canonical JSON schema**

Generate `schemas/interaction-v1.schema.json` from `InteractionRecord.model_json_schema()` and commit the generated file. Add a test asserting the committed schema equals the runtime-generated schema so contract changes are explicit in Git.

- [ ] **Step 3: Implement immutable publishing**

Publish under:

```text
exports/<period>/<export_id>/
  interactions_<period>.parquet
  interactions_<period>_w01.csv
  feedback_<period>.csv
  kb_snapshot_<period>.csv
  export_manifest_<period>.json
```

Write files to a sibling `.partial` directory, verify hashes and counts, then atomically rename it to the final directory. The manifest must include `export_id`, schema version, extraction window, source count, exported count, quality result summary, created timestamp, code version from `importlib.metadata.version("cs-ops")`, and file entries.

- [ ] **Step 4: Verify manifest determinism and immutability**

Run: `pytest tests/unit/test_export.py tests/integration/test_manifest.py -q`

Expected: all tests PASS. Rebuilding from the same canonical input produces identical data-file hashes; only run metadata fields may differ.

- [ ] **Step 5: Commit Task 5**

```bash
git add src/cs_ops/export.py schemas/interaction-v1.schema.json tests/unit/test_export.py tests/integration/test_manifest.py
git commit -m "feat: publish immutable audit exports"
```

## Task 6: Exception-Complete and Stratified Strong-Model Batches

**Files:**
- Create: `src/cs_ops/batching.py`
- Create: `prompts/ops-analysis-v1.md`
- Create: `tests/unit/test_batching.py`
- Create: `tests/integration/test_batch_coverage.py`

**Interfaces:**
- Consumes: `ExportManifest`, `QualityResult`, and full interaction Parquet.
- Produces: `BatchManifest` and model-ready CSV files with stable selection reasons.
- Produces: a fixed `OPS-ANALYSIS-v1` prompt that requires evidence-linked `finding-candidate-v1` JSONL and prohibits model-generated KPI recalculation or confirmed statuses.

- [ ] **Step 1: Write failing selection tests**

Create records for every mandatory inclusion category:

- negative feedback;
- complaint;
- handoff;
- non-`NONE` fallback;
- empty/system-error/unknown output;
- repeated failure key;
- deterministic high-risk code.

Add normal records across multiple QA IDs, channels, weeks, and knowledge-base versions. Assert every mandatory record is selected and normal selection is reproducible with seed `20260711`.

- [ ] **Step 2: Implement deterministic selection**

`BatchPlanner.build()` must:

- include all mandatory exception records;
- group normal records by `(matched_qa_id or "NO_QA_ID", channel, kb_version or "NO_KB_VERSION", interaction_scope, business_week)`;
- select `max(ceil(group_size * normal_sample_rate), min(group_size, min_normal_samples_per_qa))` normal rows from each group;
- use `record_id` SHA-256 ordering instead of a runtime random generator;
- attach `selection_reason` as a semicolon-separated controlled list;
- never select the same `record_id` twice.

- [ ] **Step 3: Implement session-safe batching**

Sort selected sessions by earliest event time. Add whole sessions until the next session would exceed `max_turns_per_batch`; then begin a new batch. If one session alone exceeds the limit, put it in its own batch and mark `oversized_session=true`.

Write `analysis_batch_001.csv` and `batch_manifest.csv`. Create `prompts/ops-analysis-v1.md` with the required input fields, allowed analysis tasks, prohibited actions, JSONL output contract, and a statement that a finding without evidence record IDs is invalid. The prompt must require every finding to label `interaction_scope` and state that `MULTI_TURN` findings are not eligible for direct single-turn UAT regression projection. The manifest must prove:

- all mandatory records are covered;
- selected record IDs are unique;
- selected count equals the sum of batch counts;
- every selected record maps to exactly one batch.

- [ ] **Step 4: Run selection and coverage tests**

Run: `pytest tests/unit/test_batching.py tests/integration/test_batch_coverage.py -q`

Expected: all tests PASS for empty months, small groups, a 3,001-turn session, and mixed exception/normal data.

- [ ] **Step 5: Commit Task 6**

```bash
git add src/cs_ops/batching.py prompts/ops-analysis-v1.md tests/unit/test_batching.py tests/integration/test_batch_coverage.py
git commit -m "feat: create traceable model analysis batches"
```

## Task 7: Data-Quality Excel Workbook

**Files:**
- Create: `src/cs_ops/dq_workbook.py`
- Create: `tests/unit/test_dq_workbook.py`
- Create: `tests/integration/test_dq_workbook_values.py`

**Interfaces:**
- Consumes: `ExportManifest` and `QualityResult`.
- Produces: `data_quality_report_<period>.xlsx` with eight specified sheets.

- [ ] **Step 1: Write a failing workbook structure test**

Assert the exact sheet order:

```python
EXPECTED_SHEETS = [
    "00_使用说明",
    "01_Export_Manifest",
    "02_Reconciliation",
    "03_Field_Completeness",
    "04_Duplicates",
    "05_Session_Rebuild",
    "06_KB_Linkage",
    "07_Exceptions",
    "08_Schema_Changes",
]
```

The list contains nine sheets because the user guide is additional to the eight quality-detail sheets in the design.

- [ ] **Step 2: Implement workbook generation**

Use openpyxl in write-only mode for detail sheets. Apply:

- frozen top row;
- filters on tabular sheets;
- ISO date formatting;
- red fill for hard failures, amber for warnings, green for passed gates;
- a visible `RELEASE_ALLOWED` value on `00_使用说明` and `02_Reconciliation`;
- no raw full interaction text except the minimal anonymized exception evidence required for diagnosis.

- [ ] **Step 3: Verify formulas, values, and workbook integrity**

Tests must reopen the file with `data_only=False`, assert the sheet order, verify manifest counts and hard-failure codes, and scan cell formulas for `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, and `#N/A`.

Run: `pytest tests/unit/test_dq_workbook.py tests/integration/test_dq_workbook_values.py -q`

Expected: all tests PASS and the generated workbook opens without repair warnings.

- [ ] **Step 4: Commit Task 7**

```bash
git add src/cs_ops/dq_workbook.py tests/unit/test_dq_workbook.py tests/integration/test_dq_workbook_values.py
git commit -m "feat: generate data quality workbook"
```

## Task 8: Strong-Model Finding Contract and Safe Import

**Files:**
- Create: `schemas/finding-candidate-v1.schema.json`
- Create: `src/cs_ops/findings.py`
- Create: `tests/fixtures/finding_candidates.jsonl`
- Create: `tests/unit/test_findings.py`

**Interfaces:**
- Consumes: strong-model JSONL files containing evidence-linked candidates.
- Produces: normalized `FindingsImportResult` and `findings_candidates.parquet` with every status forced to `PENDING_BUSINESS_REVIEW`.

- [ ] **Step 1: Define the finding candidate fixture and failing tests**

Use fields:

```json
{
  "schema_version": "finding-candidate-v1",
  "finding_id": "F-202607-0001",
  "batch_id": "BATCH-001",
  "record_ids": ["R-1"],
  "issue_type": "POSSIBLE_WRONG_ROUTE",
  "severity_candidate": "P1",
  "evidence_summary": "The response appears unrelated to the reset request.",
  "root_cause_hypothesis": "Intent confusion",
  "recommended_action": "Review QA-17 and QA-18",
  "proposed_test_inputs": ["I cannot sign in after resetting my password"],
  "interaction_scope": "SINGLE_TURN",
  "uat_translation_eligibility": "REVIEW_REQUIRED",
  "model_name": "company-strong-model",
  "prompt_version": "OPS-ANALYSIS-v1"
}
```

Tests must reject unknown schemas, missing record IDs, duplicate finding IDs, record IDs absent from the batch manifest, and any `MULTI_TURN` finding marked as eligible for direct single-turn UAT regression. Tests must also prove that a valid single-turn candidate remains `PENDING_BUSINESS_REVIEW` after import.

- [ ] **Step 2: Implement the importer and hard status override**

Even if a JSONL row contains `status`, ignore it and set:

```python
status = FindingStatus.PENDING_BUSINESS_REVIEW
source = FindingSource.STRONG_MODEL
```

Store `interaction_scope` and `uat_translation_eligibility` with the candidate. The importer must never create a frozen UAT case. A later human-reviewed export may create a v1.4 `03_Candidate_Cases` draft with `generator_run_id="OPS-<period>-<export_id>"`, `business_approval=PENDING`, `compliance_approval=PENDING` for sensitive cases, and evidence IDs in `review_note`.

Write valid candidates to Parquet and rejected rows to `finding_import_errors.csv` with file name, line number, error code, and message. The import returns nonzero only when at least one row is rejected.

- [ ] **Step 3: Generate and lock the JSON schema**

Generate `schemas/finding-candidate-v1.schema.json` from `FindingCandidate`. Add a test comparing the committed schema with runtime generation.

- [ ] **Step 4: Run finding-import tests**

Run: `pytest tests/unit/test_findings.py -q`

Expected: all tests PASS and no model-supplied row can become `CONFIRMED`, `REMEDIATED`, or `CLOSED`.

- [ ] **Step 5: Commit Task 8**

```bash
git add schemas/finding-candidate-v1.schema.json src/cs_ops/findings.py tests/fixtures/finding_candidates.jsonl tests/unit/test_findings.py
git commit -m "feat: import model findings as review candidates"
```

## Task 9: Monthly PDF and Excel Report Builders

**Files:**
- Create: `src/cs_ops/monthly_report.py`
- Create: `tests/unit/test_monthly_report.py`
- Create: `tests/integration/test_monthly_report_artifacts.py`

**Interfaces:**
- Consumes: deterministic KPI tables, data-quality results, finding candidates, and a separate human-review decisions CSV.
- Produces: `monthly_report_<period>.pdf`, `monthly_report_<period>.xlsx`, and `MonthlyReportArtifacts`.

- [ ] **Step 1: Write failing KPI-status separation tests**

Build a fixture containing one pending model candidate, one rejected candidate, and one human-confirmed error. Assert:

- confirmed-error KPI numerator is 1;
- candidate count is 2 before review and remains separate;
- rejected findings never enter the confirmed numerator;
- only a human-review CSV may set `CONFIRMED`, and it must include reviewer and reviewed timestamp.

- [ ] **Step 2: Implement the monthly Excel workbook**

Create these sheets in exact order:

```python
[
    "00_使用说明",
    "01_Data_Quality",
    "02_KPI_Summary",
    "03_QA_Performance",
    "04_Exceptions",
    "05_Customer_Feedback",
    "06_KB_Recommendations",
    "07_Regression_Cases",
    "08_Action_Tracker",
    "09_Definitions",
]
```

Calculate KPI values from deterministic tables, never from generated prose. Include `finding_id`, evidence IDs, source, candidate severity, interaction scope, UAT translation eligibility, human status, reviewer, action owner, target date, and regression status. The `07_Regression_Cases` sheet may contain only human-confirmed `SINGLE_TURN` draft candidates; it must retain the UAT v1.4 fields (`generator_run_id`, `test_family`, proposed route/QA ID, approvals, and evidence note) and explicitly state “not frozen / not executable”.

- [ ] **Step 3: Implement the 8–12 page PDF**

Use ReportLab with sections matching the design: executive summary, data quality, service performance, knowledge-base performance, customer feedback, risks, remediation, and next-month priorities. Render only anonymized representative evidence and cap examples at five per finding category.

The cover page must display period, `export_id`, knowledge-base versions, report status `DRAFT` or `APPROVED`, generated timestamp, and reviewer. A report cannot be marked `APPROVED` without reviewer and reviewed timestamp.

- [ ] **Step 4: Verify report artifacts**

Tests must use the Task 1 `pypdf` development dependency to:

- reopen the Excel workbook and verify all sheets and KPI values;
- parse the PDF with `pypdf` added to dev dependencies and verify all eight section headings;
- assert raw full-export file paths do not appear as email attachment names;
- assert pending candidates are visibly labeled “待业务确认”.

Run: `pytest tests/unit/test_monthly_report.py tests/integration/test_monthly_report_artifacts.py -q`

Expected: all report tests PASS.

- [ ] **Step 5: Commit Task 9**

```bash
git add src/cs_ops/monthly_report.py tests/unit/test_monthly_report.py tests/integration/test_monthly_report_artifacts.py
git commit -m "feat: build reviewed monthly reports"
```

## Task 10: Deterministic Daily Alerts and SMTP Delivery

**Files:**
- Create: `src/cs_ops/alerts.py`
- Create: `tests/unit/test_alerts.py`
- Create: `tests/integration/test_email_delivery.py`

**Interfaces:**
- Consumes: quality findings, deterministic operational metrics, report artifacts, and controlled thresholds.
- Produces: `AlertCandidate` records and SMTP messages to business and IT recipients.

- [ ] **Step 1: Write failing deterministic-alert tests**

Test alert codes:

- `EMPTY_OR_SYSTEM_ERROR_SPIKE`;
- `UNAPPROVED_OUTPUT` in strict-whitelist mode;
- `PROHIBITED_QA_ID_FOR_HIGH_RISK_INTENT`;
- `FALLBACK_RATE_SPIKE`;
- `HANDOFF_RATE_SPIKE`;
- `NEGATIVE_FEEDBACK_RATE_SPIKE`;
- `DATA_PIPELINE_RELEASE_BLOCKED`.

Assert every automatically generated semantic label contains “候选” and never “已确认”.

- [ ] **Step 2: Implement rule evaluation**

Use exact configured thresholds and baseline windows from configuration. The evaluator receives precomputed daily metrics and emits structured `AlertCandidate` records with code, observed value, threshold, evidence IDs, run ID, and severity candidate. Do not call an LLM or external classification service.

- [ ] **Step 3: Implement SMTP messages with attachment controls**

Use `smtplib.SMTP_SSL` when `smtp_port=465`, otherwise STARTTLS. Read password from `mail.password_env`. For daily alerts, attach no interaction file. For monthly delivery, allow only `.pdf` and `.xlsx` paths returned by `MonthlyReportArtifacts`; include the controlled storage location for full exports in the message body.

- [ ] **Step 4: Test delivery without a real mail server**

Patch `smtplib.SMTP_SSL` and assert recipients, subject, MIME types, and filenames. Verify `.csv`, `.parquet`, `.jsonl`, and `.zip` attachments raise `UnsafeAttachmentError`.

Run: `pytest tests/unit/test_alerts.py tests/integration/test_email_delivery.py -q`

Expected: all alert and mail tests PASS.

- [ ] **Step 5: Commit Task 10**

```bash
git add src/cs_ops/alerts.py tests/unit/test_alerts.py tests/integration/test_email_delivery.py
git commit -m "feat: send deterministic alerts and report email"
```

## Task 11: Daily, Weekly, and Monthly Orchestration CLI

**Files:**
- Create: `src/cs_ops/pipeline.py`
- Create: `src/cs_ops/cli.py`
- Create: `tests/unit/test_cli.py`
- Create: `tests/integration/test_pipeline.py`

**Interfaces:**
- Consumes: all prior components.
- Produces: `cs-ops daily`, `weekly`, `monthly`, `import-findings`, and `deliver-report` commands with stable exit codes.

- [ ] **Step 1: Write failing CLI contract tests**

Test commands and exit codes:

```text
0  success
2  configuration error
3  source unavailable
4  data contract or quality release blocked
5  finding import rejected
6  report generation failed
7  email delivery failed
```

Assert `cs-ops --help` lists all five commands and that no command exposes a write-back, knowledge-base update, or production configuration mutation option.

- [ ] **Step 2: Implement the daily pipeline**

`Pipeline.daily(as_of)` must:

1. Read the last successful daily checkpoint.
2. Apply a 48-hour lookback without duplicating released records.
3. Start a run.
4. Extract, evaluate quality, and either publish or block.
5. Generate data-quality workbook and deterministic alerts.
6. Mark success only after artifact verification.
7. Mark failure with the exact error code on any exception.

- [ ] **Step 3: Implement weekly and monthly pipelines**

`Pipeline.weekly(week)` builds high-risk and normal-control batches from already released daily data. `Pipeline.monthly(period)` freezes the month, processes late arrivals, fetches the effective knowledge-base snapshot through `KnowledgeBaseSource.snapshot()`, publishes full audit files including `kb_snapshot_<period>.csv`, builds batches, and creates the quality workbook. Neither command invokes a model.

`import-findings` validates manually saved strong-model JSONL. `deliver-report` requires the report status `APPROVED` and sends PDF/Excel only.

- [ ] **Step 4: Implement structured logs**

Emit one JSON object per log line with keys `timestamp`, `level`, `run_id`, `event`, `period`, `export_id`, `record_count`, and `error_code`. Do not log customer text, tokens, SMTP passwords, or API authorization headers.

- [ ] **Step 5: Run CLI and pipeline tests**

Run: `pytest tests/unit/test_cli.py tests/integration/test_pipeline.py -q`

Expected: all tests PASS, blocked quality exits with 4, and the checkpoint does not advance on failure.

- [ ] **Step 6: Commit Task 11**

```bash
git add src/cs_ops/pipeline.py src/cs_ops/cli.py tests/unit/test_cli.py tests/integration/test_pipeline.py
git commit -m "feat: orchestrate customer service operations runs"
```

## Task 12: End-to-End Acceptance, 100k Load Test, CI, and Runbook

**Files:**
- Create: `tests/integration/test_end_to_end.py`
- Create: `tests/load/generate_interactions.py`
- Create: `tests/load/test_100k_pipeline.py`
- Create: `.github/workflows/cs-ops-tests.yml`
- Create: `docs/runbooks/ai-customer-service-operations.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the complete application.
- Produces: acceptance evidence, reproducible load data, CI, and operating instructions for IT and business users.

- [ ] **Step 1: Write the end-to-end acceptance test**

Use an in-process fake source with one week of deterministic anonymized records. Execute extraction, quality, export, batching, data-quality workbook, finding import, monthly report draft, human-review import, approved report, and mocked email delivery.

Assert the final confirmed finding traces to:

- an original `record_id`;
- one source page;
- one Parquet audit row;
- one model batch;
- one `finding_id`;
- one reviewer decision;
- one regression-case row.

- [ ] **Step 2: Build a reproducible 100,000-row generator**

`tests/load/generate_interactions.py` must accept `--rows`, `--sessions`, and `--seed`, generate only fictional anonymized placeholders, and write Parquet directly. Default command:

```bash
python tests/load/generate_interactions.py --rows 100000 --sessions 25000 --seed 20260711
```

Do not commit the generated 100k data file.

- [ ] **Step 3: Add the load acceptance test**

The test must verify:

- 100,000 input rows equal 100,000 exported rows;
- no duplicate `record_id`;
- all mandatory exception rows are selected;
- no session is split across model batches;
- every manifest hash verifies;
- peak process memory and elapsed time are printed to test output.

Set provisional acceptance targets of less than 30 minutes and less than 4 GiB RSS on the IT reference runner. If the reference runner differs, IT may tighten but not loosen these values without recording the reason in the runbook.

- [ ] **Step 4: Add CI for unit and integration tests**

Create `.github/workflows/cs-ops-tests.yml` to run on pull requests and pushes to `main` with Python 3.11. Steps: checkout, setup-python, install `.[dev]`, `ruff check .`, and `pytest tests/unit tests/integration -q`. Do not run the 100k load test in standard CI.

- [ ] **Step 5: Write the operating runbook**

Document exact commands for:

```bash
cs-ops daily --as-of 2026-07-15T00:00:00Z --config config/cs_ops.yml
cs-ops weekly --week 2026-W29 --config config/cs_ops.yml
cs-ops monthly --period 2026-07 --config config/cs_ops.yml
cs-ops import-findings --period 2026-07 --input findings/ --config config/cs_ops.yml
cs-ops deliver-report --period 2026-07 --config config/cs_ops.yml
```

Include recovery steps for every exit code, checkpoint rollback rules, artifact locations, human review procedure, stable-period transition criteria, and a statement that the scheduler is managed by IT outside this repository.

- [ ] **Step 6: Update the repository README**

Add an “上线后数据质量运营” section linking to the design, implementation plan, runbook, configuration example, and CLI help. Keep the existing UAT execution instructions unchanged.

- [ ] **Step 7: Run the complete verification suite**

Run:

```bash
ruff check .
pytest tests/unit tests/integration -q
python tests/load/generate_interactions.py --rows 100000 --sessions 25000 --seed 20260711
pytest tests/load/test_100k_pipeline.py -q -s
git diff --check
```

Expected: lint exits 0; unit and integration tests report 0 failures; load test reports 100,000 rows with verified hashes and resource use within the provisional targets; Git diff check prints no errors.

- [ ] **Step 8: Commit Task 12**

```bash
git add .github/workflows/cs-ops-tests.yml README.md docs/runbooks tests/integration/test_end_to_end.py tests/load
git commit -m "test: verify customer service operations pipeline"
```

## 2. Delivery Sequence and Review Gates

Implement the tasks in order because each task consumes locked interfaces from earlier tasks. Use one review gate after each task commit. Do not combine Task 1–6 into a single pull request without explicit reviewer approval.

Recommended delivery groups:

1. Tasks 1–3: source contract and repeatable extraction.
2. Tasks 4–5: deterministic release gates and full audit export.
3. Tasks 6–7: strong-model batch preparation and data-quality workbook.
4. Tasks 8–10: finding import, reporting, and email.
5. Tasks 11–12: orchestration, acceptance, load evidence, CI, and runbook.

Every group must pass its own tests before work begins on the next group. The first production-like connection occurs only after Tasks 1–5 pass against one week of company-provided anonymized sample data.

## 3. Implementation Completion Criteria

Implementation is complete only when all of the following are evidenced:

- The read-only source adapter makes GET requests only.
- A failed hard quality gate cannot advance a checkpoint or publish a formal data package.
- Source count, exported count, batch count, and manifest counts reconcile exactly.
- All exception records enter a model batch and normal sampling is reproducible.
- Model findings cannot self-promote to confirmed status.
- Multi-turn findings remain analytically traceable but cannot enter the single-turn UAT regression export without a separately approved multi-turn test design.
- A human-confirmed single-turn finding can be traced to a v1.4 UAT Candidate_Cases draft with evidence, `generator_run_id`, and pending approvals; no pipeline step can freeze or execute it.
- Approved reports attach only PDF and Excel; full exports remain in controlled storage.
- One week of company anonymized sample data passes end-to-end shadow comparison.
- The 100,000-row load test meets the recorded reference-runner limits.
- IT can execute daily, weekly, monthly, import, and delivery commands from the runbook.
- Business can trace one confirmed monthly finding through evidence, review, remediation, and regression UAT.
