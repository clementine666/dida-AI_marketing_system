"""新加坡 F1 活动 - 4 Agent 完整工作流示例。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.agent1_service import Agent1Service
from app.services.agent2_service import Agent2Service
from app.services.agent3_service import Agent3Service
from app.services.agent4_service import Agent4Service

CAMPAIGN_ID = "CAMP_F1_SG_2026"
DESTINATION = "Singapore"


def run_f1_workflow() -> dict:
    agent1 = Agent1Service()
    agent2 = Agent2Service()
    agent3 = Agent3Service()
    agent4 = Agent4Service()

    print("=" * 60)
    print("Step 1: Agent 1 - 分析搜索过新加坡的客户")
    demand_report = agent1.get_demand_report(DESTINATION)
    print(f"  目标客户数: {demand_report['client_count']}")
    print(f"  推荐方向: {demand_report['recommendation_direction'][0]}")

    print("\nStep 2: Agent 2 - 匹配 F1 赛场周边酒店")
    resource_match = agent2.match_resources(DESTINATION, "F1 Singapore Grand Prix")
    print(f"  匹配酒店数: {resource_match['hotel_count']}")
    for h in resource_match["matched_hotels"][:3]:
        print(f"    - {h['hotel_name']} ({h['star_rating']}星)")

    print("\nStep 3: Agent 3 - 策划活动方案 + 搭建监控")
    campaign_plan = agent3.create_campaign_plan(CAMPAIGN_ID, demand_report, resource_match)
    alerts = agent3.run_monitoring(CAMPAIGN_ID)
    print(f"  活动: {campaign_plan['campaign_name']}")
    print(f"  监控告警数: {len(alerts)}")

    print("\nStep 4: Agent 4 - 活动复盘")
    review_report = agent4.generate_review_report(CAMPAIGN_ID)
    print(f"  报告: {review_report['report_title']}")
    print(f"  关键发现: {review_report['key_findings'][0]}")

    workflow_output = {
        "workflow": "Singapore F1 Campaign",
        "campaign_id": CAMPAIGN_ID,
        "agent1_demand_report": demand_report,
        "agent2_resource_match": resource_match,
        "agent3_campaign_plan": campaign_plan,
        "agent3_alerts": alerts,
        "agent4_review_report": review_report,
    }

    output_path = ROOT / "data" / "f1_workflow_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(workflow_output, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n完整输出已保存: {output_path}")
    return workflow_output


if __name__ == "__main__":
    run_f1_workflow()
