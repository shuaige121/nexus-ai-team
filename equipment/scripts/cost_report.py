"""
Cost Report Equipment
Generates daily token usage and cost reports
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

# Token pricing per million tokens (USD)
TOKEN_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 30.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-opus": {"input": 75.0, "output": 75.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for token usage.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    pricing = TOKEN_PRICING.get(model, TOKEN_PRICING["gpt-4o"])
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def read_usage_logs(log_dir: str = "logs", days: int = 1) -> list[dict]:
    """
    Read token usage logs from database or log files.

    Args:
        log_dir: Directory containing logs
        days: Number of days to look back

    Returns:
        List of usage records
    """
    records: list[dict] = []

    try:
        import sqlite3
        db_path = Path(__file__).parent.parent / "nexus.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            try:
                cursor.execute(
                    """
                    SELECT timestamp, agent_name, model, input_tokens, output_tokens
                    FROM token_usage
                    WHERE timestamp >= ?
                """,
                    (cutoff,),
                )
                for row in cursor.fetchall():
                    records.append({
                        "timestamp": row[0],
                        "agent": row[1],
                        "model": row[2],
                        "input_tokens": row[3],
                        "output_tokens": row[4],
                    })
            except sqlite3.OperationalError:
                logger.warning("token_usage table not found in database")
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to read from database: {e}")

    return records


def generate_report(usage_records: list[dict]) -> dict:
    """
    Generate cost report from usage records.

    Args:
        usage_records: List of usage records

    Returns:
        Cost report
    """
    timestamp = datetime.now().isoformat()

    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    by_agent: dict = defaultdict(lambda: {"cost": 0.0, "requests": 0, "input_tokens": 0, "output_tokens": 0})
    by_model: dict = defaultdict(lambda: {"cost": 0.0, "requests": 0, "input_tokens": 0, "output_tokens": 0})

    for record in usage_records:
        agent = record.get("agent", "unknown")
        model = record.get("model", "gpt-4o")
        inp = record.get("input_tokens", 0)
        out = record.get("output_tokens", 0)
        cost = calculate_cost(model, inp, out)

        total_cost += cost
        total_input_tokens += inp
        total_output_tokens += out

        by_agent[agent]["cost"] += cost
        by_agent[agent]["requests"] += 1
        by_agent[agent]["input_tokens"] += inp
        by_agent[agent]["output_tokens"] += out

        by_model[model]["cost"] += cost
        by_model[model]["requests"] += 1
        by_model[model]["input_tokens"] += inp
        by_model[model]["output_tokens"] += out

    return {
        "timestamp": timestamp,
        "total_cost": round(total_cost, 6),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "by_agent": dict(by_agent),
        "by_model": dict(by_model),
    }


def save_report(report: dict, report_dir: Path) -> Path:
    """
    Save report to file.

    Args:
        report: Cost report
        report_dir: Directory to save report
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_file = report_dir / f"cost-report-{date_str}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report saved: {report_file}")
    return report_file


def main(
    report_dir: str = "reports/cost",
    email_enabled: bool = False,
    email_to: str | None = None,
    period_days: int = 1,
) -> dict:
    """
    Generate daily token cost report.

    Args:
        report_dir: Directory to save reports
        email_enabled: Whether to send email (not implemented)
        email_to: Email recipient
        period_days: Number of days to analyze

    Returns:
        Cost report
    """
    try:
        records = read_usage_logs(days=period_days)
        logger.info(f"Found {len(records)} usage records")

        report = generate_report(records)
        save_report(report, Path(report_dir))

        summary = (
            f"Total cost: ${report['total_cost']:.4f}, "
            f"Tokens: {report['total_input_tokens']},{report['total_output_tokens']} in / "
            f"{report['total_output_tokens']} out, "
            f"Agents: {len(report['by_agent'])}, "
            f"Models: {len(report['by_model'])}"
        )
        report["summary"] = summary
        logger.info(f"Cost report completed: {summary}")

        if email_enabled:
            logger.info("Email notification disabled (not implemented)")

        return report

    except Exception as e:
        logger.error(f"Cost report failed: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "summary": f"Failed: {e}",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    print(f"Summary: {result['summary']}")
    print(f"\nTotal Cost: ${result.get('total_cost', 0):.4f}")
    for agent, data in result.get("by_agent", {}).items():
        print(f"\nCost by Agent:")
        print(f"  {agent}: ${data['cost']:.4f} ({data['requests']} requests)")
    for model, data in result.get("by_model", {}).items():
        print(f"\nCost by Model:")
        print(f"  {model}: ${data['cost']:.4f} ({data['requests']} requests)")
