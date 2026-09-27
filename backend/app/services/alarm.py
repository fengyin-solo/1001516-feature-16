"""告警监测业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "alarm"
REQUIRED_FIELDS = ["告警编号", "告警来源", "告警类型"]
THRESHOLD_FIELDS = ["阈值下限", "阈值上限", "阈值单位", "生效范围"]
STATUS_ORDER = ["待确认", "处置中", "已关闭", "已忽略"]
ACTION_RULES = {"确认告警": "处置中", "关闭告警": "已关闭", "忽略告警": "已忽略"}
NEGATIVE_ACTIONS = ["忽略告警"]

# 告警类型与阈值单位的对应口径：单位不在清单里就不允许保存。
ALARM_TYPE_UNITS = {
    "温度告警": ["℃"],
    "湿度告警": ["%RH"],
    "风速告警": ["m/s"],
    "气压告警": ["hPa"],
    "降水告警": ["mm"],
    "电压告警": ["V"],
    "数据缺报告警": ["次"],
}


def _to_number(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _alarm_code(row: dict[str, Any]) -> str:
    return str(row.get("告警编号") or "").strip()


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同一告警编号只保留最新一条（id 最大），没有编号的记录原样保留。"""
    latest_id: dict[str, int] = {}
    for row in rows:
        code = _alarm_code(row)
        if code:
            latest_id[code] = max(latest_id.get(code, 0), int(row.get("id", 0)))
    kept: list[dict[str, Any]] = []
    for row in rows:
        code = _alarm_code(row)
        if code and int(row.get("id", 0)) < latest_id[code]:
            continue
        kept.append(row)
    return kept


def validate_threshold(values: dict[str, Any]) -> list[str]:
    """上下限、单位与生效范围一起校验，返回所有不满足的说明，空列表表示通过。"""
    problems: list[str] = []
    alarm_type = str(values.get("告警类型") or "").strip()
    lower = _to_number(values.get("阈值下限"))
    upper = _to_number(values.get("阈值上限"))
    unit = str(values.get("阈值单位") or "").strip()
    scope = str(values.get("生效范围") or "").strip()

    if lower is None:
        problems.append(f"阈值下限「{values.get('阈值下限')}」不是有效数值")
    if upper is None:
        problems.append(f"阈值上限「{values.get('阈值上限')}」不是有效数值")
    if lower is not None and upper is not None and upper < lower:
        problems.append(f"阈值上限 {upper:g} 低于下限 {lower:g}，上限必须大于等于下限")
    if not unit:
        problems.append("阈值单位不能为空")
    elif alarm_type in ALARM_TYPE_UNITS and unit not in ALARM_TYPE_UNITS[alarm_type]:
        allowed = "、".join(ALARM_TYPE_UNITS[alarm_type])
        problems.append(f"阈值单位「{unit}」与告警类型「{alarm_type}」不匹配，该类型允许的单位：{allowed}")
    elif alarm_type and alarm_type not in ALARM_TYPE_UNITS:
        supported = "、".join(ALARM_TYPE_UNITS)
        problems.append(f"告警类型「{alarm_type}」不在已登记的阈值口径里（支持：{supported}），无法校验单位")
    if not scope:
        problems.append("生效范围不能为空")
    return problems


def format_threshold(values: dict[str, Any]) -> str:
    """把阈值收成一条口径：下限~上限 单位（生效范围）。"""
    lower = _to_number(values.get("阈值下限"))
    upper = _to_number(values.get("阈值上限"))
    unit = str(values.get("阈值单位") or "").strip()
    scope = str(values.get("生效范围") or "").strip()
    return f"{lower:g}~{upper:g} {unit}（{scope}）"


class AlarmService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = _dedupe_rows(store.rows(MODULE))
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("告警编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        problems: list[str] = []
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            problems.append(f"缺少必填字段：{'、'.join(missing)}")
        problems.extend(validate_threshold(values))
        if problems:
            return None, problems
        rows = store.rows(MODULE)
        code = str(values["告警编号"]).strip()
        # id 先取再走，保证单调递增：最新一条的 id 永远是同编号里最大的。
        next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        # 同一告警编号重复触发只保留最新一条：先摘掉旧记录再登记新记录。
        rows[:] = [row for row in rows if _alarm_code(row) != code]
        entry = {"id": next_id}
        entry.update({field: str(values.get(field)).strip() for field in REQUIRED_FIELDS})
        entry["阈值下限"] = _to_number(values.get("阈值下限"))
        entry["阈值上限"] = _to_number(values.get("阈值上限"))
        entry["阈值单位"] = str(values.get("阈值单位") or "").strip()
        entry["生效范围"] = str(values.get("生效范围") or "").strip()
        entry["触发阈值"] = format_threshold(entry)
        for field in ["触发时刻", "处置人员", "关闭时刻"]:
            if str(values.get(field) or "").strip():
                entry[field] = str(values.get(field)).strip()
        entry["告警状态"] = STATUS_ORDER[0]
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """保存触发阈值修改：与既有取值合并后按一条口径联合校验，不通过就不落库。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, [f"告警记录 {entry_id} 不存在或已归档"]
        merged = dict(entry)
        for field in THRESHOLD_FIELDS:
            if field in values:
                merged[field] = values[field]
        if str(values.get("告警类型") or "").strip():
            merged["告警类型"] = str(values["告警类型"]).strip()
        problems = validate_threshold(merged)
        if problems:
            return None, problems
        entry["告警类型"] = str(merged.get("告警类型") or "").strip()
        entry["阈值下限"] = _to_number(merged.get("阈值下限"))
        entry["阈值上限"] = _to_number(merged.get("阈值上限"))
        entry["阈值单位"] = str(merged.get("阈值单位") or "").strip()
        entry["生效范围"] = str(merged.get("生效范围") or "").strip()
        entry["触发阈值"] = format_threshold(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"告警记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于告警监测可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["告警状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"告警记录已{action}"

    def stats(self) -> dict[str, Any]:
        """统计卡片与触发阈值快照：和列表、详情读同一份数据，保证取值一致。"""
        rows = _dedupe_rows(store.rows(MODULE))
        today = date.today().isoformat()
        cards = [
            {"label": "待确认告警", "value": sum(1 for row in rows if row.get("status") == "待确认")},
            {"label": "处置中告警", "value": sum(1 for row in rows if row.get("status") == "处置中")},
            {"label": "今日告警数", "value": sum(1 for row in rows if str(row.get("触发时刻") or "").startswith(today))},
        ]
        thresholds = {_alarm_code(row): row.get("触发阈值") for row in rows if _alarm_code(row)}
        return {"cards": cards, "thresholds": thresholds, "typeUnits": ALARM_TYPE_UNITS}
