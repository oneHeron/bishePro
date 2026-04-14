<template>
  <section class="catalog-view">
    <h1>{{ pageTitle }}</h1>
    <p class="hint">Catalog · 展示当前分类下的全部条目及详细介绍。</p>

    <article class="card catalog-card">
      <div class="catalog-toolbar">
        <button type="button" :class="{ active: type === 'methods' }" @click="goType('methods')">方法</button>
        <button type="button" :class="{ active: type === 'datasets' }" @click="goType('datasets')">数据集</button>
        <button type="button" :class="{ active: type === 'metrics' }" @click="goType('metrics')">指标</button>
        <div v-if="type === 'methods' || type === 'datasets'" class="quick-filter catalog-attr-filter">
          <button type="button" :class="{ active: attrFilter === 'all' }" @click="attrFilter = 'all'">全部</button>
          <button type="button" :class="{ active: attrFilter === 'attributed' }" @click="attrFilter = 'attributed'">有属性</button>
          <button type="button" :class="{ active: attrFilter === 'unattributed' }" @click="attrFilter = 'unattributed'">无属性</button>
        </div>
        <div class="catalog-search-wrap">
          <input
            v-model.trim="searchText"
            type="text"
            class="catalog-search-input"
            :placeholder="searchPlaceholder"
          />
        </div>
      </div>
      <p v-if="type === 'methods' || type === 'datasets'" class="hint catalog-filter-note">
        当前分类: {{ attrFilterLabel }}
      </p>

      <p v-if="loading" class="hint">正在加载 {{ pageTitle }}...</p>
      <p v-else-if="!filteredItems.length" class="hint">没有匹配到相关内容。</p>

      <div v-else class="catalog-list">
        <article v-for="item in filteredItems" :key="item.key" class="catalog-item">
          <header>
            <h2 v-html="highlightText(item.name)" />
            <code v-html="highlightText(item.key)" />
          </header>
          <p>{{ detailText(item) }}</p>
          <p v-if="searchText && matchedSnippet(item)" class="catalog-match" v-html="matchedSnippet(item)" />
          <p v-if="type === 'methods'" class="hint">
            <strong>实现级别:</strong> {{ methodLevelText(item) }}
          </p>
          <ul v-if="type === 'datasets'" class="meta-list">
            <li><strong>拓扑结构:</strong> 是</li>
            <li><strong>节点特征:</strong> {{ item.has_features ? '有' : '无' }}</li>
            <li><strong>标签信息:</strong> {{ item.has_labels ? '有' : '无' }}</li>
            <li><strong>节点数:</strong> {{ item.node_count ?? '-' }}</li>
            <li><strong>边数:</strong> {{ item.edge_count ?? '-' }}</li>
            <li><strong>社区数:</strong> {{ item.community_count ?? '-' }}</li>
          </ul>
          <ul v-if="type === 'methods'" class="meta-list">
            <li><strong>类别:</strong> {{ methodCategory(item) }}</li>
            <li><strong>需要 GPU:</strong> {{ item.requires_gpu ? '是' : '否' }}</li>
            <li><strong>兼容性:</strong> {{ methodCompatText(item) }}</li>
            <li><strong>算法说明:</strong> {{ item.algorithm_note || item.description }}</li>
          </ul>
          <ul v-if="type === 'metrics'" class="meta-list">
            <li><strong>依赖标签:</strong> {{ item.requires_labels ? '是' : '否' }}</li>
          </ul>
        </article>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const methods = ref([])
const datasets = ref([])
const metrics = ref([])
const searchText = ref('')
const attrFilter = ref('all')

const type = computed(() => {
  const t = route.params.type
  if (t === 'methods' || t === 'datasets' || t === 'metrics') return t
  return 'methods'
})

const pageTitle = computed(() => {
  if (type.value === 'methods') return '全部方法'
  if (type.value === 'datasets') return '全部数据集'
  return '全部指标'
})

const items = computed(() => {
  if (type.value === 'methods') return methods.value
  if (type.value === 'datasets') return datasets.value
  return metrics.value
})
const searchPlaceholder = computed(() => {
  if (type.value === 'methods') return '按名称 / Key / 描述搜索方法'
  if (type.value === 'datasets') return '按名称 / Key / 描述搜索数据集'
  return '按名称 / Key / 描述搜索指标'
})
const filteredItems = computed(() => {
  const attrFiltered = items.value.filter((item) => matchAttrFilter(item))
  const keyword = normalizeText(searchText.value)
  if (!keyword) return attrFiltered
  const tokens = keyword.split(/\s+/).filter(Boolean)
  return attrFiltered.filter((item) => {
    const haystack = normalizeText(
      [
        item?.name,
        item?.key,
        item?.description,
        item?.algorithm_note,
        item?.source,
      ]
        .filter(Boolean)
        .join(' ')
    )
    return tokens.every((token) => haystack.includes(token))
  })
})
const attrFilterLabel = computed(() => {
  if (attrFilter.value === 'attributed') return '有属性'
  if (attrFilter.value === 'unattributed') return '无属性'
  return '全部'
})

function normalizeText(text) {
  return String(text || '').toLowerCase()
}

function matchAttrFilter(item) {
  if (type.value === 'metrics' || attrFilter.value === 'all') return true
  if (type.value === 'datasets') {
    if (attrFilter.value === 'attributed') return item.has_features === true
    if (attrFilter.value === 'unattributed') return item.has_features !== true
    return true
  }
  if (type.value === 'methods') {
    const supportsAttr = item.supports_attributed !== false
    const supportsUnattr = item.supports_unattributed !== false
    if (attrFilter.value === 'attributed') return supportsAttr
    if (attrFilter.value === 'unattributed') return supportsUnattr
    return true
  }
  return true
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeRegExp(text) {
  return String(text || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function searchTokens() {
  return normalizeText(searchText.value).split(/\s+/).filter(Boolean)
}

function highlightText(text) {
  const raw = String(text || '')
  const escaped = escapeHtml(raw)
  const tokens = searchTokens()
  if (!tokens.length) return escaped
  const pattern = tokens.map((t) => escapeRegExp(t)).join('|')
  if (!pattern) return escaped
  return escaped.replace(new RegExp(`(${pattern})`, 'gi'), '<mark>$1</mark>')
}

function matchedSnippet(item) {
  const tokens = searchTokens()
  if (!tokens.length) return ''
  const candidates = [
    item?.description,
    item?.algorithm_note,
    item?.name,
    item?.key,
    item?.source,
  ]
    .filter(Boolean)
    .map((v) => String(v))

  for (const text of candidates) {
    const lowered = normalizeText(text)
    let hit = -1
    for (const token of tokens) {
      const idx = lowered.indexOf(token)
      if (idx !== -1 && (hit === -1 || idx < hit)) hit = idx
    }
    if (hit === -1) continue

    const start = Math.max(0, hit - 24)
    const end = Math.min(text.length, hit + 48)
    const prefix = start > 0 ? '...' : ''
    const suffix = end < text.length ? '...' : ''
    return `${prefix}${highlightText(text.slice(start, end))}${suffix}`
  }
  return ''
}

function methodCategory(item) {
  const supportsAttr = item.supports_attributed !== false
  const supportsUnattr = item.supports_unattributed !== false
  if (supportsAttr && supportsUnattr) return '通用型（有属性/无属性）'
  if (supportsAttr) return '有属性'
  if (supportsUnattr) return '无属性'
  return '其他'
}

function methodCompatText(method) {
  const supportsAttr = method.supports_attributed !== false
  const supportsUnattr = method.supports_unattributed !== false
  if (supportsAttr && supportsUnattr) return '支持有属性/无属性网络'
  if (supportsAttr) return '仅支持有属性网络'
  if (supportsUnattr) return '仅支持无属性网络'
  return '兼容性未声明'
}

function methodLevelText(method) {
  const levelMap = {
    approximate: '近似实现',
    "standard-lite": '标准实现（轻量）',
    standard: '标准实现',
    template: '复杂模板（待你替换核心算法）'
  }
  return levelMap[method.implementation_level] || method.implementation_level || '近似实现'
}

function detailText(item) {
  if (item.description) return item.description
  if (type.value === 'datasets') {
    const tags = ['拓扑']
    if (item.has_features) tags.push('特征')
    if (item.has_labels) tags.push('标签')
    return `数据集包含：${tags.join(' / ')}`
  }
  if (type.value === 'metrics') return '用于评估社区检测结果质量的指标。'
  return '社区检测算法。'
}

function goType(nextType) {
  searchText.value = ''
  attrFilter.value = 'all'
  router.push(`/catalog/${nextType}`)
}

async function load() {
  loading.value = true
  try {
    if (!methods.value.length) methods.value = await api.getMethods()
    if (!datasets.value.length) datasets.value = await api.getDatasets()
    if (!metrics.value.length) metrics.value = await api.getMetrics()
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.type,
  () => load(),
  { immediate: true }
)

onMounted(load)
</script>
