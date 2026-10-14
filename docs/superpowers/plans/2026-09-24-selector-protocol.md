# Selector protocol reliability implementation plan

**Goal:** Complete the user-approved selector fix without silently injecting invalid experiences or launching unqualified full training.

**Architecture:** Preserve embedding/lexical candidates; assign call-local integer IDs and return only `{"selected":[1,2]}`. Validate strictly, derive unselected membership locally, retain original IDs and hashes. Retry protocol errors once; transport failures do not trigger selector retries. A typed string prompt carries a shared 120-second selection deadline through existing usage wrappers into the real requester, with one HTTP attempt per selector call and 256 output tokens. General generation requests retain their settings. No provider JSON-mode assumption.

**Scope:** Only selector protocol/request bounds. No changes to ranking, library, generation prompts, repair feedback, training pools, or Base/Plus. D_grow is development data, not independent quality evidence.

- [x] Add failing tests in `tests/test_semantic_retrieval.py` and `tests/test_requester_isolation.py`: mapping, strict schema, duplicates, malformed/truncated replies, retry exhaustion, empty selection, transport failure, bounded blocking and retained concurrency slots.
- [x] Implement compact protocol in `methods/sct_trajectory/semantic_retrieval.py`; keep traces of every attempt and inferred unselected IDs; add typed policy in `selector_protocol.py`, consumed by `run_closed_loop._requester`.
- [x] Run focused and relevant integration regressions. Preserve old output snapshots.
- [x] Reconstruct all prior semantic queries from frozen D_grow artifacts; verify query/candidate hashes, replay both protocols in randomized paired order using the same cache and shared <=80 slots. Record every failure, latency, selection, and token count. Use fresh diagnostic directory; no prompt selection on test outcomes.
- [x] Run fixed stratified end-to-end training smoke with new protocol; audit mappings/adoption/actual local Function/Secure validation. Reliability success is not proof of Joint improvement.
- [x] Update Chinese report and README with actual results, limits, and the full-training decision. No automatic 874 CLE or Plus on reliability evidence alone.

## Evidence-driven request-control revision

The first stress trial added an excessive 60s per-HTTP cutoff: stopped early with all partial evidence retained. The subsequent complete 486-query replay removed that cutoff but still produced 81 network timeouts at global/selector concurrency 80, with zero format errors. Audit: 6902/6902 checks passed, not a quality success. Therefore add an independent selector sublimit of 16 per requester, inside the shared overall 80 request budget. Selector acquisition and HTTP both consume the existing 120s deadline. Retain both permits until the actual worker exits. General generation settings remain unchanged. Test this full query set again before accepting the configuration; concurrency tuning uses technical failures only, no F/S outcomes.

Additional review requirements: retain allowlisted structured transport diagnostics and individual response token usage before parse validation; adversarial diagnostic content must not mask the original failure. The current 206-test regression set passes after these changes.

## Completion evidence

206 offline regressions passed. Initial mixed protocol stress was explicitly aborted and preserved (290 rows); full short-protocol concurrency80 replay:81/486 network failures, audit6902/6902. Final independent selector limit16 replay:485/486 completed,2 recovered JSON attempts,one network failure,all62 historic failures completed; audit7302/7302. Fixed24-task two-arm e2e:48 rows,semantic41/41 retrieval successes,no semantic pipeline errors; both final Joint7/24,p=1.0. Hierarchical arm has one truncated final output/unmeasured result. Audit1076/1076. Source/input hashes stable during each complete run. No full CLE/Plus launch; no paid processes remain.
