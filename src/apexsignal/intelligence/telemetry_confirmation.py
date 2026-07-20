"""News proposes, telemetry confirms.

A news event proposes a pace shift with wide uncertainty. Once practice/qualifying pace is
observed (controlled for tyre, fuel, traffic, track evolution — the caller supplies the residual),
we Bayesian-update the proposed effect toward the evidence. The posterior can strengthen, reduce,
or reverse the news adjustment, and the evidence trail is returned.
"""

from __future__ import annotations

from pydantic import BaseModel


class TelemetryConfirmation(BaseModel):
    prior_pace_delta: float
    prior_uncertainty: float
    observed_pace_delta: float
    observation_noise: float
    posterior_pace_delta: float
    posterior_uncertainty: float
    verdict: str  # "confirmed" | "reduced" | "reversed" | "inconclusive"


def confirm_with_telemetry(
    prior_pace_delta: float,
    prior_uncertainty: float,
    observed_pace_delta: float,
    *,
    observation_noise: float = 0.08,
) -> TelemetryConfirmation:
    """Normal-normal Bayesian update of a proposed pace delta given observed residual pace."""
    prior_var = max(1e-6, prior_uncertainty**2)
    obs_var = max(1e-6, observation_noise**2)
    post_prec = 1.0 / prior_var + 1.0 / obs_var
    post_mean = (prior_pace_delta / prior_var + observed_pace_delta / obs_var) / post_prec
    post_sd = post_prec**-0.5

    verdict = _verdict(prior_pace_delta, post_mean)
    return TelemetryConfirmation(
        prior_pace_delta=prior_pace_delta,
        prior_uncertainty=prior_uncertainty,
        observed_pace_delta=observed_pace_delta,
        observation_noise=observation_noise,
        posterior_pace_delta=post_mean,
        posterior_uncertainty=post_sd,
        verdict=verdict,
    )


def _verdict(prior: float, posterior: float) -> str:
    if abs(prior) < 1e-6:
        return "inconclusive"
    if posterior * prior < 0:
        return "reversed"  # posterior flipped sign vs. the news claim
    if abs(posterior) >= abs(prior):
        return "confirmed"  # evidence at least as strong as claimed
    return "reduced"
