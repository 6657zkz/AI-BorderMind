"""算子基类：TEXT2SQL 单元（查询生成级联的「固定算子」层）。

原则：规则写 SQL、LLM 只填参数。每个算子声明参数模型（pydantic 校验），
执行时返回「结果 + SQL + 耗时 + 时间戳」——即证据链的最小单元，结论可回溯。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, ClassVar

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session


def _json_safe(value: Any) -> Any:
    """把数据库原生类型转成 JSON 可序列化（Decimal→float、date/datetime→iso）。"""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class OperatorError(RuntimeError):
    """算子执行失败（参数非法 / SQL 错误 / 依赖数据缺失）。"""


@dataclass
class OperatorResult:
    operator: str
    params: dict[str, Any]
    sql: str
    rows: list[dict[str, Any]]
    executed_at: str
    elapsed_ms: int
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "params": self.params,
            "sql": self.sql,
            "rows": self.rows,
            "executed_at": self.executed_at,
            "elapsed_ms": self.elapsed_ms,
            "truncated": self.truncated,
        }


class Operator(BaseModel):
    """算子基类。子类声明 name/description/param_schema/outputs，实现 _build_sql()。"""

    name: ClassVar[str]
    description: ClassVar[str] = ""
    outputs: ClassVar[str] = ""
    param_schema: ClassVar[type[BaseModel]]
    max_rows: ClassVar[int] = 100

    def validate_params(self, **params: Any) -> dict[str, Any]:
        try:
            return self.param_schema(**params).model_dump()
        except Exception as exc:  # pydantic ValidationError
            raise OperatorError(f"算子 {self.name} 参数非法: {exc}") from exc

    def execute(self, db: Session, **params: Any) -> OperatorResult:
        clean = self.validate_params(**params)
        sql, bind = self._build_sql(**clean)
        start = time.monotonic()
        try:
            result = db.execute(text(sql), bind)
        except Exception as exc:
            db.rollback()  # 复位会话，避免后续算子被「事务已中止」连锁拖垮
            raise OperatorError(f"算子 {self.name} SQL 执行失败: {exc}") from exc
        mapped = [
            {k: _json_safe(v) for k, v in r.items()}
            for r in result.mappings()
        ]
        elapsed = int((time.monotonic() - start) * 1000)
        return OperatorResult(
            operator=self.name,
            params=clean,
            sql=sql,
            rows=mapped[: self.max_rows],
            executed_at=datetime.now(timezone.utc).isoformat(),
            elapsed_ms=elapsed,
            truncated=len(mapped) > self.max_rows,
        )

    def _build_sql(self, **params: Any) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError
