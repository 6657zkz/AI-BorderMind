"""画像澄清：从用户回答解析「品类 + 市场」/「竞品」并持久化到项目。

原则：只问数据里没有的、结构化、最小化。市场做广匹配（任意国家/地区/代码，
不拒绝未知市场——没数据时专家会诚实报告数据不足，而不是死循环反问）。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Category, Product, Project
from ..llm import LLMClient, get_client

# 中文/常用名 → 市场代码（广覆盖，未列出的交给 LLM 代码或兜底）
_MARKET_MAP: dict[str, str] = {
    "美国": "US", "美区": "US", "us": "US",
    "日本": "JP", "日站": "JP", "jp": "JP",
    "德国": "DE", "de": "DE",
    "英国": "UK", "uk": "UK",
    "加拿大": "CA", "ca": "CA",
    "澳洲": "AU", "澳大利亚": "AU", "au": "AU",
    "印度尼西亚": "ID", "印尼": "ID", "id": "ID",
    "印度": "IN", "in": "IN",
    "法国": "FR", "fr": "FR",
    "意大利": "IT", "it": "IT",
    "西班牙": "ES", "es": "ES",
    "巴西": "BR", "br": "BR",
    "墨西哥": "MX", "mx": "MX",
    "韩国": "KR", "韩站": "KR", "kr": "KR",
    "泰国": "TH", "th": "TH",
    "越南": "VN", "vn": "VN",
    "菲律宾": "PH", "ph": "PH",
    "新加坡": "SG", "sg": "SG",
    "马来西亚": "MY", "my": "MY",
    "阿联酋": "AE", "迪拜": "AE", "ae": "AE",
    "沙特": "SA", "sa": "SA",
    "土耳其": "TR", "tr": "TR",
    "俄罗斯": "RU", "俄站": "RU", "ru": "RU",
    "南非": "ZA", "za": "ZA",
    "埃及": "EG", "eg": "EG",
    "非洲": "AF", "af": "AF",
    "欧洲": "EU", "eu": "EU",
    "东南亚": "SEA", "sea": "SEA",
}


def _to_market_code(text: str | None) -> str | None:
    if not text:
        return None
    t = text.strip()
    up = t.upper()
    if up.isascii() and len(up) <= 3 and up.isalpha():  # 已是代码/缩写（US/ID/AF/EU…）
        return up
    low = t.lower()
    for key, code in _MARKET_MAP.items():
        if key.lower() in low:
            return code
    return None


def _normalize(s: str) -> str:
    return s.replace(" ", "").replace("站", "").lower()


def _resolve_category(db: Session, name: str) -> str:
    """按名称解析 category_id：先精确（忽略空格/大小写），再包含匹配，查不到新建。"""
    norm = _normalize(name)
    rows = db.execute(select(Category)).scalars().all()
    for r in rows:
        for cand in (r.name_local, r.name_en):
            if cand and _normalize(cand) == norm:
                return r.category_id
    for r in rows:
        for cand in (r.name_local, r.name_en):
            if cand and norm and norm in _normalize(cand):
                return r.category_id
    cid = f"cat_{uuid.uuid4().hex[:8]}"
    db.add(Category(category_id=cid, level=2, name_local=name, name_en=name, tariff_rate=0.0))
    db.commit()
    return cid


def parse_scope(db: Session, message: str, llm: LLMClient | None = None) -> dict[str, Any] | None:
    """从用户回答解析范围；缺品类或市场返回 None（交给工作流继续澄清）。"""
    llm = llm or get_client()
    system = (
        "从用户话里提取研判范围。只输出 JSON："
        '{"category": "品类名（如 纸巾、TWS耳机、生活用品）或 null", '
        '"market": "目标市场（国家/地区名或代码，如 美国/US、印度尼西亚/ID、非洲/AF）或 null"}。'
        "market 给中文名或代码都行。"
    )
    data = llm.complete_json([{"role": "user", "content": message}], system=system, temperature=0)
    category_name = (data.get("category") or "").strip()
    market_raw = (data.get("market") or "").strip()
    market_code = _to_market_code(market_raw) or _to_market_code(message)
    if not category_name or not market_code:
        return None
    return {
        "category_id": _resolve_category(db, category_name),
        "category_name": category_name,
        "market_code": market_code,
        "market_name": market_raw or market_code,
    }


def apply_scope(db: Session, project_id: str, scope: dict[str, Any]) -> Project | None:
    project = db.get(Project, project_id)
    if project is None:
        return None
    project.category_id = scope["category_id"]
    project.market_code = scope["market_code"]
    db.commit()
    db.refresh(project)
    return project


def apply_product(db: Session, project_id: str, product_id: str) -> Project | None:
    """把竞品写入项目 profile_json.product_ids（去重）。"""
    project = db.get(Project, project_id)
    if project is None:
        return None
    profile = dict(project.profile_json or {})
    ids = list(dict.fromkeys((profile.get("product_ids") or []) + [product_id]))
    profile["product_ids"] = ids
    project.profile_json = profile
    db.commit()
    db.refresh(project)
    return project


def top_products(db: Session, category_id: str, limit: int = 3) -> list[tuple[str, str]]:
    """类目头部竞品（按评论数降序）：返回 [(product_id, 显示名)]。"""
    rows = (
        db.execute(
            select(Product)
            .where(Product.category_id == category_id)
            .order_by(Product.review_count.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [(r.product_id, r.brand or r.title or r.product_id) for r in rows]
