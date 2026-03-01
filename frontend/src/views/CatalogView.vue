<template>
  <section class="catalog-view">
    <h1>{{ pageTitle }}</h1>
    <p class="hint">展示当前分类下的全部条目及详细介绍。</p>

    <article class="card catalog-card">
      <div class="catalog-toolbar">
        <button type="button" :class="{ active: type === 'methods' }" @click="goType('methods')">Methods</button>
        <button type="button" :class="{ active: type === 'datasets' }" @click="goType('datasets')">Datasets</button>
        <button type="button" :class="{ active: type === 'metrics' }" @click="goType('metrics')">Metrics</button>
      </div>

      <p v-if="loading" class="hint">Loading {{ type }}...</p>
      <p v-else-if="!items.length" class="hint">No data.</p>

      <div v-else class="catalog-list">
        <article v-for="item in items" :key="item.key" class="catalog-item">
          <header>
            <h2>{{ item.name }}</h2>
            <code>{{ item.key }}</code>
          </header>
          <p>{{ detailText(item) }}</p>
          <p v-if="type === 'methods'" class="hint">
            <strong>实现级别:</strong> {{ methodLevelText(item) }}
          </p>
          <ul v-if="type === 'datasets'" class="meta-list">
            <li><strong>Topology:</strong> Yes</li>
            <li><strong>Features:</strong> {{ item.has_features ? 'Yes' : 'No' }}</li>
            <li><strong>Labels:</strong> {{ item.has_labels ? 'Yes' : 'No' }}</li>
            <li><strong>Nodes:</strong> {{ item.node_count ?? '-' }}</li>
            <li><strong>Edges:</strong> {{ item.edge_count ?? '-' }}</li>
            <li><strong>Communities:</strong> {{ item.community_count ?? '-' }}</li>
          </ul>
          <ul v-if="type === 'methods'" class="meta-list">
            <li><strong>Category:</strong> {{ methodCategory(item) }}</li>
            <li><strong>Requires GPU:</strong> {{ item.requires_gpu ? 'Yes' : 'No' }}</li>
            <li><strong>Compatibility:</strong> {{ methodCompatText(item) }}</li>
            <li><strong>Algorithm Note:</strong> {{ item.algorithm_note || item.description }}</li>
          </ul>
          <ul v-if="type === 'metrics'" class="meta-list">
            <li><strong>Requires Labels:</strong> {{ item.requires_labels ? 'Yes' : 'No' }}</li>
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

const type = computed(() => {
  const t = route.params.type
  if (t === 'methods' || t === 'datasets' || t === 'metrics') return t
  return 'methods'
})

const pageTitle = computed(() => {
  if (type.value === 'methods') return 'All Methods'
  if (type.value === 'datasets') return 'All Datasets'
  return 'All Metrics'
})

const items = computed(() => {
  if (type.value === 'methods') return methods.value
  if (type.value === 'datasets') return datasets.value
  return metrics.value
})

function methodCategory(item) {
  const supportsAttr = item.supports_attributed !== false
  const supportsUnattr = item.supports_unattributed !== false
  if (supportsAttr && supportsUnattr) return '有属性/无属性'
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
    const tags = ['Topology']
    if (item.has_features) tags.push('Features')
    if (item.has_labels) tags.push('Labels')
    return `Dataset supports: ${tags.join(' + ')}`
  }
  if (type.value === 'metrics') return 'Evaluation metric for community detection results.'
  return 'Community detection algorithm.'
}

function goType(nextType) {
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
