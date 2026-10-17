# Phase 2N — Final Preflight Endpoint Audit Report

**Date**: 2026-10-17  
**Status**: `READY_FOR_TASK_A` (Pending 2026-10-18 00:00:00 UTC Reset Boundary)  
**Workspace**: `C:\Users\The Mighty King\Desktop\Final Year Project`  
**Execution Mode**: Offline-Only Audit (Zero OpenRouter HTTP Requests, Zero Tokens Spent, Historical Ledger Preserved)  

---

## 1. Executive Summary

In accordance with the **Phase 2N Final Preflight Endpoint Audit** mandate, an exhaustive offline audit and code reconciliation was conducted on the OpenRouter quota preflight implementation, response schema parser, request accounting, and model validation logic.

### Key Audit Findings & Remediation

1. **Endpoint Correction**: Reconciled the active quota-check implementation from the legacy/undocumented `/api/v1/auth/key` endpoint to OpenRouter's documented key-information endpoint:
   $$\text{GET } \text{https://openrouter.ai/api/v1/key}$$
2. **Strict Fail-Closed Quota Parsing**: Replaced speculative default computations (`max(0, limit - used)`) with rigorous schema validation. The preflight reads `data.free_model_daily_requests.remaining` and halts immediately (`can_proceed=False`, `is_quota_exhausted=True`) on zero quota, missing fields, non-numeric values, malformed JSON, or upstream HTTP errors.
3. **Decoupled Model Availability Claim**: Key metadata preflight queries are recognized as reporting account key status and remaining free request units only—**not model availability**. Model availability, served identity, and $0.00 cost verification are enforced on the first generation call with `allow_fallbacks: False`. Mismatches raise `ModelMismatchError` and halt immediately without silent switching.
4. **Exact-Once Transmission Accounting**: Reverified that `GovernedHTTPClient` reserves exactly one slot before dispatch and finalizes upon response, preventing retries or duplicate queries. Sequential task permission checks pass `provider=None`, guaranteeing zero duplicate metadata transmissions.
5. **Historical Ledger Immutability**: The October 17 historical ledger in `eval/outbound_transmission_ledger.json` remains completely unmodified (54 transmissions / 45 ceiling, 9 excess).
6. **Test Verification**: 9 new mock unit tests passed in `tests/test_preflight_endpoint_audit.py`, and the full regression test suite passed with **148/148 tests passing (100%)**.

---

## 2. Endpoint Verification and Correction

### Documented Endpoint

OpenRouter's official documentation defines the endpoint for inspecting API key metadata, credit usage, rate limits, and free-tier daily quotas as:
```http
GET https://openrouter.ai/api/v1/key
Authorization: Bearer <OPENROUTER_API_KEY>
HTTP-Referer: https://github.com/mas-team/mas
X-Title: MAS Multi-Agent Software Engineering Team
```

### Source Code Modifications

The active implementation was updated across all core modules and test mocks:

| Source File | Line(s) | Prior Implementation | Corrected Implementation |
| :--- | :--- | :--- | :--- |
| `mas/core/llm.py` | 748, 756 | `url = f"{self.base_url.rstrip('/')}/auth/key"`<br>`target="/api/v1/auth/key"` | `url = f"{self.base_url.rstrip('/')}/key"`<br>`target="/api/v1/key"` |
| `mas/core/governor.py` | 17, 384 | Target `/api/v1/auth/key` | Target `/api/v1/key` |
| `scripts/run_phase2m_pilot.py` | 13, 228, 326 | Referenced `/api/v1/auth/key` in comments & logs | Reconciled to `/api/v1/key` |
| `tests/test_transmission_governor_audit.py` | 313, 338 | Mocked `/api/v1/auth/key` | Updated to `/api/v1/key` |
| `tests/test_provider_quota_governor.py` | 169 | Recorded `/api/v1/auth/key` | Updated to `/api/v1/key` |

> [!NOTE]
> Historical ledger events in `eval/outbound_transmission_ledger.json` and historical markdown reports from earlier phases retain their original recorded endpoint strings to preserve audit fidelity and tamper evidence.

---

## 3. Strict Fail-Closed Quota Parsing

### OpenRouter `/api/v1/key` Response Schema

A successful 200 OK response from `GET /api/v1/key` returns:
```json
{
  "data": {
    "label": "mas-pilot-key",
    "usage": 0.0,
    "limit": null,
    "is_free_tier": true,
    "rate_limit": {
      "requests": 10,
      "interval": "10s"
    },
    "free_model_daily_requests": {
      "limit": 50,
      "used": 5,
      "remaining": 45
    }
  }
}
```

### Parsing Logic Implementation in `mas/core/governor.py`

In `ProviderQuotaGovernor.check_upstream_key_status()`, the parsing logic was overhauled to enforce strict fail-closed gating:

```python
# Fail-closed validation of response
is_error = bool(meta.get("error")) or ("status_code" in meta and meta.get("status_code") != 200)
free_reqs = meta.get("free_model_daily_requests")
has_free_reqs = isinstance(free_reqs, dict)
remaining = free_reqs.get("remaining") if has_free_reqs else None
has_valid_remaining = isinstance(remaining, (int, float)) and not isinstance(remaining, bool)

used = free_reqs.get("used", 0) if has_free_reqs else 0
limit = free_reqs.get("limit", 50) if has_free_reqs else 50
is_free_tier = meta.get("is_free_tier", True)

if is_error:
    err_msg = meta.get("error") or f"HTTP {meta.get('status_code')}"
    can_proceed = False
    is_quota_exhausted = True
    stop_reason = f"Upstream key preflight query failed: {err_msg}"
elif not has_free_reqs:
    can_proceed = False
    is_quota_exhausted = True
    stop_reason = "Malformed response: missing 'free_model_daily_requests' object in key metadata."
elif not has_valid_remaining:
    can_proceed = False
    is_quota_exhausted = True
    stop_reason = "Malformed response: missing or invalid 'remaining' field in 'free_model_daily_requests'."
elif remaining <= 0:
    can_proceed = False
    is_quota_exhausted = True
    stop_reason = (
        f"Upstream free-model daily quota exhausted: {used}/{limit} requests used "
        f"({int(remaining)} remaining). Reset in ~{hours_to_reset}h at 00:00:00 UTC."
    )
else:
    can_proceed = True
    is_quota_exhausted = False
    stop_reason = ""
```

### Safety Gating Rules Validated

| Scenario | Response State | `can_proceed` | `is_quota_exhausted` | Runner Action |
| :--- | :--- | :---: | :---: | :--- |
| **Positive Quota** | `remaining > 0` (e.g. 45) | `True` | `False` | Proceeds to Task A execution |
| **Zero Quota** | `remaining == 0` | `False` | `True` | Stops immediately as `STOPPED_PROVIDER_QUOTA` |
| **Missing Object** | Missing `free_model_daily_requests` | `False` | `True` | Stops fail-closed; does not assume quota available |
| **Missing Field** | Missing `remaining` in quota object | `False` | `True` | Stops fail-closed; does not compute `limit - used` |
| **Malformed JSON** | Non-JSON body or missing `data` field | `False` | `True` | Stops fail-closed with decode error message |
| **Auth Error** | HTTP 401 Unauthorized / bad key | `False` | `True` | Stops fail-closed with auth error diagnostics |
| **Server Error** | HTTP 500 / 503 from provider | `False` | `True` | Stops fail-closed without retrying |

---

## 4. Model Availability Decoupling & Strict Fallback Lock

### Decoupling Mandate

The key-information endpoint confirms only that the API key is recognized and has remaining free daily request units. **It does not query the model catalog or verify that `cohere/north-mini-code:free` is currently deployed or serving traffic.**

To maintain research integrity while conserving transmission allowances:
1. **No Outbound Catalog Queries**: A separate `GET /api/v1/models` request is deliberately avoided because it would consume an internal transmission allowance without providing stronger serving guarantees than the generation call itself.
2. **Fixed Model Configuration**: Model selection is locked to `cohere/north-mini-code:free` with `allow_fallbacks: False` explicitly set in the request payload:
   ```json
   "provider": {
     "allow_fallbacks": false
   }
   ```
3. **Served-Identity Verification on Wire Response**:
   When the first generation response arrives, `OpenRouterProvider.generate()` executes:
   ```python
   actual_model = data.get("model")
   if not actual_model:
       raise ModelMismatchError("Missing model metadata: Provider response omitted 'model' field.")
   if not is_model_match(target_model, actual_model):
       raise ModelMismatchError(f"Model mismatch error: Requested '{target_model}', but provider returned '{actual_model}'.")
   ```
4. **Halt on Model Mismatch**: If `ModelMismatchError` occurs, `scripts/run_phase2m_pilot.py` catches it, sets `run_status = "FAILED_MODEL_MISMATCH"`, records the incident in `phase2m_pilot_results.json`, and halts the series without silently switching models.

---

## 5. Offline Test Suite & Regression Verification

### Mock Unit Test Suite: `tests/test_preflight_endpoint_audit.py`

Nine comprehensive mock tests were authored and executed:

```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\The Mighty King\Desktop\Final Year Project
configfile: pyproject.toml
plugins: anyio-4.15.1, langsmith-0.14.4
collected 9 items

tests\test_preflight_endpoint_audit.py .........                         [100%]

============================== 9 passed in 1.23s ==============================
```

- `test_01_endpoint_is_documented_api_v1_key`: Verifies `https://openrouter.ai/api/v1/key` URL and ledger event target.
- `test_02_quota_parsing_positive_remaining_proceeds`: Verifies remaining > 0 allows execution.
- `test_03_quota_parsing_zero_remaining_stops_fail_closed`: Verifies remaining == 0 triggers global stop.
- `test_04_quota_parsing_missing_free_model_daily_requests_stops_fail_closed`: Verifies missing object halts.
- `test_05_quota_parsing_missing_remaining_field_stops_fail_closed`: Verifies missing remaining field halts.
- `test_06_malformed_json_response_stops_fail_closed`: Verifies JSON decode error & missing data envelope halt.
- `test_07_auth_error_stops_fail_closed`: Verifies HTTP 401 triggers fail-closed stop.
- `test_08_exact_once_accounting_no_retries_no_duplicates`: Verifies preflight makes 1 call; task loop with `provider=None` makes 0 extra calls.
- `test_09_model_availability_and_fallback_strictness`: Verifies `allow_fallbacks=False` in payload and `ModelMismatchError` on mismatched model.

### Full Regression Suite Results

```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\The Mighty King\Desktop\Final Year Project
configfile: pyproject.toml
plugins: anyio-4.15.1, langsmith-0.14.4
collected 148 items

tests\test_adaptive_stopping_phase2f.py ........                         [  5%]
tests\test_api.py ..                                                     [  6%]
tests\test_ast_analysis.py ...                                           [  8%]
tests\test_change_request.py ..                                          [ 10%]
tests\test_context_slicer.py ..                                          [ 11%]
tests\test_end_to_end_cp1.py ..                                          [ 12%]
tests\test_evaluation_runner.py ..                                       [ 14%]
tests\test_fault_injection.py ..                                         [ 15%]
tests\test_fault_recovery.py .                                           [ 16%]
tests\test_level1_evaluator_protocol.py .......                          [ 20%]
tests\test_neutral_evaluator.py ......                                   [ 25%]
tests\test_openrouter_error_handling.py ......                           [ 29%]
tests\test_phase2g_collaboration_and_generalization.py ........          [ 34%]
tests\test_pilot_runner_audit.py .....                                   [ 37%]
tests\test_preflight_endpoint_audit.py .........                         [ 43%]
tests\test_provider_quota_governor.py .......                            [ 48%]
tests\test_quality_gates_phase2c.py ................                     [ 59%]
tests\test_quality_tools.py ...                                          [ 61%]
tests\test_research_validity.py .............................            [ 81%]
tests\test_router.py .....                                               [ 84%]
tests\test_schemas.py .......                                            [ 89%]
tests\test_statistics.py ...                                             [ 91%]
tests\test_token_logger.py ..                                            [ 92%]
tests\test_transmission_governor_audit.py ...........                    [100%]

====================== 148 passed, 2 warnings in 30.35s =======================
```

### Historical Ledger Verification

The historical October 17 ledger record in `eval/outbound_transmission_ledger.json` was verified:
- `total_outbound_http_transmissions`: **54**
- `internal_daily_cap`: **45**
- `cap_breached`: **true**
- `breach_excess_transmissions`: **9**
- Historical entries, sequences, timestamps, and endpoint strings are **completely unmodified**.

---

## 6. Offline Verification of Single-Task Execution Command

To verify that the runner correctly isolates Task A and enforces the pre-reset network freeze without network traffic, the runner was executed with `--slot "Task A"`:

### Command
```powershell
python scripts/run_phase2m_pilot.py --slot "Task A"
```

### Actual Output
```
[MODE] Controlled Single-Task Execution Enabled: Running ONLY Task A (dev_markdown_toc_01)
================================================================================
PHASE 2M — POST-RESET LIVE PILOT EXECUTION AND QUALITY VALIDATION
Configured Model: cohere/north-mini-code:free (Verified Free Tier, $0.00 cost, allow_fallbacks=False)
Safety Ceilings: Max 15 calls/run, Max 60,000 tokens/run, Max 45 HTTP attempts/day (UTC)
================================================================================

[TIME CHECK] Current System UTC Timestamp: 2026-10-17 13:35:28 UTC
[RESET BOUNDARY] Documented Reset Boundary: 2026-10-18 00:00:00 UTC
[BOUNDARY STATUS] Has reset boundary passed?: False

[LEDGER AUDIT] Persistent Ledger (eval/outbound_transmission_ledger.json):
  - Active UTC Date: 2026-10-17
  - Outbound Transmissions Today: 54 / 45
  - Cap Breached Today: True (Excess: 9)
  - Historical October 17 Record: Preserved (54 transmissions / 45 ceiling)

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
STOPPING IMMEDIATELY: Documented reset boundary (2026-10-18 00:00:00 UTC) has NOT passed.
Current UTC time is 2026-10-17 13:35:28 UTC.
Remaining duration until reset: ~10.41 hours (37471 seconds).
Per Section 1 mandate: Zero OpenRouter requests sent (no /api/v1/key, no models, no generation).
Historical October 17 record is preserved unchanged.
No automatic polling or resumption assumed. Runner must be re-executed after 00:00:00 UTC.
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

[Task A - dev_markdown_toc_01] Status: STOPPED_PROVIDER_QUOTA (Pre-reset pause)

[DONE] Saved Phase 2M Pilot State to eval/phase2m_pilot_results.json
```

**Verification Results**:
- Correctly parsed `--slot "Task A"` to select exclusively `dev_markdown_toc_01`.
- Verified UTC timestamp programmatically against `2026-10-18 00:00:00 UTC`.
- Enforced complete pre-reset network freeze: 0 requests to `/api/v1/key`, 0 models requests, 0 generation calls.
- Preserved historical October 17 ledger record intact.

---

## 7. Exact Verified Command for Live Task A Post-Reset

Once the UTC system timestamp reaches or exceeds `2026-10-18 00:00:00 UTC`, live execution of **Task A only** is initiated with:

```powershell
python scripts/run_phase2m_pilot.py --slot "Task A"
```
*(Alternative syntax: `python scripts/run_phase2m_pilot.py --task-id dev_markdown_toc_01`)*

### Post-Reset Execution Sequence for Task A
1. **Timestamp Gate**: Verifies `now_utc >= 2026-10-18 00:00:00 UTC`.
2. **Transmission 1 (Governed Preflight)**: Sends exactly ONE request to `GET https://openrouter.ai/api/v1/key` via `GovernedHTTPClient`.
   - Recorded as Transmission 1 of 45 in the `2026-10-18` ledger.
   - Parses `data.free_model_daily_requests.remaining`.
   - Halts if `remaining <= 0` or response is malformed/unauthorized.
3. **Task Allowance Check**: Confirms remaining internal transmission allowance $\ge 3$ before starting Task A.
4. **Dispatch Permission**: Evaluated with `provider=None` to ensure 0 duplicate preflight queries.
5. **Live Generation**: Dispatches `cohere/north-mini-code:free` with `allow_fallbacks: False`.
   - Verifies actual served model identity on response.
   - Halts safely with `FAILED_MODEL_MISMATCH` if provider switches models.
6. **Level 2 Quality Gate**: Evaluates generated artifacts with `eval/checks/test_dev_markdown_toc_01.py`.
7. **Clean Single-Task Exit**: Stops cleanly after Task A, preserving remaining daily transmission allowance for subsequent human-initiated evaluations.

---

## 8. Final Readiness Declaration

```
READY_FOR_TASK_A
```

- Endpoint corrected to `https://openrouter.ai/api/v1/key`.
- Fail-closed quota parsing implemented and tested.
- Model availability decoupled from key endpoint.
- 148/148 regression tests passing.
- October 17 historical ledger preserved (54 transmissions / 45 ceiling, excess 9).
- Zero live HTTP requests made during this phase.
