"""Small NumPy numeric helpers shared by models, calibration, and metrics.

Kept dependency-light (NumPy only) so the whole Phase 2 model stack runs in CI without the
heavier ``models`` extra.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

Floats = NDArray[np.float64]

_EPS = 1e-12


def as_array(values: object) -> Floats:
    return np.asarray(values, dtype=np.float64)


def sigmoid(x: Floats) -> Floats:
    return 1.0 / (1.0 + np.exp(-x))


def clip01(p: Floats, eps: float = _EPS) -> Floats:
    return np.clip(p, eps, 1.0 - eps)


def logit(p: Floats, eps: float = _EPS) -> Floats:
    q = clip01(p, eps)
    return np.log(q / (1.0 - q))


def fit_logistic_1d(
    x: Floats, y: Floats, *, max_iter: int = 100, tol: float = 1e-8
) -> tuple[float, float]:
    """Fit ``P(y=1) = sigmoid(a*x + b)`` by Newton-Raphson (IRLS).

    Returns ``(a, b)``. Falls back gracefully on a degenerate (separable/constant) problem.
    """
    x = as_array(x)
    y = as_array(y)
    n = x.shape[0]
    if n == 0:
        return 1.0, 0.0

    # Design matrix [x, 1].
    design = np.column_stack([x, np.ones(n)])
    beta = np.zeros(2)
    for _ in range(max_iter):
        eta = design @ beta
        p = clip01(sigmoid(eta))
        w = p * (1.0 - p)
        grad = design.T @ (y - p)
        # Hessian = X^T W X (+ tiny ridge for stability).
        hess = design.T @ (design * w[:, None]) + 1e-8 * np.eye(2)
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:  # pragma: no cover - defensive
            break
        beta = beta + step
        if float(np.max(np.abs(step))) < tol:
            break
    return float(beta[0]), float(beta[1])


def pool_adjacent_violators(y: Floats, weights: Floats | None = None) -> Floats:
    """Isotonic (non-decreasing) fit of ``y`` via the pool-adjacent-violators algorithm.

    ``y`` must already be ordered by the predictor. Returns fitted values, same length.
    """
    y = as_array(y)
    n = y.shape[0]
    if n == 0:
        return y
    w = np.ones(n) if weights is None else as_array(weights)

    # Merge adjacent blocks whenever the monotonicity constraint is violated.
    stack_val: list[float] = []
    stack_w: list[float] = []
    stack_len: list[int] = []
    for j in range(n):
        value = float(y[j])
        weight = float(w[j])
        length = 1
        while stack_val and stack_val[-1] > value:
            prev_val, prev_w, prev_len = stack_val.pop(), stack_w.pop(), stack_len.pop()
            total_w = prev_w + weight
            value = (prev_val * prev_w + value * weight) / total_w
            weight = total_w
            length += prev_len
        stack_val.append(value)
        stack_w.append(weight)
        stack_len.append(length)

    out = np.empty(n)
    pos = 0
    for value, length in zip(stack_val, stack_len, strict=True):
        out[pos : pos + length] = value
        pos += length
    return out
