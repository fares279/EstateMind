"""
Simulation REST API views.
All views are CSRF-exempt function-based views returning JSON with CORS headers.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import SimulationRun
from .engine.config import (
    SCENARIOS, SCALE_PRESETS, get_scenario, get_scale, scenarios_list,
)

logger = logging.getLogger("simulation.views")

# ── CORS helpers ──────────────────────────────────────────────────────────────
_CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _json(data: dict, status: int = 200) -> JsonResponse:
    r = JsonResponse(data, status=status)
    for k, v in _CORS.items():
        r[k] = v
    return r


def _preflight() -> HttpResponse:
    r = HttpResponse(status=204)
    for k, v in _CORS.items():
        r[k] = v
    return r


def _err(msg: str, status: int = 400) -> JsonResponse:
    return _json({"error": msg}, status)


# ── Scenario catalogue ─────────────────────────────────────────────────────────
def scenarios_view(request):
    if request.method == "OPTIONS":
        return _preflight()
    return _json({"scenarios": scenarios_list()})


# ── Start simulation ───────────────────────────────────────────────────────────
@csrf_exempt
def start_view(request):
    if request.method == "OPTIONS":
        return _preflight()
    if request.method != "POST":
        return _err("Method not allowed", 405)

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("Invalid JSON body")

    scenario_name    = str(body.get("scenario_name") or body.get("scenario") or "baseline")
    num_months       = max(6, min(60, int(body.get("num_months", 12))))
    agent_scale      = str(body.get("agent_scale", "tiny"))
    seed             = int(body.get("seed", 2026))
    policy_overrides = body.get("policy_overrides") or {}

    if scenario_name not in SCENARIOS:
        return _err(f"Unknown scenario '{scenario_name}'. Valid: {list(SCENARIOS.keys())}")

    if agent_scale not in SCALE_PRESETS:
        agent_scale = "tiny"

    # Sanitise policy_overrides — only numeric values for known scenario keys
    _safe_overrides = {}
    _allowed_keys = {
        "monthly_drift", "demand_multiplier", "credit_approval_rate",
        "bct_rate", "developer_activity", "speculator_activity",
        "investor_multiplier", "coastal_penalty", "price_volatility",
    }
    for k, v in policy_overrides.items():
        if k in _allowed_keys:
            try:
                _safe_overrides[k] = float(v)
            except (TypeError, ValueError):
                pass

    run_id = str(uuid.uuid4())

    try:
        run = SimulationRun.objects.create(
            run_id        = run_id,
            scenario_name = scenario_name,
            agent_scale   = agent_scale,
            num_months    = num_months,
            status        = SimulationRun.STATUS_PENDING,
        )
    except Exception as exc:
        logger.exception("Failed to create SimulationRun")
        return _err(f"Database error: {exc}", 500)

    def _run():
        from .engine.simulator import TunisiaRealEstateSimulator
        from django.db import connections
        try:
            sim = TunisiaRealEstateSimulator(
                run_id           = run_id,
                scenario_name    = scenario_name,
                num_months       = num_months,
                agent_scale      = agent_scale,
                seed             = seed,
                policy_overrides = _safe_overrides,
            )
            sim.run()
        except Exception:
            logger.exception("Background simulation %s crashed", run_id)
        finally:
            connections.close_all()

    t = threading.Thread(target=_run, daemon=True, name=f"sim-{run_id[:8]}")
    t.start()

    return _json({
        "run_id":          run_id,
        "status":          "pending",
        "scenario_name":   scenario_name,
        "num_months":      num_months,
        "agent_scale":     agent_scale,
        "policy_overrides": _safe_overrides,
        "message":         "Simulation started",
    }, 201)


# ── Run list ───────────────────────────────────────────────────────────────────
def runs_list_view(request):
    if request.method == "OPTIONS":
        return _preflight()

    runs_qs = SimulationRun.objects.order_by("-created_at")[:100]
    runs = []
    for r in runs_qs:
        runs.append({
            "run_id":             str(r.run_id),
            "scenario_name":      r.scenario_name,
            "scenario_label":     SCENARIOS.get(r.scenario_name, {}).get("label", r.scenario_name),
            "status":             r.status,
            "num_months":         r.num_months,
            "current_month":      r.current_month,
            "agent_scale":        r.agent_scale,
            "total_transactions": r.total_transactions,
            "progress_pct":       round(r.current_month / max(1, r.num_months) * 100, 1),
            "created_at":         r.created_at.isoformat() if r.created_at else None,
            "completed_at":       r.completed_at.isoformat() if r.completed_at else None,
            "error_message":      r.error_message,
        })

    return _json({"runs": runs, "count": len(runs)})


# ── Run detail / delete ────────────────────────────────────────────────────────
@csrf_exempt
def run_detail_view(request, run_id):
    if request.method == "OPTIONS":
        return _preflight()

    try:
        run = SimulationRun.objects.get(run_id=run_id)
    except SimulationRun.DoesNotExist:
        return _err("Run not found", 404)

    if request.method == "DELETE":
        run.delete()
        return _json({"message": "Deleted", "run_id": str(run_id)})

    latest = {}
    states = run.monthly_states or []
    if states:
        last = states[-1]
        latest = {
            "avg_price":    last.get("avg_price", 0),
            "transactions": last.get("transactions", 0),
            "liquidity":    last.get("liquidity_score", 0),
            "affordability": last.get("affordability_index", 0),
            "interest_rate": last.get("bcb_rate", 0.08),
            "price_growth":  last.get("price_growth_rate", 0),
            "credit_rate":   last.get("credit_rate", 0.55),
        }

    return _json({
        "run_id":               str(run.run_id),
        "scenario_name":        run.scenario_name,
        "scenario_label":       SCENARIOS.get(run.scenario_name, {}).get("label", run.scenario_name),
        "status":               run.status,
        "num_months":           run.num_months,
        "current_month":        run.current_month,
        "progress_pct":         round(run.current_month / max(1, run.num_months) * 100, 1),
        "total_transactions":   run.total_transactions,
        "avg_transaction_price": float(run.avg_transaction_price or 0),
        "agent_scale":          run.agent_scale,
        "latest_metrics":       latest,
        "created_at":           run.created_at.isoformat() if run.created_at else None,
        "started_at":           run.started_at.isoformat() if run.started_at else None,
        "completed_at":         run.completed_at.isoformat() if run.completed_at else None,
        "error_message":        run.error_message,
    })


# ── Timeseries ─────────────────────────────────────────────────────────────────
def timeseries_view(request, run_id):
    if request.method == "OPTIONS":
        return _preflight()

    try:
        run = SimulationRun.objects.get(run_id=run_id)
    except SimulationRun.DoesNotExist:
        return _err("Run not found", 404)

    months = [
        {
            "month":               s.get("month"),
            "avg_price":           s.get("avg_price", 0),
            "transactions":        s.get("transactions", 0),
            "liquidity_score":     s.get("liquidity_score", 0),
            "affordability_index": s.get("affordability_index", 0),
            "price_growth_rate":   s.get("price_growth_rate", 0),
            "active_listings":     s.get("active_listings", 0),
            "bcb_rate":            s.get("bcb_rate", 0.08),
            "credit_rate":         s.get("credit_rate", 0.55),
        }
        for s in (run.monthly_states or [])
    ]

    return _json({"run_id": str(run.run_id), "months": months})


# ── Summary metrics ────────────────────────────────────────────────────────────
def metrics_view(request, run_id):
    if request.method == "OPTIONS":
        return _preflight()

    try:
        run = SimulationRun.objects.get(run_id=run_id)
    except SimulationRun.DoesNotExist:
        return _err("Run not found", 404)

    metrics = run.final_metrics or {}

    if not metrics and run.monthly_states:
        states = run.monthly_states
        prices = [s.get("avg_price", 0) for s in states if s.get("avg_price")]
        first  = prices[0]  if prices else 0
        last   = prices[-1] if prices else 0
        pct    = (last - first) / max(1.0, first) * 100 if first else 0
        metrics = {
            "total_transactions":        run.total_transactions,
            "price_change_pct":          round(pct, 2),
            "final_avg_price":           round(last, 2),
            "initial_avg_price":         round(first, 2),
            "peak_monthly_transactions": max((s.get("transactions", 0) for s in states), default=0),
            "avg_affordability":         round(
                sum(s.get("affordability_index", 0) for s in states) / max(1, len(states)), 2),
            "avg_liquidity":             round(
                sum(s.get("liquidity_score", 0) for s in states) / max(1, len(states)), 4),
            "scenario_label":            SCENARIOS.get(run.scenario_name, {}).get("label", run.scenario_name),
        }

    return _json({"run_id": str(run.run_id), "metrics": metrics})


# ── Agent outcomes ─────────────────────────────────────────────────────────────
def agents_view(request, run_id):
    if request.method == "OPTIONS":
        return _preflight()

    try:
        run = SimulationRun.objects.get(run_id=run_id)
    except SimulationRun.DoesNotExist:
        return _err("Run not found", 404)

    return _json({
        "run_id":       str(run.run_id),
        "agents":       run.agent_outcomes or [],
        "total_agents": sum(a.get("count", 0) for a in (run.agent_outcomes or [])),
    })


# ── Compare two runs ───────────────────────────────────────────────────────────
def compare_view(request):
    if request.method == "OPTIONS":
        return _preflight()

    run_a_id = request.GET.get("run_a", "").strip()
    run_b_id = request.GET.get("run_b", "").strip()

    if not run_a_id or not run_b_id:
        return _err("Provide run_a and run_b query parameters")

    try:
        run_a = SimulationRun.objects.get(run_id=run_a_id)
        run_b = SimulationRun.objects.get(run_id=run_b_id)
    except SimulationRun.DoesNotExist as exc:
        return _err(f"Run not found: {exc}", 404)

    def _summary(run: SimulationRun) -> dict:
        states = run.monthly_states or []
        prices = [s.get("avg_price", 0) for s in states if s.get("avg_price")]
        first  = prices[0]  if prices else 0
        last   = prices[-1] if prices else 0
        pct    = (last - first) / max(1.0, first) * 100 if first else 0
        return {
            "run_id":             str(run.run_id),
            "scenario_name":      run.scenario_name,
            "scenario_label":     SCENARIOS.get(run.scenario_name, {}).get("label", run.scenario_name),
            "agent_scale":        run.agent_scale,
            "num_months":         run.num_months,
            "status":             run.status,
            "total_transactions": run.total_transactions,
            "summary": {
                "initial_avg_price": round(first, 2),
                "final_avg_price":   round(last, 2),
                "price_change_pct":  round(pct, 2),
                "avg_affordability": round(
                    sum(s.get("affordability_index", 0) for s in states) / max(1, len(states)), 2),
                "avg_liquidity":     round(
                    sum(s.get("liquidity_score", 0) for s in states) / max(1, len(states)), 4),
            },
        }

    return _json({"run_a": _summary(run_a), "run_b": _summary(run_b)})


# ── Zone price snapshot (for frontend geographic map) ─────────────────────────
def zones_view(request, run_id):
    """Return per-governorate average apartment price for the most recent step."""
    if request.method == "OPTIONS":
        return _preflight()

    try:
        run = SimulationRun.objects.get(run_id=run_id)
    except SimulationRun.DoesNotExist:
        return _err("Run not found", 404)

    # Build from the zone_prices stored in the last monthly_state
    states = run.monthly_states or []
    zone_prices: dict = {}
    if states:
        zone_prices = states[-1].get("zone_prices", {})

    # Aggregate to governorate level (apartment type only — key = "(gov, apartment)")
    gov_prices: dict = {}
    from .engine.config import DELEGATION_DATA
    deleg_gov = {d["delegation"]: d["governorate"] for d in DELEGATION_DATA}

    for key_str, price in zone_prices.items():
        # Key stored as "('Delegation Name', 'apartment')"
        try:
            key = eval(key_str)  # safe: values from our own code
            delegation, ptype = key
            if ptype != "apartment":
                continue
            gov = deleg_gov.get(delegation, "")
            if not gov:
                continue
            if gov not in gov_prices:
                gov_prices[gov] = {"prices": [], "governorate": gov}
            gov_prices[gov]["prices"].append(float(price))
        except Exception:
            continue

    zones = []
    for gov, d in gov_prices.items():
        prices = d["prices"]
        zones.append({
            "governorate": gov,
            "avg_price_m2": round(sum(prices) / len(prices), 2) if prices else 0,
        })
    zones.sort(key=lambda x: x["governorate"])

    return _json({
        "run_id": str(run.run_id),
        "month":  states[-1].get("month", 0) if states else 0,
        "zones":  zones,
    })
