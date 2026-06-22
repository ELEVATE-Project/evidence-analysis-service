# Manual Testing Strategy — Relevant-Evidence Threshold (Cap)

**Feature branch:** `feature/relevant-evidence-threshold` · **Implementation notes:** `THRESHOLD_FEATURE_MIGRATION.md` §8
**Goal:** verify that once a `(UUID, Tasks)` pair has `N` evidences tagged `Relevant`, the rest are written as `notValidated` with **no AI call** — and that this is correct under splitting, resume, missing-UUID input, and is a no-op when the feature is off.

---

## 0. Test files (created for this feature)

Under `public/sample-csv/projects/threshold-tests/` (not auto-uploaded at startup — only `sample_input.csv`/`sample_criteria.csv` are):

| File | Shape | Exercises |
|------|-------|-----------|
| `cap_criteria.csv` | 2 tasks → questions (`Tasks,Question`) | Shared criteria for all inputs below |
| `cap_basic_input.csv` | 1 user, 1 task, **6** image evidences | Basic cap; oversized single group stays whole |
| `cap_multi_input.csv` | user-001 (t1×4, t2×3), user-002 (t1×5, t2×1) = 13 rows | Cap is **per (user, task)**, independent counters |
| `cap_groupsplit_input.csv` | 5 users, group sizes 1/2/3/4/6/**12**, rows **interleaved/unsorted** = 28 rows | Sort + group-aware splitting; oversized-group warning |
| `cap_no_uuid_input.csv` | like basic but **no `UUID` column** | Graceful cap disable |
| `cap_live_input.csv` + `cap_live_criteria.csv` | 1 user/task, **6 fetchable images** (raw.githubusercontent) + an always-"yes" question | Live cap run for Tier 2 (verified) |

All inputs use the canonical column set (`UUID, Declared State, …, Tasks, Task Evidence`) and image (`.jpg`) evidence URLs. The pre-processor never fetches the URLs, so Tier 1 is fully offline. Tiers 2–3 (real AI) need reachable images + API keys (see those sections).

> **Why these shapes:** the processor runs **one worker per split file** and counts `Relevant` per worker. If a `(UUID, Tasks)` group is split across files the cap over-counts — so group-aware splitting is the riskiest part and gets the most direct test (Tier 1).

---

## 1. Prerequisites

```bash
cd ~/Downloads/elevate-latest-pldt/evidence-analysis/service
source venv/bin/activate                 # Python 3.12
git switch feature/relevant-evidence-threshold
TESTS=public/sample-csv/projects/threshold-tests
```

Standalone scripts read the task-column names from env (the service injects these automatically):
`PREPROCESS_QUESTION_TASK_COLUMN=Tasks` (questions CSV) and the input column defaults to `Tasks`.

---

## 2. TIER 1 — Pre-processor: sort + group-aware splitting  ✅ deterministic, no API, no network

This is the **primary** automated-by-hand test. It proves the correctness precondition for the cap.

### 2.1 Group-aware ON — no group may span two files

```bash
OUT=/tmp/cap_ga_on; rm -rf $OUT; mkdir -p $OUT
PREPROCESS_QUESTION_TASK_COLUMN=Tasks PREPROCESS_GROUP_AWARE_SPLIT=true \
python scripts/pre-processor/1-pre-processor.py \
  --input-csv  $TESTS/cap_groupsplit_input.csv \
  --question-csv $TESTS/cap_criteria.csv \
  --output-dir $OUT --split-files yes --rows-per-file 5 --use-school-filter false
```

**Expected console:** `✅ Sorted 28 rows by (UUID, Tasks)…`, an oversized-group warning for the 12-row group (`split_2.csv … >2× target`), and `✅ Validated: All 28 rows written across 3 splits`.

**Verify (the key invariant):**
```bash
python - "$OUT" <<'PY'
import sys, csv, glob, os, json
out = sys.argv[1]; ktf = {}
for fp in sorted(glob.glob(out + "/split_*.csv")):
    for row in csv.DictReader(open(fp)):
        ktf.setdefault((row["UUID"], row["Tasks"]), set()).add(os.path.basename(fp))
leaks = {k: sorted(v) for k, v in ktf.items() if len(v) > 1}
man = json.load(open(out + "/split_manifest.json"))
assert not leaks, f"LEAK: groups span files: {leaks}"
assert man["total_rows"] == man["actual_rows_written"] == 28
assert man["group_aware"] is True
print("PASS: 0 groups span files; 28/28 rows; group_aware=True")
PY
```
**Expected:** `PASS`. (Verified: 28 rows → 3 splits, 0 leaks.)

### 2.2 Group-aware OFF — demonstrates the bug the feature fixes (contrast)

Re-run **without** `PREPROCESS_GROUP_AWARE_SPLIT=true` into `/tmp/cap_ga_off`, then run the same verify script. Because the input is interleaved, the old size-only splitting **spreads several `(UUID, Tasks)` groups across multiple files** (observed: 5 groups span files across 6 splits). This is the exact over-count condition the cap would hit without group-awareness — and confirms Tier 1.1 is meaningful.

---

### 2.3 Other inputs (quick checks, same command, swap `--input-csv`)

| Input | rows-per-file | Expected |
|-------|---------------|----------|
| `cap_basic_input.csv` | 5 | **1** split of 6 rows — the single 6-row group is kept whole (not cut at 5). |
| `cap_multi_input.csv` | 5 | 3 splits; each of the 4 `(user, task)` groups lands in exactly one file; 0 spanning. |
| `cap_no_uuid_input.csv` | 5 | Console logs `⚠️ group-aware splitting requested but UUID/task column missing — falling back to size-only splitting`; splits by size; `group_aware=false` in manifest. |

### 2.4 Regression — feature OFF is byte-identical
Run `cap_groupsplit_input.csv` with the flag unset (Tier 1.2). Manifest `group_aware=false` and the chunking equals the legacy `ceil(rows / rows_per_file)` slicing — i.e. unchanged for any execution that doesn't enable the cap.

---

## 3. TIER 2 — Processor: the cap itself  (needs API keys + reachable images)

The cap only triggers once the model returns `>= threshold` `Relevant` tags, so this tier needs working keys **and images the script can actually fetch + the model accepts**. Three gotchas (all hit during verification):
- **Keys:** auto-loaded from `.env` (`load_dotenv` at the top of the processor). No need to pass them inline. The active provider is whatever `LLM_PROVIDER` is set to.
- **Dead key is fine:** if one `OPENROUTER_API_KEY_*`/`GEMINI_API_KEY_*` is invalid (401), token rotation skips it automatically — not a cap failure.
- **Image host matters:** the downloader is a plain `httpx.get(url)` (no browser user-agent, no redirect-following). Hosts like Wikimedia return **403** to it, so the model receives a corrupt "image" and tags everything `Irrelevant` → the cap never fires. Use a host that serves bytes to a bare GET. `cap_live_input.csv` uses `raw.githubusercontent.com` images, which work. The other `cap_*` inputs use placeholder URLs (fine for Tier 1, not fetchable for Tier 2).

### 3.1 Two-step run (pre-process → process with the cap) — uses `cap_live_*.csv`
```bash
WS=/tmp/cap_proc; rm -rf $WS; mkdir -p $WS/in $WS/out
# 1) pre-process (group-aware ON) and stage the splits as processor input
PREPROCESS_QUESTION_TASK_COLUMN=Tasks PREPROCESS_GROUP_AWARE_SPLIT=true \
python scripts/pre-processor/1-pre-processor.py \
  --input-csv $TESTS/cap_live_input.csv --question-csv $TESTS/cap_live_criteria.csv \
  --output-dir $WS/pre --split-files yes --rows-per-file 100 --use-school-filter false
cp $WS/pre/split_*.csv $WS/in/

# 2) process WITH the cap (threshold = 2)
# NOTE: ENABLE_RELEVANT_CAP no longer exists — MAX_RELEVANT_PER_USER_TASK's presence
# alone is the on/off signal now. RESUME_FROM_CHECKPOINT no longer exists either —
# the script always resumes from whatever checkpoint/partial output it finds (none,
# on a clean $WS, so this first run behaves like a fresh start).
MAX_RELEVANT_PER_USER_TASK=2 \
PROCESSOR_INPUT_TASK_COLUMN=Tasks PROCESSOR_QUESTION_TASK_COLUMN=Tasks \
python scripts/processor/1-main-parallel-script.py \
  --input-dir $WS/in --output-dir $WS/out \
  --final-output-file $WS/final.csv \
  --checkpoint-file $WS/checkpoint.json \
  --api-usage-log-file $WS/api.json \
  --questions-file $TESTS/cap_live_criteria.csv \
  --max-processed-rows 0
```
**Verified result:** 6 rows → `Relevant, Relevant, notValidated×4`; summary shows `notValidated (relevant cap reached, no API call): 4`; only 2 AI calls made.

### 3.2 What to look for
- **Run summary** (end of log): a line `🚫 notValidated (relevant cap reached, no API call): <n>`. For `cap_basic` with threshold 2 and 6 rows where ≥2 are Relevant → `n = 6 − (rows processed before cap)`; capped rows make **no** API call.
- **Startup log:** `Relevant cap ENABLED: max 2 Relevant per (UUID, task)`.

### 3.3 Output invariant (holds regardless of which rows the model tags Relevant)
```bash
python - "$WS/final.csv" 2 <<'PY'
import sys, csv
path, cap = sys.argv[1], int(sys.argv[2])
relevant, capped = {}, 0
for r in csv.DictReader(open(path)):
    key = (r.get("UUID",""), r.get("Tasks",""))
    tag = r.get("Relevance Tag","")
    if tag == "Relevant":     relevant[key] = relevant.get(key,0)+1
    if tag == "notValidated": capped += 1
over = {k:v for k,v in relevant.items() if v > cap}
assert not over, f"FAIL: keys exceeding cap {cap}: {over}"
print(f"PASS: no (UUID,Tasks) exceeds {cap} Relevant; capped(notValidated)={capped}")
PY
```
**Expected:** `PASS` — no `(UUID, Tasks)` ever has more than `MAX_RELEVANT_PER_USER_TASK` `Relevant` rows. Use `cap_multi_input.csv` (threshold 2) to confirm the counters are **independent per (user, task)**: each of `(user-001,t1)`, `(user-001,t2)`, `(user-002,t1)` caps separately.

### 3.4 Resume (kill-and-restart) test
Resume is no longer a toggle — run 3.1, interrupt it (`Ctrl-C`) after a few rows, then re-run the **exact same command unmodified** (no env var needed to turn resume on). Expected: log `[Checkpoint] Restored Relevant counts for K (UUID, task) groups`; already-Relevant rows are not reprocessed; the 3.3 invariant still holds (the counter survived the restart via the checkpoint `cap_key`).

### 3.5 Always-resume regression — `RESUME_FROM_CHECKPOINT=false` is a no-op now
Re-run 3.4's interrupt-then-restart with `RESUME_FROM_CHECKPOINT=false` explicitly set in the shell env. Expected: **no difference** — the script no longer reads this var at all, so it still resumes. (Confirms the toggle was fully removed, not just defaulted differently.)

---

## 4. TIER 3 — Service / API end-to-end

Proves the field travels API → DB (`threshold_config`) → subprocess env.

1. **Create** an execution with the new field:
   ```bash
   curl -X POST http://localhost:8000/api/v1/executions \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"name":"cap-test","csv_type_id":"<type>","evidence_threshold":2}'
   ```
   - **Verify persisted:** `GET /api/v1/executions/{id}` → `threshold_config` contains `"max_relevant_per_user_task": 2` (no `enable_relevant_cap` key anymore — it was removed; presence of the number is the only signal, all the way down to the subprocess env).
   - **Validation:** `evidence_threshold: 0` or `200` → `422` (bounds `1..100`); omitting it → `threshold_config` has no `max_relevant_per_user_task` key at all → cap stays off.
2. Upload `cap_multi_input.csv` (input) + `cap_criteria.csv` (questions), validate, run.
3. **Verify env reached the subprocess:** worker logs show `relevant_cap_enabled execution=<id> max_relevant_per_user_task=2` (service) and `Relevant cap ENABLED` (processor). No `ENABLE_RELEVANT_CAP` env var is set on the subprocess at all anymore — confirm via `ps eww <pid>` or by temporarily logging `processor_env` keys.
4. Download the output and run the §3.3 invariant check.
5. **Resume-across-retries (new behavior):** force the execution to fail mid-run (e.g. kill the celery worker process after a few rows are written, or temporarily break a network call), then re-trigger `POST /executions/{id}/run`. Expected: `resume_skip_cleanup execution=<id> workspace=...` in the logs (workspace was *not* wiped before the retry — this log line fires unconditionally now, not just when an old `PROCESSOR_RESUME_FROM_CHECKPOINT` flag was set), partial output from the failed attempt is reused, and the final output still satisfies the §3.3 cap invariant. On a **successful** run, confirm the workspace directory under `EXECUTION_WORKSPACE_ROOT` is gone afterward (`EXECUTION_CLEANUP_ON_SUCCESS` still wipes it post-success — that part is unchanged).

---

## 5. TIER 4 — Missing-UUID graceful degradation

Run Tier 2 (3.1) but with `--input-csv $TESTS/cap_no_uuid_input.csv`.
**Expected:** pre-processor logs the size-only fallback (§2.3); processor logs `relevant_cap_disabled reason=missing_uuid_column`; **every** row is processed normally and none are `notValidated`. The run never fails over the missing optional column.

---

## 6. TIER 5 — Feature-off regression (must be unchanged)

Create/run an execution **without** `evidence_threshold` (or run the scripts with `MAX_RELEVANT_PER_USER_TASK` simply unset — there's no boolean flag to set false anymore). Expected: no `MAX_RELEVANT_PER_USER_TASK` env var reaches the subprocess at all, no `PREPROCESS_GROUP_AWARE_SPLIT`, size-only splitting, zero `notValidated` rows, output identical to pre-feature behavior.

---

## 7. Results checklist

| # | Tier | Test | Pass criteria | Status |
|---|------|------|---------------|--------|
| 1 | 1 | Group-aware split (groupsplit, GA on) | 0 groups span files; 28/28 rows; `group_aware=true` | ✅ verified offline |
| 2 | 1 | Contrast (GA off) | groups DO span files (shows why feature exists) | ✅ verified offline |
| 3 | 1 | Basic single oversized group | kept whole in 1 file | ✅ verified offline |
| 4 | 1 | Multi per-(user,task) split | each group in one file | ✅ verified offline |
| 5 | 1 | Regression (flag off) | legacy slicing unchanged | ✅ verified offline |
| 6 | 2 | Cap basic (threshold 2) | ≤2 Relevant/key; rest `notValidated`; summary count | ✅ verified live (cap_live: 2 Relevant, 4 notValidated, 2 AI calls) |
| 7 | 2 | Cap multi independence | each (user,task) caps separately | ⬜ needs keys+images |
| 8 | 2 | Resume kill/restart (3.4) | counter restored; no reprocessing; no env var needed | ⬜ needs keys+images |
| 8b | 2 | Always-resume regression (3.5) | `RESUME_FROM_CHECKPOINT=false` has zero effect — var no longer read | ⬜ needs keys+images |
| 9 | 3 | API → DB → subprocess | `threshold_config` has only `max_relevant_per_user_task` (no `enable_relevant_cap` key); bounds 422; env in logs | ⬜ needs running stack |
| 9b | 3 | Resume-across-retries (service-level) | `resume_skip_cleanup` logged on retry; partial output reused; workspace removed after eventual success | ⬜ needs running stack + forced failure |
| 10 | 4 | Missing UUID | cap disabled, all processed, no failure | ⬜ needs keys (logs visible offline at pre-processor) |
| 11 | 5 | Feature off | byte-identical to today; no `MAX_RELEVANT_PER_USER_TASK` reaches subprocess | ✅ split path verified offline |

> Tier 1 + the split-regression are fully verifiable offline and already pass. Tiers 2–4 require API keys, reachable images, and (for Tier 3) the running service; they verify the same cap invariant the offline simulation in `THRESHOLD_FEATURE_MIGRATION.md` §8 already demonstrated against the real branch logic.
