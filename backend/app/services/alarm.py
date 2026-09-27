"""告警监测业务规则：状态流转、字段校验与筛选口径都收在这里。

触发阈值在全平台只认一条口径：下限、上限、单位、生效范围四项一起校验，
保存成功后把展示字符串、结构化字段、保存时刻与版本号写回同一条记录，
列表、详情、统计都从这里取值，避免出现各写各的、刷新后回退的情况。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "alarm"
REQUIRED_FIELDS = ["告警编号", "告警来源", "告警类型"]
STATUS_ORDER = ["待确认", "处置中", "已关闭", "已忽略"]
ACTION_RULES = {"确认告警": "处置中", "关闭告警": "已关闭", "忽略告警": "已忽略"}
NEGATIVE_ACTIONS = ["忽略告警"]

# 触发阈值统一口径：生效范围只认这三档，单位跟着告警类型走。
THRESHOLD_SCOPES = ["全站生效", "单站生效", "单要素生效"]
ALARM_TYPE_UNITS = {
    "温度": ["℃"],
    "湿度": ["%"],
    "气压": ["hPa"],
    "风速": ["m/s"],
    "降水": ["mm"],
    "供电": ["V", "A"],
    "通信": ["dBm"],
}
ALL_UNITS = sorted({unit for units in ALARM_TYPE_UNITS.values() for unit in units})
THRESHOLD_FIELDS = ["阈值下限", "阈值上限", "阈值单位", "生效范围"]


def _dedup_latest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同一告警编号只保留 id 最大（最后一次触发/保存）的那条。"""
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("告警编号", "")).strip()
        if not key:
            continue
        if key not in latest or int(row.get("id", 0)) > int(latest[key].get("id", 0)):
            latest[key] = row
    return sorted(latest.values(), key=lambda row: int(row.get("id", 0)))


def _allowed_units(alarm_type: str) -> list[str]:
    """按告警类型匹配允许的单位；类型不在表里时放宽到全部已知单位。"""
    for keyword, units in ALARM_TYPE_UNITS.items():
        if keyword in alarm_type:
            return units
    return list(ALL_UNITS)


def _format_number(value: float) -> str:
    return f"{value:g}"


def _raw_text(value: Any) -> str:
    """取出原始文本；数值 0 也是合法输入，不能被当成空。"""
    if value is None:
        return ""
    return str(value).strip()


def format_threshold(entry: dict[str, Any]) -> str:
    """把结构化阈值拼成唯一对外展示口径，例如 ``-40~45 ℃（全站生效）``。"""
    lower = _format_number(float(entry["阈值下限"]))
    upper = _format_number(float(entry["阈值上限"]))
    return f"{lower}~{upper} {entry['阈值单位']}（{entry['生效范围']}）"


def validate_threshold(values: dict[str, Any], alarm_type: str) -> tuple[dict[str, Any] | None, list[str]]:
    """上下限、单位、生效范围一起校验；返回（规范化结果, 问题清单）。"""
    problems: list[str] = []
    lower: float | None = None
    upper: float | None = None
    raw_lower = _raw_text(values.get("阈值下限"))
    raw_upper = _raw_text(values.get("阈值上限"))
    if not raw_lower:
        problems.append("阈值下限未填写")
    else:
        try:
            lower = float(raw_lower)
        except ValueError:
            problems.append(f"阈值下限「{raw_lower}」不是有效数值")
    if not raw_upper:
        problems.append("阈值上限未填写")
    else:
        try:
            upper = float(raw_upper)
        except ValueError:
            problems.append(f"阈值上限「{raw_upper}」不是有效数值")
    if lower is not None and upper is not None and upper < lower:
        problems.append(
            f"阈值上限 {_format_number(upper)} 低于下限 {_format_number(lower)}，需满足 下限 ≤ 上限"
        )

    unit = _raw_text(values.get("阈值单位"))
    if not unit:
        problems.append("阈值单位未填写")
    else:
        allowed = _allowed_units(alarm_type)
        if unit not in allowed:
            problems.append(
                f"阈值单位「{unit}」与告警类型「{alarm_type or '未填写'}」不匹配，该类型允许的单位：{'、'.join(allowed)}"
            )

    scope = _raw_text(values.get("生效范围"))
    if not scope:
        problems.append("生效范围未填写")
    elif scope not in THRESHOLD_SCOPES:
        problems.append(f"生效范围「{scope}」不在允许范围：{'、'.join(THRESHOLD_SCOPES)}")

    if problems:
        return None, problems
    normalized = {"阈值下限": lower, "阈值上限": upper, "阈值单位": unit, "生效范围": scope}
    return normalized, []


class AlarmService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = _dedup_latest(store.rows(MODULE))
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("告警编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def stats(self) -> list[dict[str, Any]]:
        """统计卡片与列表读同一份去重后的数据，阈值改动后各处取值自然同步。"""
        rows = _dedup_latest(store.rows(MODULE))
        today = datetime.now().date().isoformat()
        return [
            {"label": "待确认告警", "value": sum(1 for row in rows if row.get("status") == "待确认")},
            {"label": "处置中告警", "value": sum(1 for row in rows if row.get("status") == "处置中")},
            {"label": "今日告警数", "value": sum(1 for row in rows if str(row.get("触发时刻", "")).startswith(today))},
            {"label": "阈值口径异常", "value": sum(1 for row in rows if not self._threshold_consistent(row))},
        ]

    def threshold_meta(self) -> dict[str, Any]:
        """把阈值口径暴露给前端，单位与生效范围的可选项以后端这一份为准。"""
        return {"scopes": THRESHOLD_SCOPES, "type_units": ALARM_TYPE_UNITS, "units": ALL_UNITS}

    def _threshold_consistent(self, row: dict[str, Any]) -> bool:
        """结构化字段齐全、能过校验、且展示串与结构化字段一致才算口径正常。"""
        if any(row.get(field) in (None, "") for field in THRESHOLD_FIELDS):
            return False
        normalized, problems = validate_threshold(row, str(row.get("告警类型", "")))
        if problems or normalized is None:
            return False
        try:
            return row.get("触发阈值") == format_threshold(normalized)
        except (KeyError, TypeError, ValueError):
            return False

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        problems = [f"缺少必填字段：{'、'.join(missing)}"] if missing else []

        # 登记时带了阈值字段就走同一条校验口径；完全没带则允许先登记后补阈值。
        threshold_values = {field: values.get(field) for field in THRESHOLD_FIELDS}
        has_threshold_input = any(_raw_text(threshold_values.get(field)) for field in THRESHOLD_FIELDS)
        normalized: dict[str, Any] | None = None
        if has_threshold_input:
            normalized, threshold_problems = validate_threshold(threshold_values, str(values.get("告警类型", "")))
            problems.extend(threshold_problems)
        if problems:
            return None, problems

        rows = store.rows(MODULE)
        code = str(values.get("告警编号", "")).strip()
        # 同一告警编号重复触发只保留最新一条：先摘掉旧记录再登记新记录。
        rows[:] = [row for row in rows if str(row.get("告警编号", "")).strip() != code]
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in ("触发时刻", "处置人员", "关闭时刻"):
            if str(values.get(field) or "").strip():
                entry[field] = values.get(field)
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        if normalized is not None:
            self._write_threshold(entry, normalized)
        rows.append(entry)
        return entry, []

    def apply_threshold(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """保存阈值改动：四项一起校验，全部通过才允许落库。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, [f"告警记录 {entry_id} 不存在或已归档"]
        normalized, problems = validate_threshold(values, str(entry.get("告警类型", "")))
        if problems or normalized is None:
            return None, problems
        self._write_threshold(entry, normalized)
        return entry, []

    def _write_threshold(self, entry: dict[str, Any], normalized: dict[str, Any]) -> None:
        """统一写回：展示串、结构化字段、保存时刻、版本号一次到位。"""
        entry.update(normalized)
        entry["触发阈值"] = format_threshold(normalized)
        entry["阈值保存时刻"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry["阈值版本"] = int(entry.get("阈值版本", 0)) + 1

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
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"告警记录已{action}"
