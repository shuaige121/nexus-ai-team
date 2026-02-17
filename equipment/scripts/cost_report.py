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


# Token pricing (per 1M tokens)
TOKEN_PRICING = {
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60
    },
    "gpt-4-turbo": {
        "input": 10.00,
        "output": 30.00
    },
    "gpt-3.5-turbo": {
        "input": 0.50,
        "output": 1.50
    },
    "claude-3-5-sonnet": {
        "input": 3.00,
        "output": 15.00
    },
    "claude-3-opus": {
        "input": 15.00,
        "output": 75.00
    },
    "claude-3-haiku": {
        "input": 0.25,
        "output": 1.25
    }
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

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


def read_usage_logs(log_dir: Path, days: int = 1) -> list:
    """
    Read token usage logs from database or log files.

    Args:
        log_dir: Directory containing logs
        days: Number of days to look back

    Returns:
        List of usage records
    """
    usage_records = []

    # Try to read from database first
    try:
        import sqlite3
        db_path = Path(__file__).parent.parent.parent / "nexus.db"

        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.isoformat()

            # Try to query token_usage table
            try:
                cursor.execute("""
                    SELECT timestamp, agent_name, model, input_tokens, output_tokens
                    FROM token_usage
                    WHERE timestamp >= ?
                """, (cutoff_str,))

                for row in cursor.fetchall():
                    usage_records.append({
                        "timestamp": row[0],
                        "agent": row[1],
                        "model": row[2],
                        "input_tokens": row[3],
                        "output_tokens": row[4]
                    })
            except sqlite3.OperationalError:
                logger.warning("token_usage table not found in database")

            conn.close()

    except Exception as e:
        logger.warning(f"Failed to read from database: {e}")

    return usage_records


def generate_report(usage_records: list) -> dict:
    """
    Generate cost report from usage records.

    Args:
        usage_records: List of usage records

    Returns:
        Cost report
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "period_days": 1,
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "by_agent": defaultdict(lambda: {
            "cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "requests": 0
        }),
        "by_model": defaultdict(lambda: {
            "cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "requests": 0
        })
    }

    for record in usage_records:
        agent = record.get("agent", "unknown")
        model = record.get("model", "gpt-4o")
        input_tokens = record.get("input_tokens", 0)
        output_tokens = record.get("output_tokens", 0)

        # Calculate cost
        cost = calculate_cost(model, input_tokens, output_tokens)

        # Update totals
        report["total_cost"] += cost
        report["total_input_tokens"] += input_tokens
        report["total_output_tokens"] += output_tokens

        # Update by agent
        report["by_agent"][agent]["cost"] += cost
        report["by_agent"][agent]["input_tokens"] += input_tokens
        report["by_agent"][agent]["output_tokens"] += output_tokens
        report["by_agent"][agent]["requests"] += 1

        # Update by model
        report["by_model"][model]["cost"] += cost
        report["by_model"][model]["input_tokens"] += input_tokens
        report["by_model"][model]["output_tokens"] += output_tokens
        report["by_model"][model]["requests"] += 1

    # Convert defaultdicts to regular dicts
    report["by_agent"] = dict(report["by_agent"])
    report["by_model"] = dict(report["by_model"])

    # Round costs
    report["total_cost"] = round(report["total_cost"], 4)
    for agent in report["by_agent"]:
        report["by_agent"][agent]["cost"] = round(report["by_agent"][agent]["cost"], 4)
    for model in report["by_model"]:
        report["by_model"][model]["cost"] = round(report["by_model"][model]["cost"], 4)

    return report


def save_report(report: dict, report_dir: Path):
    """
    Save report to file.

    Args:
        report: Cost report
        report_dir: Directory to save report
    """
    report_dir.mkdir(parents=True, exist_ok=True)

    # Save daily report
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_file = report_dir / f"cost-report-{date_str}.json"

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Report saved: {report_file}")


def main(report_dir="reports/cost", email_enabled=False, email_to=None, period_days=1):
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
    report_path = Path(report_dir)

    try:
        # Read usage logs
        usage_records = read_usage_logs(report_path, days=period_days)

        logger.info(f"Found {len(usage_records)} usage records")

        # Generate report
        report = generate_report(usage_records)
        report["period_days"] = period_days

        # Save report
        save_report(report, report_path)

        # Summary
        report["summary"] = (
            f"Total cost: ${report['total_cost']:.4f}, "
            f"Tokens: {report['total_input_tokens']:,} in / {report['total_output_tokens']:,} out, "
            f"Agents: {len(report['by_agent'])}, "
            f"Models: {len(report['by_model'])}"
        )

        logger.info(f"Cost report completed: {report['summary']}")

        # Email notification (not implemented)
        if email_enabled and email_to:
            logger.info(f"Email notification disabled (not implemented)")

        return report

    except Exception as e:
        logger.error(f"Cost report failed: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
            "summary": f"Failed: {str(e)}"
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    print(f"Summary: {result['summary']}")
    print(f"\nTotal Cost: ${result['total_cost']:.4f}")

    if result.get('by_agent'):
        print("\nCost by Agent:")
        for agent, data in result['by_agent'].items():
            print(f"  {agent}: ${data['cost']:.4f} ({data['requests']} requests)")

    if result.get('by_model'):
        print("\nCost by Model:")
        for model, data in result['by_model'].items():
            print(f"  {model}: ${data['cost']:.4f} ({data['requests']} requests)")
