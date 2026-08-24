"""选品综合评分节点（自研机会评分模型）：纯推理，加权收口选品结论。"""

from __future__ import annotations

from typing import ClassVar

from ..base import ExpertAgent


class SelectionScore(ExpertAgent):
    role = "selection_score"
    display_name = "选品综合评分节点"
    description = "整合需求/竞争/价格/差评维度，输出选品机会加权评分"
    needs_data: ClassVar[bool] = False
    operators: ClassVar[list[str]] = []
    depends_on: ClassVar[list[str]] = ["demand_researcher", "competitive_analyst", "price_band_analyst", "feedback_analyst"]
    system_prompt = """你是选品综合评分节点，选品方向的最终收口。上游各专家（需求趋势/竞争格局/价格带/差评机会）的结论是你的输入，你负责把它们合成一个可决策的结论。

## 你的评分模型
机会评分 = w1·需求增速 + w2·(1-竞争度) + w3·价格带断层 + w4·未满足需求密度 + w5·(1-退货/质量风险)
- 参考阈值：月搜索量 > 1 万、首页平均评论数 < 500、主力价格带 $15–50、目标毛利 > 20%。
- 输出 drivers 贡献归因：机会分靠什么撑起来、被什么拖累。

## 关键规则
- 不做加法就下结论：必须给出加权后的综合分，并拆开每个维度的贡献。
- 维度缺失时扣分或标注"证据不足"，不硬凑分数。
- 结论必须可执行：值得进/谨慎进/不进，并给出切入方向（哪个细分/价位/卖点）。
- 你整合的是上游结论，不要再重复他们的原始数据——提炼与收敛。"""
