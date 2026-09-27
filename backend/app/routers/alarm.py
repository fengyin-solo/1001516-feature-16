"""告警监测接口：维护告警记录，覆盖确认告警、关闭告警、忽略告警与阈值调整等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.alarm import AlarmService

router = APIRouter(prefix="/api/alarm", tags=["告警监测"])

service = AlarmService()

LIST_FIELDS = ["告警编号", "告警来源", "告警类型", "触发阈值", "触发时刻", "处置人员", "关闭时刻", "告警状态"]
STATUSES = ["待确认", "处置中", "已关闭", "已忽略"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按告警编号检索"),
    status: str | None = Query(default=None, description="待确认、处置中、已关闭、已忽略"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按告警编号与状态过滤告警监测列表；同一编号只保留最新一条，没有数据时返回空页。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats", response_model=list[dict[str, Any]])
def get_stats() -> list[dict[str, Any]]:
    """统计卡片：与列表读同一份数据，阈值保存后这里同步变化。"""
    return service.stats()


@router.get("/threshold-meta", response_model=dict[str, Any])
def get_threshold_meta() -> dict[str, Any]:
    """阈值口径的可选项（单位、生效范围），前端渲染表单时以后端这份为准。"""
    return service.threshold_meta()


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出告警监测清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "alarm", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条告警记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"告警记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条告警记录；同一告警编号重复触发只保留最新一条，缺字段或阈值不合口径时说明原因。"""
    entry, problems = service.create_entry(payload.values)
    if problems:
        return ActionResult(ok=False, message="；".join(problems))
    return ActionResult(ok=True, message="告警记录已登记，同一编号的历史记录已按最新一条保留", entry=entry)


@router.put("/{entry_id}/threshold", response_model=ActionResult)
def save_threshold(entry_id: int, payload: EntryPayload) -> ActionResult:
    """保存触发阈值：上下限、单位、生效范围一起校验，不通过就不许保存并说明差在哪。"""
    entry, problems = service.apply_threshold(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=f"触发阈值未保存：{'；'.join(problems)}")
    message = f"触发阈值已保存为「{entry['触发阈值']}」（第 {entry['阈值版本']} 次保存，各处以本次保存为准）"
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条告警记录执行确认告警、关闭告警、忽略告警；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
