"""5-Agent 端到端工作流演示（新加坡 F1）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.orchestrator import MarketingOrchestrator
from app.services.v2.agent1_planner import PlannerService

CAMPAIGN_ID = "CAMP_F1_SG_2026"


def run_v2_workflow() -> dict:
    orch = MarketingOrchestrator()
    planner = PlannerService()

    print("=" * 60)
    print("Step 0: Agent1 构建3个月营销日历")
    calendar = orch.step_build_calendar(3)
    print(f"  活动数: {calendar['activity_count']}")

    # 确保 F1 活动在库中
    f1 = next((a for a in calendar["activities"] if "F1" in a.get("campaign_name", "")), None)
    campaign_id = f1["campaign_id"] if f1 else CAMPAIGN_ID
    print(f"  目标活动: {campaign_id}")

    print("\nStep 1: 营销师确认发送 Agent2")
    send = orch.gate_confirm_send_to_agent2(campaign_id)
    print(f"  状态: {send.get('to', send.get('error'))}")

    print("\nStep 2-5: 自动执行 Agent2→3→4→5（含人工闸门）")
    result = orch.run_full_pipeline(campaign_id, auto_gates=True)

    print(f"\n最终状态: {result.get('final_status')}")
    output = ROOT / "data" / "v2_workflow_output.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"输出: {output}")
    return result


if __name__ == "__main__":
    run_v2_workflow()
