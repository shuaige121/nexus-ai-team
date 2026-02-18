"""Analytics API routes."""

from fastapi import APIRouter, Query

from dashboard.backend.mock_data import (
    generate_cost_optimization,
    generate_performance_data,
    generate_token_history,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/tokens")
async def get_token_stats(
    time_range: str = Query("7d", alias="range"),
    agent: str | None = Query(None),
):
    """获取token消耗数据。"""
    days_map = {"1d": 1, "7d": 7, "30d": 30}
    days = days_map.get(time_range, 7)
    data = generate_token_history(days)
    if agent:
        data = [d for d in data if d["agent_name"] == agent]

    # Compute summary
    total_input = sum(d["input_tokens"] for d in data)
    total_output = sum(d["output_tokens"] for d in data)
    total_cost = sum(d["cost"] for d in data)
    total_calls = sum(d["calls"] for d in data)
    max_single = max((d["cost"] for d in data), default=0)

    return {
        "daily": data,
        "summary": {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": round(total_cost, 2),
            "total_calls": total_calls,
            "avg_cost_per_contract": round(total_cost / max(total_calls, 1), 4),
            "max_single_cost": round(max_single, 4),
        }
    }


@router.get("/performance")
async def get_performance(
    department: str | None = Query(None),
):
    """获取绩效数据。"""
    data = generate_performance_data()
    if department:
        data = [d for d in data if d["department"] == department]
    return {
        "agents": data,
        "rework_ranking": sorted(data, key=lambda x: x["rework_rate"], reverse=True)[:5]
    }


@router.get("/cost")
async def get_cost_analysis():
    """获取成本优化建议。"""
    suggestions = generate_cost_optimization()
    total_savings = sum(s["estimated_monthly_savings"] for s in suggestions)
    return {
        "suggestions": suggestions,
        "total_estimated_monthly_savings": round(total_savings, 2)
    }
