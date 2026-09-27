<template>
  <section class="page" data-module="alarm">
    <header class="page-head">
      <div>
        <h2>告警监测管理</h2>
        <p class="page-desc">维护告警记录，围绕告警编号、告警来源、告警类型、触发阈值做登记、筛选与状态流转。</p>
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

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <p v-if="noticeMessage" class="notice-bar">{{ noticeMessage }}</p>

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
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openThreshold(row)">调整阈值</button>
            <button class="link" type="button" @click="openDetail(row)">详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无告警监测数据，可先登记告警记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条告警监测记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createDialog" class="modal-mask" @click.self="createDialog = false">
      <div class="modal">
        <h3>登记告警记录</h3>
        <div class="form-grid">
          <label class="form-item">
            <span>告警编号 *</span>
            <input v-model="createForm['告警编号']" placeholder="如 ALAR-0004；同编号重复触发只保留最新一条" />
          </label>
          <label class="form-item">
            <span>告警来源 *</span>
            <input v-model="createForm['告警来源']" placeholder="如 气温传感器" />
          </label>
          <label class="form-item">
            <span>告警类型 *</span>
            <input v-model="createForm['告警类型']" list="alarm-type-options" placeholder="如 温度告警" />
          </label>
          <label class="form-item">
            <span>触发时刻</span>
            <input v-model="createForm['触发时刻']" placeholder="如 2026-09-27 10:30" />
          </label>
        </div>
        <p class="hint-text">触发阈值可登记后补；填写时下限、上限、单位、生效范围四项一起校验。</p>
        <div class="form-grid">
          <label class="form-item">
            <span>阈值下限</span>
            <input v-model="createForm['阈值下限']" placeholder="如 -40" />
          </label>
          <label class="form-item">
            <span>阈值上限</span>
            <input v-model="createForm['阈值上限']" placeholder="如 45" />
          </label>
          <label class="form-item">
            <span>阈值单位</span>
            <input v-model="createForm['阈值单位']" list="create-unit-options" placeholder="选择或输入单位" />
            <datalist id="create-unit-options">
              <option v-for="unit in createAllowedUnits" :key="unit" :value="unit" />
            </datalist>
            <em class="hint-text">该类型允许单位：{{ createAllowedUnits.join('、') || '—' }}</em>
          </label>
          <label class="form-item">
            <span>生效范围</span>
            <select v-model="createForm['生效范围']">
              <option value="">请选择</option>
              <option v-for="scope in meta.scopes" :key="scope" :value="scope">{{ scope }}</option>
            </select>
          </label>
        </div>
        <p v-if="createError" class="dialog-error">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="createDialog = false">取消</button>
          <button class="btn primary" type="button" @click="submitCreate">保存登记</button>
        </div>
      </div>
    </div>

    <div v-if="thresholdDialog" class="modal-mask" @click.self="thresholdDialog = false">
      <div class="modal">
        <h3>调整触发阈值 · {{ thresholdTarget?.['告警编号'] }}</h3>
        <p class="hint-text">
          告警类型「{{ thresholdTarget?.['告警类型'] }}」允许的单位：{{ thresholdAllowedUnits.join('、') || '—' }}；
          当前取值：{{ thresholdTarget?.['触发阈值'] ?? '—' }}
          <template v-if="thresholdTarget?.['阈值版本']">
            （第 {{ thresholdTarget['阈值版本'] }} 次保存，{{ thresholdTarget['阈值保存时刻'] }}）
          </template>
        </p>
        <div class="form-grid">
          <label class="form-item">
            <span>阈值下限 *</span>
            <input v-model="thresholdForm['阈值下限']" placeholder="如 -40" />
          </label>
          <label class="form-item">
            <span>阈值上限 *</span>
            <input v-model="thresholdForm['阈值上限']" placeholder="如 45" />
          </label>
          <label class="form-item">
            <span>阈值单位 *</span>
            <input v-model="thresholdForm['阈值单位']" list="threshold-unit-options" placeholder="选择或输入单位" />
            <datalist id="threshold-unit-options">
              <option v-for="unit in thresholdAllowedUnits" :key="unit" :value="unit" />
            </datalist>
          </label>
          <label class="form-item">
            <span>生效范围 *</span>
            <select v-model="thresholdForm['生效范围']">
              <option value="">请选择</option>
              <option v-for="scope in meta.scopes" :key="scope" :value="scope">{{ scope }}</option>
            </select>
          </label>
        </div>
        <p v-if="thresholdError" class="dialog-error">{{ thresholdError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="thresholdDialog = false">取消</button>
          <button class="btn primary" type="button" @click="submitThreshold">保存阈值</button>
        </div>
      </div>
    </div>

    <div v-if="detailDialog" class="modal-mask" @click.self="detailDialog = false">
      <div class="modal">
        <h3>告警记录详情 · {{ detailEntry?.['告警编号'] }}</h3>
        <dl v-if="detailEntry" class="detail-list">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detailEntry[field] ?? '—' }}</dd>
          </template>
        </dl>
        <div class="modal-actions">
          <button class="btn" type="button" @click="detailDialog = false">关闭</button>
        </div>
      </div>
    </div>

    <datalist id="alarm-type-options">
      <option v-for="keyword in alarmTypeKeywords" :key="keyword" :value="`${keyword}告警`" />
    </datalist>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type StatCard = { label: string; value: number }
type ThresholdMeta = { scopes: string[]; units: string[]; type_units: Record<string, string[]> }

const ENDPOINT = '/api/alarm'
const columns = ["告警编号", "告警来源", "告警类型", "触发阈值", "触发时刻", "处置人员", "关闭时刻", "告警状态"]
const detailFields = [...columns, "阈值下限", "阈值上限", "阈值单位", "生效范围", "阈值保存时刻", "阈值版本"]
const actions = ["确认告警", "关闭告警", "忽略告警"]
const SNAPSHOT_KEY = 'alarm-threshold-snapshot'

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<StatCard[]>([])
const meta = ref<ThresholdMeta>({ scopes: [], units: [], type_units: {} })
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const createDialog = ref(false)
const createForm = ref<Row>({})
const createError = ref('')
const thresholdDialog = ref(false)
const thresholdForm = ref<Row>({})
const thresholdTarget = ref<Row | null>(null)
const thresholdError = ref('')
const detailDialog = ref(false)
const detailEntry = ref<Row | null>(null)

const alarmTypeKeywords = computed(() => Object.keys(meta.value.type_units))
const createAllowedUnits = computed(() => allowedUnitsFor(String(createForm.value['告警类型'] ?? '')))
const thresholdAllowedUnits = computed(() => allowedUnitsFor(String(thresholdTarget.value?.['告警类型'] ?? '')))

function allowedUnitsFor(alarmType: string): string[] {
  for (const [keyword, units] of Object.entries(meta.value.type_units)) {
    if (alarmType.includes(keyword)) {
      return units
    }
  }
  return meta.value.units
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createError.value = ''
  createDialog.value = true
}

function openThreshold(row: Row) {
  thresholdTarget.value = row
  thresholdForm.value = {
    阈值下限: row['阈值下限'] ?? '',
    阈值上限: row['阈值上限'] ?? '',
    阈值单位: row['阈值单位'] ?? '',
    生效范围: row['生效范围'] ?? '',
  }
  thresholdError.value = ''
  thresholdDialog.value = true
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('告警记录明细读取失败')
    }
    detailEntry.value = (await response.json()) as Row
    detailDialog.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警记录明细读取失败'
  }
}

async function submitCreate() {
  createError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string }
    if (!payload.ok) {
      createError.value = payload.message
      return
    }
    createDialog.value = false
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '告警记录登记失败'
  }
}

async function submitThreshold() {
  thresholdError.value = ''
  const target = thresholdTarget.value
  if (!target) {
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${target.id}/threshold`, {
      method: 'PUT',
      body: JSON.stringify({ values: thresholdForm.value }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string; entry?: Row }
    if (!payload.ok) {
      thresholdError.value = payload.message
      return
    }
    thresholdDialog.value = false
    noticeMessage.value = payload.message
    // 本次保存已是最新口径，先更新本地快照，避免刷新时被误判成“不一致”。
    if (payload.entry) {
      rememberSnapshot(String(payload.entry['告警编号'] ?? ''), String(payload.entry['触发阈值'] ?? ''))
    }
    await reload()
  } catch (error) {
    thresholdError.value = error instanceof Error ? error.message : '触发阈值保存失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string }
    if (!payload.ok) {
      throw new Error(payload.message || '告警监测动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警监测操作失败'
  }
}

function readSnapshot(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(SNAPSHOT_KEY) ?? '{}') as Record<string, string>
  } catch {
    return {}
  }
}

function rememberSnapshot(code: string, threshold: string) {
  if (!code) {
    return
  }
  try {
    const snapshot = readSnapshot()
    snapshot[code] = threshold
    localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(snapshot))
  } catch {
    // 本地快照不可写时跳过，列表取值仍以后端保存结果为准
  }
}

function syncSnapshot(items: Row[]) {
  // 重新进入页面时以后端最后一次保存的取值为准；发现与本地快照不一致时给出说明。
  const previous = readSnapshot()
  const current: Record<string, string> = {}
  let drift = 0
  for (const item of items) {
    const code = String(item['告警编号'] ?? '')
    if (!code) {
      continue
    }
    const saved = String(item['触发阈值'] ?? '')
    current[code] = saved
    if (code in previous && previous[code] !== saved) {
      drift += 1
    }
  }
  try {
    localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(current))
  } catch {
    // 本地快照不可写时跳过，不影响列表展示
  }
  if (drift > 0) {
    noticeMessage.value = `检测到 ${drift} 条告警的触发阈值与上次展示不一致，已按最后一次保存的取值刷新`
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok) {
      throw new Error('告警记录列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    syncSnapshot(rows.value)
    if (statsResponse.ok) {
      stats.value = (await statsResponse.json()) as StatCard[]
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '告警监测列表读取失败'
  }
}

async function loadMeta() {
  try {
    const response = await request(`${ENDPOINT}/threshold-meta`)
    if (response.ok) {
      meta.value = (await response.json()) as ThresholdMeta
    }
  } catch {
    // 口径可选项拉取失败时表单仍可手输，最终以后端校验为准
  }
}

onMounted(() => {
  void loadMeta()
  void reload()
})
</script>

<style scoped>
.notice-bar {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 12px;
  margin: 0 0 12px;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 30;
}
.modal {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 560px;
  max-width: 92vw;
  max-height: 86vh;
  overflow: auto;
}
.modal h3 {
  margin: 0 0 12px;
  font-size: 15px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
  margin-top: 10px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item input,
.form-item select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.hint-text {
  font-size: 12px;
  color: var(--muted);
  font-style: normal;
}
.dialog-error {
  color: #b42318;
  font-size: 12px;
  margin: 10px 0 0;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.detail-list {
  display: grid;
  grid-template-columns: 120px 1fr;
  row-gap: 8px;
  font-size: 13px;
  margin: 0;
}
.detail-list dt {
  color: var(--muted);
}
.detail-list dd {
  margin: 0;
}
</style>
