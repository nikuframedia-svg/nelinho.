"""Q.68.2.B — Decoder mutation-pin tests (DEFERRED until baseline measured).

Status
======
**Baseline NOT MEASURED.** Per `agent_docs/q68_mutmut_baseline_real.md`:

> `src/plan/cpo/decoder.py` (façade 195L) + decoder_helpers.py (347L) +
> decoder_kpis.py (203L) + decoder_resources.py (546L) = 1291L total —
> status: **pending_first_run**. The Q.66.D decomposition redrew the
> module boundaries AFTER Q.67.3.B created 44 anticipatory pin tests
> (`tests/plan/test_decoder_mutation_pin_q67.py`). Pin effectiveness
> against survivors is **DESCONHECIDA** until `-Module cpo` runs against
> the decomposed tree.

Therefore Q.68.2.B does NOT add new decoder pin tests yet. Adding them
without survivor data would repeat the Q.67.3.B problem (anticipatory
pins not grounded in real mutants). The work order is:

1. Reserve a nocturnal window (≥45 min on Luis' laptop).
2. Run the canonical baseline command:

       pwsh scripts/mutation_test.ps1 -Module cpo

   This sequence runs fitness.py THEN decoder.py with the cache cleared
   between them. Preserve the decoder cache afterwards:

       Copy-Item .mutmut-cache .mutmut-cache.decoder

3. Sample 30 top survivors via `mutmut show <id>` (UTF-8 console:
   `$env:PYTHONIOENCODING="utf-8"` first to avoid the `\\U0001f641`
   `UnicodeEncodeError` from mutmut's print).
4. Classify into the 5 categories from
   `agent_docs/q68_mutmut_baseline_real.md` and add pins HERE with
   explicit mutant IDs in each docstring (the Q.67.3.B file is
   anticipatory; this file MUST be ground-truth).

Until then, this file contains only a single failing-by-skip sentinel
so CI flags the gap.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason=(
        "Q.68.2.B follow-up — decoder.py mutmut baseline not yet measured. "
        "Run `pwsh scripts/mutation_test.ps1 -Module cpo` (~30-40 min), "
        "preserve `.mutmut-cache`, sample top 30 survivors, then port them "
        "here with explicit mutant IDs. Unblocking this skip is the action "
        "item — see agent_docs/q68_mutmut_baseline_real.md §'Próximos "
        "passos operacionais' step 1."
    )
)
def test_decoder_mutmut_pin_q68_2b_pending_first_run():
    """Sentinel: gates the file until decoder.py mutmut baseline exists.

    When the baseline run completes, replace this single sentinel with
    20+ pin tests mirroring the structure of
    `tests/shared/test_decisions_mutmut_pin_q68_2b.py`:

    * Category 1 (magic-number tweak):   weights, _NORM_* constants,
                                          DEFAULT_REWORK_BUFFER_PCT.
    * Category 2 (comparator flip):       `>` ↔ `>=` on duration / capacity
                                          / utilization gates.
    * Category 3 (`or default` removal):  `len(workers) or 1`, `max(1, ...)`,
                                          falsy-field defaults.
    * Category 4 (branch dispatch):       `_empty_result()` early returns,
                                          desmolde branch, batch tail skip.
    * Category 5 (string rename):         phase names (POST_DESMOLDE_*),
                                          axis tags ("makespan", "rework").

    The Q.67.3.B file (`test_decoder_mutation_pin_q67.py`) already covers
    the helper subset that DID NOT move during Q.66.D decomposition; this
    file should target the cross-module wiring introduced by the split
    (decoder.py façade → decoder_helpers / decoder_kpis / decoder_resources).
    """
    raise AssertionError("must not run — guarded by pytest.mark.skip")
