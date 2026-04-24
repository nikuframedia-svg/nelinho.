"""
Tests for src.plan.cpo.frrmab.FRRMAB + the 6 mutation operators.

Coverage:
- Each operator produces a valid chromosome (precedence-safe for decoder
  is handled by the decoder itself, not the mutation operator)
- FRRMAB explores every operator at least once (initial round-robin)
- FRRMAB converges toward the high-reward operator under deterministic
  rewards (c=0.2 keeps exploration low)
- Sliding window and decay: stale rewards fade over time
"""

from __future__ import annotations

import random
from typing import Dict

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.frrmab import (
    DEFAULT_OPERATORS,
    FRRMAB,
    op_flip_routing,
    op_insert_move,
    op_perturb_params,
    op_shift_group,
    op_swap_adjacent,
    op_swap_random,
)


def _chromo(n: int = 10, seed: int = 1) -> Chromosome:
    rng = random.Random(seed)
    return Chromosome.random(n, rng)


class TestOperators:
    def test_swap_adjacent_preserves_elements(self):
        c = _chromo(10)
        original = set(c.permutation)
        rng = random.Random(42)
        out = op_swap_adjacent(c, rng)
        assert set(out.permutation) == original
        assert len(out.permutation) == 10

    def test_swap_random_preserves_elements(self):
        c = _chromo(10)
        original = set(c.permutation)
        rng = random.Random(42)
        out = op_swap_random(c, rng)
        assert set(out.permutation) == original

    def test_insert_move_preserves_elements(self):
        c = _chromo(10)
        original = set(c.permutation)
        rng = random.Random(42)
        out = op_insert_move(c, rng)
        assert set(out.permutation) == original

    def test_flip_routing_preserves_elements(self):
        c = _chromo(10)
        original = set(c.permutation)
        rng = random.Random(42)
        out = op_flip_routing(c, rng)
        assert set(out.permutation) == original

    def test_shift_group_preserves_elements(self):
        c = _chromo(10)
        original = set(c.permutation)
        rng = random.Random(42)
        out = op_shift_group(c, rng)
        assert set(out.permutation) == original

    def test_perturb_params_bounds(self):
        c = Chromosome(permutation=[0, 1, 2], edd_gap=14, buffer_pct=0.1, quality_weight=0.3)
        rng = random.Random(42)
        # Run many times to cover clamp boundaries
        for _ in range(100):
            c = op_perturb_params(c, rng)
            assert 5 <= c.edd_gap <= 30
            assert 0.0 <= c.buffer_pct <= 0.30
            assert 0.0 <= c.quality_weight <= 1.0

    def test_small_permutation_is_robust(self):
        rng = random.Random(42)
        small = Chromosome(permutation=[0])
        # Shouldn't raise on a 1-element permutation
        for fn in (op_swap_adjacent, op_swap_random, op_insert_move, op_flip_routing, op_shift_group):
            out = fn(small, rng)
            assert out.permutation == [0]


class TestFRRMABRoundRobinThenExploitation:
    def test_each_operator_explored_at_least_once(self):
        rng = random.Random(0)
        mab = FRRMAB(rng=rng)
        seen = set()
        for _ in range(len(DEFAULT_OPERATORS)):
            name, _ = mab.select()
            seen.add(name)
            mab.record(name, reward=0.1)
        assert seen == set(DEFAULT_OPERATORS.keys())

    def test_converges_to_high_reward_operator(self):
        """
        Inject synthetic rewards: swap_adjacent always returns 0.5,
        everyone else returns 0.01. After a warm-up period, FRRMAB
        should overwhelmingly pick swap_adjacent.
        """
        rng = random.Random(42)
        mab = FRRMAB(rng=rng, c=0.2, window=200, decay=1.0)

        # Warm up: each op once
        for name in DEFAULT_OPERATORS:
            mab.select()
            mab.record(name, reward=0.01)

        # Main loop: whenever swap_adjacent is selected, give high reward.
        selections: Dict[str, int] = {k: 0 for k in DEFAULT_OPERATORS}
        for _ in range(400):
            name, _ = mab.select()
            selections[name] += 1
            reward = 0.5 if name == "swap_adjacent" else 0.01
            mab.record(name, reward)

        total = sum(selections.values())
        swap_share = selections["swap_adjacent"] / total
        # With c=0.2 exploitation dominates — swap_adjacent should win majority
        assert swap_share > 0.4, f"swap_adjacent share={swap_share:.2f}, selections={selections}"

    def test_record_ignores_unknown_operator(self):
        mab = FRRMAB(rng=random.Random(0))
        mab.record("unknown_op", reward=1.0)
        snap = mab.snapshot()
        assert all(s["plays"] == 0 for s in snap.values())

    def test_snapshot_counts_match_selects(self):
        rng = random.Random(0)
        mab = FRRMAB(rng=rng)
        for _ in range(5):
            name, _ = mab.select()
            mab.record(name, reward=0.1)
        snap = mab.snapshot()
        total_plays = sum(s["plays"] for s in snap.values())
        assert total_plays == 5


class TestFRRMABDecay:
    def test_sliding_window_is_the_decay(self):
        """Sprint C 4.2 FR2 — the per-record multiply-by-decay loop was
        removed because it was O(window) per `record()` call. The
        sliding-window mean (FIFO with maxlen) already decays old
        rewards implicitly: once the window fills, the oldest reward
        falls off on every append.

        So two records of 1.0 give a clean mean of 1.0 — no artificial
        geometric decay is applied anymore.
        """
        rng = random.Random(0)
        mab = FRRMAB(rng=rng, decay=0.5, window=100)  # decay kept for compat
        mab.record("swap_adjacent", reward=1.0)
        mab.record("swap_adjacent", reward=1.0)
        snap = mab.snapshot()
        assert snap["swap_adjacent"]["mean_reward"] == 1.0
        assert snap["swap_adjacent"]["history_len"] == 2

    def test_window_caps_history_at_maxlen(self):
        """The window is the only decay mechanism: when it fills, older
        rewards fall off the front so the running mean reflects only
        recent behaviour.
        """
        rng = random.Random(0)
        mab = FRRMAB(rng=rng, decay=1.0, window=3)
        for r in (0.0, 0.0, 1.0, 1.0, 1.0):
            mab.record("swap_adjacent", reward=r)
        snap = mab.snapshot()
        # Only the last 3 rewards (1, 1, 1) survive the window → mean=1.0
        assert snap["swap_adjacent"]["history_len"] == 3
        assert snap["swap_adjacent"]["mean_reward"] == 1.0
