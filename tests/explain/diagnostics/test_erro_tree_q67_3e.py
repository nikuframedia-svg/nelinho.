"""Q.67.3.E — pin tests for the "blocked" comment in erro_tree.py.

Two assertions:

  1. **Material detector is NOT in the cascade.** ``ErroTreeDetector``
     today only runs Mold / Worker / Overload. A future sprint
     (Q.68.D) will add a material/lot detector when curated lot data
     lands. Until then we pin the absence so an over-eager refactor
     doesn't silently add a stub that always returns "no evidence"
     (which would hide the bloqueio).

  2. **The bloqueio is documented in-code.** The ``ErroTreeDetector``
     ``__init__`` must carry the ``Q.67.3.E`` marker pointing at
     ``Q.68.D``. This is a meta-test against drift: if someone
     rewrites the comment without preserving the issue reference,
     the test trips and the author has to re-acknowledge the
     decision in ``src/sandbox/CLAUDE.md`` / sprint history.
"""

from __future__ import annotations

import inspect
from uuid import UUID

from src.explain.diagnostics.erro_tree import (
    ErroTreeDetector,
    MoldDetector,
    OverloadDetector,
    WorkerDetector,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def test_material_detector_not_in_cascade_q67_3e() -> None:
    """Material detector is intentionally NOT wired — bloqueado por
    falta de material_lot data no curated layer (issue Q.68.D)."""
    # Fake session — ``ErroTreeDetector.__init__`` doesn't touch it.
    detector = ErroTreeDetector(session=object(), tenant_id=_TENANT)

    # The cascade is exactly Mold + Worker + Overload, in that order.
    assert len(detector._detectors) == 3
    assert isinstance(detector._detectors[0], MoldDetector)
    assert isinstance(detector._detectors[1], WorkerDetector)
    assert isinstance(detector._detectors[2], OverloadDetector)

    # No "Material*" detector class anywhere in the cascade.
    names = {type(d).__name__ for d in detector._detectors}
    assert not any("Material" in n for n in names), (
        "Material detector slipped into the cascade — Q.67.3.E says "
        "this is bloqueado pending material_lot ingestion (Q.68.D)."
    )


def test_erro_tree_carries_q67_3e_marker() -> None:
    """Meta-test: the ``ErroTreeDetector`` source must carry the
    Q.67.3.E reference + the Q.68.D pointer so the bloqueio doesn't
    drift away from the code that embodies it."""
    source = inspect.getsource(ErroTreeDetector)

    # Marker — preserves audit trail to the sub-sprint that
    # documented this in-code.
    assert "Q.67.3.E" in source, (
        "ErroTreeDetector lost its Q.67.3.E marker — restore the "
        "comment block in __init__ before merging."
    )

    # Forward reference to the issue/sprint that will unblock it.
    assert "Q.68.D" in source, (
        "ErroTreeDetector lost its Q.68.D forward-reference — the "
        "bloqueio must point at the sprint that will fix it."
    )

    # Spelling-stable phrase so a quick grep finds the bloqueio.
    assert "material_lot" in source, (
        "ErroTreeDetector lost the 'material_lot' phrase — that "
        "exact term is the curated-layer column the detector waits "
        "for; keep it grep-able."
    )
