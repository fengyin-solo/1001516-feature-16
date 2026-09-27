<template>
  <section class="page" data-module="alarm">
    <header class="page-head">
      <div>
        <h2>告警监测管理</h2>
        <p class="page-desc">触发阈值按「下限~上限 单位（生效范围）」一条口径维护，上下限、单位与生效范围一起校验。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记告警记录</button>
        <button class="btn" type="button" @click="exportRows">导出告警监测清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p v-if="syncNotice" class="sync-notice">{{ syncNotice }}</p>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>告警编号</span>
        <input v-model="filters.keyword" placeholder="按告警编号检索" />
      </label>
      <label class="filter-item">
        <span>告警状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button class="link" type="button" @click="openEdit(row)">编辑阈值</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无告警监测数据，可先登记告警记录</td>
        </tr>
      </tbody>
    </table>

    <section v-if="detail" class="detail-panel">
      <header class="detail-head">
        <h3>告警详情：{{ detail['告警编号'] }}</h3>
        <button class="btn ghost" type="button" @click="detail = null">收起</button>
      </header>
      <dl class="detail-grid">
        <template v-for="field in detailFields" :key="field">
          <dt>{{ field }}</dt>
          <dd>{{ detail[field] ?? '—' }}</dd>
        </template>
      </dl>
    </section>

    <div v-if="editing" class="dialog-mask" @click.self="editing = false">
      <form class="dialog" @submit.prevent="submitEdit">
        <h3>{{ editMode === 'create' ? '登记告警记录' : `编辑触发阈值：${editForm['告警编号']}` }}</h3>
        <template v-if="editMode === 'create'">
          <label class="form-item">
            <span>告警编号</span>
            <input v-model="editForm['告警编号']" placeholder="如 ALAR-0004" required />
          </label>
          <label class="form-item">
            <span>告警来源</span>
            <input v-model="editForm['告警来源']" placeholder="如 气温传感器 SENS-0001" required />
          </label>
        </template>
        <label class="form-item">
          <span>告警类型</span>
          <select v-model="editForm['告警类型']" @change="syncUnitWithType">
            <option v-for="type in alarmTypes" :key="type" :value="type">{{ type }}</option>
          </select>
        </label>
        <div class="form-row">
          <label class="form-item">
            <span>阈值下限</span>
            <input v-model="editForm['阈值下限']" type="number" step="any" required />
          </label>
          <label class="form-item">
            <span>阈值上限</span>
            <input v-model="editForm['阈值上限']" type="number" step="any" required />
          </label>
        </div>
        <label class="form-item">
          <span>阈值单位</span>
          <select v-model="editForm['阈值单位']">
            <option v-for="unit in unitOptions" :key="unit" :value="unit">{{ unit }}</option>
          </select>
        </label>
        <label class="form-item">
          <span>生效范围</span>
          <input v-model="editForm['生效范围']" placeholder="如 全站网 或 STAT-0001" required />
        </label>
        <template v-if="editMode === 'create'">
          <label class="form-item">
            <span>触发时刻</span>
            <input v-model="editForm['触发时刻']" placeholder="如 2026-09-27 08:15" />
          </label>
          <label class="form-item">
            <span>处置人员</span>
            <input v-model="editForm['处置人员']" placeholder="如 值班管理员" />
          </label>
        </template>
        <p class="form-hint">保存时会一起校验上下限、单位与生效范围：上限低于下限、单位与告警类型不匹配都不会保存。</p>
        <p v-if="editError" class="error-text">{{ editError }}</p>
        <footer class="dialog-actions">
          <button class="btn primary" type="submit">保存</button>
          <button class="btn ghost" type="button" @click="editing = false">取消</button>
        </footer>
      </form>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条告警监测记录</span>
      <span v-if="okMessage" class="ok-text">{{ okMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type StatCard = { label: string; value: number }

const ENDPOINT = '/api/alarm'
const SNAPSHOT_KEY = 'alarm-threshold-snapshot'
const columns = ["告警编号", "告警来源", "告警类型", "触发阈值", "触发时刻", "处置人员", "关闭时刻", "告警状态"]
const detailFields = ["告警编号", "告警来源", "告警类型", "阈值下限", "阈值上限", "阈值单位", "生效范围", "触发阈值", "触发时刻", "处置人员", "关闭时刻", "告警状态"]
const actions = ["确认告警", "关闭告警", "忽略告警"]
const statuses = ["待确认", "处置中", "已关闭", "已忽略"]
// 单位口径以后端 /api/alarm/stats 下发的为准，这里只留一份兜底，保证统计未加载时表单也能用。
const DEFAULT_TYPE_UNITS: Record<string, string[]> = {
  '温度告警': ['℃'],
  '湿度告警': ['%RH'],
  '风速告警': ['m/s'],
  '气压告警': ['hPa'],
  '降水告警': ['mm'],
  '电压告警': ['V'],
  '数据缺报告警': ['次'],
}

const rows = ref<Row[]>([])
const stats = ref<StatCard[]>([])
const total = ref(0)
const errorMessage = ref('')
const okMessage = ref('')
const syncNotice = ref('')
const filters = ref({ keyword: '', status: '' })
const detail = ref<Row | null>(null)
const typeUnits = ref<Record<string, string[]>>(DEFAULT_TYPE_UNITS)

const editing = ref(false)
const editMode = ref<'create' | 'threshold'>('threshold')
const editingId = ref<number | null>(null)
const editForm = reactive<Record<string, string>>({})
const editError = ref('')

const alarmTypes = computed(() => Object.keys(typeUnits.value))
const unitOptions = computed(() => typeUnits.value[editForm['告警类型']] ?? [])

let snapshotChecked = false

function readSnapshot(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(SNAPSHOT_KEY) ?? '{}') as Record<string, string>
  } catch {
    return {}
  }
}

function writeSnapshot(snapshot: Record<string, string>) {
  localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(snapshot))
}

function collectThresholds(list: Row[]): Record<string, string> {
  const snapshot: Record<string, string> = {}
  for (const row of list) {
    const code = String(row['告警编号'] ?? '')
    if (code) {
      snapshot[code] = String(row['触发阈值'] ?? '')
    }
  }
  return snapshot
}

function reconcileSnapshot() {
  const current = collectThresholds(rows.value)
  if (!snapshotChecked) {
    snapshotChecked = true
    const cached = readSnapshot()
    const diffs: string[] = []
    for (const [code, saved] of Object.entries(current)) {
      const cachedValue = cached[code]
      if (cachedValue !== undefined && cachedValue !== saved) {
        diffs.push(`${code}（缓存「${cachedValue || '—'}」→ 最后保存「${saved || '—'}」）`)
      }
    }
    if (diffs.length) {
      syncNotice.value = `检测到本地缓存的触发阈值与最后一次保存不一致，已按最后保存的取值刷新：${diffs.join('；')}`
    }
  }
  // 只合并当前页取值，避免筛选状态下把缓存里其他编号冲掉。
  writeSnapshot({ ...readSnapshot(), ...current })
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function resetEditForm(values: Record<string, string>) {
  for (const key of Object.keys(editForm)) {
    delete editForm[key]
  }
  Object.assign(editForm, values)
  editError.value = ''
  editing.value = true
}

function openCreate() {
  editMode.value = 'create'
  editingId.value = null
  const defaultType = alarmTypes.value[0] ?? ''
  resetEditForm({
    告警编号: '',
    告警来源: '',
    告警类型: defaultType,
    阈值下限: '',
    阈值上限: '',
    阈值单位: (typeUnits.value[defaultType] ?? [''])[0] ?? '',
    生效范围: '',
    触发时刻: '',
    处置人员: '',
  })
}

function openEdit(row: Row) {
  editMode.value = 'threshold'
  editingId.value = Number(row.id)
  resetEditForm({
    告警编号: String(row['告警编号'] ?? ''),
    告警类型: String(row['告警类型'] ?? ''),
    阈值下限: String(row['阈值下限'] ?? ''),
    阈值上限: String(row['阈值上限'] ?? ''),
    阈值单位: String(row['阈值单位'] ?? ''),
    生效范围: String(row['生效范围'] ?? ''),
  })
}

function syncUnitWithType() {
  if (!unitOptions.value.includes(editForm['阈值单位'])) {
    editForm['阈值单位'] = unitOptions.value[0] ?? ''
  }
}

async function submitEdit() {
  editError.value = ''
  const isCreate = editMode.value === 'create'
  const url = isCreate ? ENDPOINT : `${ENDPOINT}/${editingId.value}`
  try {
    const response = await request(url, {
      method: isCreate ? 'POST' : 'PUT',
      body: JSON.stringify({ values: { ...editForm } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '触发阈值保存失败')
    }
    editing.value = false
    okMessage.value = payload.message ?? '触发阈值已保存'
    await reload()
  } catch (error) {
    editError.value = error instanceof Error ? error.message : '触发阈值保存失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  okMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '告警监测动作未生效，请稍后重试')
    }
    okMessage.value = payload.message ?? `告警记录已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警监测操作失败'
  }
}

async function refreshDetail(id: number) {
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    if (!response.ok) {
      detail.value = null
      return
    }
    detail.value = (await response.json()) as Row
  } catch {
    detail.value = null
  }
}

async function openDetail(row: Row) {
  await refreshDetail(Number(row.id))
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) {
    query.set('keyword', filters.value.keyword)
  }
  if (filters.value.status) {
    query.set('status', filters.value.status)
  }
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok) {
      throw new Error('告警记录列表读取失败')
    }
    if (!statsResponse.ok) {
      throw new Error('告警统计读取失败')
    }
    const payload = await listResponse.json()
    const statsPayload = await statsResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stats.value = statsPayload.cards ?? []
    typeUnits.value = statsPayload.typeUnits ?? DEFAULT_TYPE_UNITS
    reconcileSnapshot()
    if (detail.value) {
      await refreshDetail(Number(detail.value.id))
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警监测列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.sync-notice {
  background: #fff8e6;
  border: 1px solid #f0c36d;
  border-radius: 6px;
  color: #8a5a00;
  font-size: 12px;
  padding: 8px 10px;
}
.detail-panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-top: 12px;
  padding: 12px 16px;
}
.detail-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
}
.detail-head h3 {
  font-size: 14px;
  margin: 0;
}
.detail-grid {
  display: grid;
  grid-template-columns: 120px 1fr 120px 1fr;
  gap: 6px 12px;
  margin: 10px 0 0;
}
.detail-grid dt {
  color: var(--muted);
  font-size: 12px;
}
.detail-grid dd {
  font-size: 13px;
  margin: 0;
}
.dialog-mask {
  background: rgba(15, 23, 42, 0.4);
  inset: 0;
  position: fixed;
  z-index: 10;
}
.dialog {
  background: #fff;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 8vh auto;
  max-width: 440px;
  padding: 18px 20px;
}
.dialog h3 {
  font-size: 15px;
  margin: 0;
}
.form-item span {
  color: var(--muted);
  display: block;
  font-size: 12px;
  margin-bottom: 2px;
}
.form-item input,
.form-item select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  width: 100%;
}
.form-row {
  display: flex;
  gap: 10px;
}
.form-row .form-item {
  flex: 1;
}
.form-hint {
  color: var(--muted);
  font-size: 12px;
  margin: 0;
}
.dialog-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
.ok-text {
  color: #067647;
}
</style>
