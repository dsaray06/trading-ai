"""Black-Scholes option pricing and Greeks — pure, deterministic math.

yfinance provides implied volatility per contract but not Greeks, so we compute
them here. Like the technical indicators, this is reproducible and unit-tested
against known closed-form values (docs/03-agents.md §4).

Conventions: continuous compounding, optional dividend yield `q`. Time `t` in
years. Greeks are returned per-contract-share (delta unitless; vega per 1.00 of
volatility, i.e. per 100 vol points; theta per year).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

OptionType = Literal["call", "put"]

_SQRT_2PI = math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def _d1_d2(s: float, k: float, t: float, r: float, sigma: float, q: float) -> tuple[float, float]:
    vol = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / vol
    return d1, d1 - vol


@dataclass(frozen=True)
class OptionMetrics:
    price: float
    delta: float
    gamma: float
    theta: float   # per year
    vega: float    # per 1.00 change in vol
    rho: float
    intrinsic: float
    breakeven: float


def black_scholes_price(
    s: float, k: float, t: float, r: float, sigma: float,
    opt_type: OptionType, q: float = 0.0,
) -> float:
    """Closed-form Black-Scholes price. Falls back to intrinsic for t<=0 or sigma<=0."""
    if t <= 0 or sigma <= 0:
        return max(0.0, (s - k) if opt_type == "call" else (k - s))
    d1, d2 = _d1_d2(s, k, t, r, sigma, q)
    disc_r, disc_q = math.exp(-r * t), math.exp(-q * t)
    if opt_type == "call":
        return s * disc_q * _norm_cdf(d1) - k * disc_r * _norm_cdf(d2)
    return k * disc_r * _norm_cdf(-d2) - s * disc_q * _norm_cdf(-d1)


def option_metrics(
    s: float, k: float, t: float, r: float, sigma: float,
    opt_type: OptionType, q: float = 0.0,
) -> OptionMetrics:
    """Price + Greeks + intrinsic + breakeven for one option."""
    price = black_scholes_price(s, k, t, r, sigma, opt_type, q)
    intrinsic = max(0.0, (s - k) if opt_type == "call" else (k - s))
    breakeven = (k + price) if opt_type == "call" else (k - price)

    if t <= 0 or sigma <= 0:
        delta = (1.0 if s > k else 0.0) if opt_type == "call" else (-1.0 if s < k else 0.0)
        return OptionMetrics(price, delta, 0.0, 0.0, 0.0, 0.0, intrinsic, breakeven)

    d1, d2 = _d1_d2(s, k, t, r, sigma, q)
    disc_r, disc_q = math.exp(-r * t), math.exp(-q * t)
    pdf_d1 = _norm_pdf(d1)
    sqrt_t = math.sqrt(t)

    gamma = disc_q * pdf_d1 / (s * sigma * sqrt_t)
    vega = s * disc_q * pdf_d1 * sqrt_t
    if opt_type == "call":
        delta = disc_q * _norm_cdf(d1)
        theta = (
            -(s * disc_q * pdf_d1 * sigma) / (2 * sqrt_t)
            - r * k * disc_r * _norm_cdf(d2)
            + q * s * disc_q * _norm_cdf(d1)
        )
        rho = k * t * disc_r * _norm_cdf(d2)
    else:
        delta = -disc_q * _norm_cdf(-d1)
        theta = (
            -(s * disc_q * pdf_d1 * sigma) / (2 * sqrt_t)
            + r * k * disc_r * _norm_cdf(-d2)
            - q * s * disc_q * _norm_cdf(-d1)
        )
        rho = -k * t * disc_r * _norm_cdf(-d2)

    return OptionMetrics(
        price=price, delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho,
        intrinsic=intrinsic, breakeven=breakeven,
    )
