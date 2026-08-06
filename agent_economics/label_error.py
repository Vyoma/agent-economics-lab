"""How outcome-label error propagates into a cost-normalized decision.

An LLM judge supplies the `acceptable` label. Cost per acceptable outcome divides
by the count of those labels, so the label sits in a denominator and its error is
amplified. This module derives by how much, and states the largest label error a
gate can absorb before its verdict flips.

Every claim below is verified against its own definition by brute force, so the
analysis cannot drift from the code.

    python3 -m agent_economics.label_error

Scope. This is a conditional result: given a judge that errs at rate epsilon, it
says what happens to the decision. It does not measure any judge's error rate, and
it does not claim a rate for any model. Measuring that is separate work.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Workload:
    """Ground-truth state of a labelled workload.

    costs are per task and label-independent: model spend, human review,
    remediation, and incident loss are incurred whether or not the outcome is
    later judged acceptable. values are realized only on acceptable outcomes.
    """

    costs: tuple[float, ...]
    values: tuple[float, ...]
    acceptable: tuple[bool, ...]

    @property
    def n(self) -> int:
        return len(self.costs)

    @property
    def a(self) -> int:
        return sum(self.acceptable)

    @property
    def r(self) -> float:
        """Acceptable rate."""
        return self.a / self.n

    @property
    def C(self) -> float:
        """Total effective cost. Independent of labels."""
        return math.fsum(self.costs)

    def unit_cost(self, labels: tuple[bool, ...] | None = None) -> float:
        """u = C / (number judged acceptable). A ratio metric."""
        judged = sum(labels if labels is not None else self.acceptable)
        return self.C / judged if judged else math.inf

    def net_value(self, labels: tuple[bool, ...] | None = None) -> float:
        """N = (realized value - total cost) / n. A difference metric."""
        use = labels if labels is not None else self.acceptable
        realized = math.fsum(v for v, ok in zip(self.values, use) if ok)
        return (realized - self.C) / self.n


def confusion(truth: tuple[bool, ...], judged: tuple[bool, ...]) -> tuple[int, int]:
    """Return (false accepts, false rejects)."""
    fp = sum(1 for t, j in zip(truth, judged) if j and not t)
    fn = sum(1 for t, j in zip(truth, judged) if t and not j)
    return fp, fn


# --------------------------------------------------------------------------
# Proposition 1. Ratio distortion is exact and governed by Delta / a.
#
#   u_hat / u = a / (a + Delta),    Delta = FP - FN
#
# --------------------------------------------------------------------------
def check_proposition_1(trials: int = 4000) -> float:
    import random

    rng = random.Random(11)
    worst = 0.0
    for _ in range(trials):
        n = rng.randint(4, 40)
        a = rng.randint(1, n)
        truth = tuple([True] * a + [False] * (n - a))
        costs = tuple(round(rng.uniform(0.01, 5.0), 4) for _ in range(n))
        values = tuple(round(rng.uniform(0.0, 20.0), 4) for _ in range(n))
        w = Workload(costs, values, truth)
        judged = tuple(
            (not t) if rng.random() < 0.3 else t for t in truth
        )
        if sum(judged) == 0:
            continue
        fp, fn = confusion(truth, judged)
        delta = fp - fn
        predicted = w.a / (w.a + delta)
        observed = w.unit_cost(judged) / w.unit_cost()
        worst = max(worst, abs(predicted - observed))
    return worst


# --------------------------------------------------------------------------
# Proposition 2. Amplification. With one-directional error at rate epsilon,
# the relative error in u is epsilon / r to first order, so the amplification
# factor of a ratio metric is 1 / r.
# --------------------------------------------------------------------------
def amplification(r: float, epsilon: float) -> tuple[float, float]:
    """Return (exact relative error in u, first-order prediction epsilon / r)."""
    # One-directional false rejects: a_hat = a - epsilon * n
    # rho = |u_hat - u| / u = (a / (a - epsilon n)) - 1 = epsilon / (r - epsilon)
    exact = epsilon / (r - epsilon) if r > epsilon else math.inf
    return exact, epsilon / r


# --------------------------------------------------------------------------
# Proposition 3. Difference metrics do not amplify. The absolute error in N is
# bounded by v_max * epsilon and carries no 1 / r factor.
# --------------------------------------------------------------------------
def check_proposition_3(trials: int = 4000) -> bool:
    import random

    rng = random.Random(23)
    for _ in range(trials):
        n = rng.randint(4, 40)
        a = rng.randint(1, n)
        truth = tuple([True] * a + [False] * (n - a))
        costs = tuple(round(rng.uniform(0.01, 5.0), 4) for _ in range(n))
        values = tuple(round(rng.uniform(0.0, 20.0), 4) for _ in range(n))
        w = Workload(costs, values, truth)
        judged = tuple((not t) if rng.random() < 0.3 else t for t in truth)
        fp, fn = confusion(truth, judged)
        epsilon = (fp + fn) / n
        bound = max(values) * epsilon
        if abs(w.net_value(judged) - w.net_value()) > bound + 1e-9:
            return False
    return True


# --------------------------------------------------------------------------
# Proposition 4. Flip threshold. For a gate u <= tau with relative slack
#
#   s = (tau - u) / u                       (s > 0 means currently passing)
#
# a one-directional false-reject rate epsilon flips the gate exactly when
#
#   epsilon > r * s / (1 + s)      =:  epsilon*
#
# --------------------------------------------------------------------------
def epsilon_star(r: float, s: float) -> float:
    """Largest label error rate that cannot flip the gate."""
    if s <= 0:
        return 0.0
    return r * s / (1.0 + s)


def check_proposition_4() -> float:
    """Compare the closed form against an exact search over integer flips."""
    worst = 0.0
    for n in (20, 50, 100, 200):
        for a in range(2, n):
            r = a / n
            C = 100.0
            u = C / a
            for s in (0.02, 0.05, 0.1, 0.25, 0.5, 1.0):
                tau = u * (1 + s)
                # Smallest integer false-reject count that pushes u above tau.
                flips = None
                for k in range(1, a):
                    if C / (a - k) > tau:
                        flips = k
                        break
                if flips is None:
                    continue
                empirical = flips / n           # the true epsilon at which it flips
                predicted = epsilon_star(r, s)
                # The closed form is continuous; the truth is integer-quantised,
                # so the gap is bounded by one task.
                worst = max(worst, abs(empirical - predicted) - 1.0 / n)
    return max(0.0, worst)


def main() -> int:
    print("=" * 68)
    print("  PROPOSITION CHECKS")
    print("=" * 68)

    p1 = check_proposition_1()
    print(f"  P1  ratio distortion u_hat/u = a/(a+D)      max error {p1:.2e}  "
          f"{'PASS' if p1 < 1e-9 else 'FAIL'}")

    print("  P2  amplification of a ratio metric")
    print(f"      {'r':>6} {'eps':>7} {'exact':>9} {'eps/r':>9} {'ratio':>7}")
    for r in (0.9, 0.5, 0.2, 0.1):
        for eps in (0.01, 0.05):
            exact, pred = amplification(r, eps)
            print(f"      {r:>6.2f} {eps:>7.2%} {exact:>9.2%} {pred:>9.2%} "
                  f"{exact/pred:>7.2f}")

    p3 = check_proposition_3()
    print(f"  P3  difference metric bounded by v_max*eps  "
          f"{'PASS' if p3 else 'FAIL'}")

    p4 = check_proposition_4()
    print(f"  P4  flip threshold eps* = r*s/(1+s)         "
          f"excess over 1-task quantisation {p4:.4f}  "
          f"{'PASS' if p4 < 1e-9 else 'FAIL'}")

    print()
    print("=" * 68)
    print("  COROLLARY: required label accuracy, vs the field norm of ~85%")
    print("=" * 68)
    print(f"  {'accept rate':>12} {'slack':>7} {'eps*':>8} {'required':>10}"
          f"  {'85% norm':>10}")
    print("  " + "-" * 62)
    for r in (0.9, 0.7, 0.5, 0.3, 0.2):
        for s in (0.05, 0.10, 0.25):
            e = epsilon_star(r, s)
            verdict = "sufficient" if e >= 0.15 else "INSUFFICIENT"
            print(f"  {r:>12.0%} {s:>7.0%} {e:>8.2%} {1-e:>9.1%}  {verdict:>12}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
