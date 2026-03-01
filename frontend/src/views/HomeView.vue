<template>
  <section class="home-view">
    <div class="hero">
      <h1>A Comprehensive Platform for Community Detection</h1>
      <p>Integrate, run and evaluate community detection methods across diverse datasets and metrics.</p>
    </div>

    <div class="panel-grid">
      <article id="methods" class="panel-card">
        <div class="panel-head">
          <h2>Algorithms</h2>
          <small>{{ methods.length }}</small>
        </div>
        <p v-if="loading" class="hint">Loading methods...</p>
        <ul v-else class="scroll-list">
          <li v-for="method in methods" :key="method.key" class="entity-row">
            <div>
              <strong>{{ method.name }}</strong>
              <p class="method-badges">
                <span class="badge">{{ methodLevelText(method) }}</span>
              </p>
              <p>{{ method.algorithm_note || method.description || 'Community detection method.' }}</p>
            </div>
            <button type="button" @click="openDetail('method', method)">View Details</button>
          </li>
        </ul>
      </article>

      <article id="datasets" class="panel-card">
        <div class="panel-head">
          <h2>Datasets</h2>
          <small>{{ datasets.length }}</small>
        </div>
        <p v-if="loading" class="hint">Loading datasets...</p>
        <ul v-else class="scroll-list">
          <li v-for="dataset in datasets" :key="dataset.key" class="entity-row">
            <div>
              <strong>{{ dataset.name }}</strong>
              <p>{{ datasetSummary(dataset) }}</p>
              <p class="hint">N={{ dataset.node_count ?? '-' }}, E={{ dataset.edge_count ?? '-' }}, C={{ dataset.community_count ?? '-' }}</p>
            </div>
            <button type="button" @click="openDetail('dataset', dataset)">View Details</button>
          </li>
        </ul>
      </article>

      <article id="metrics" class="panel-card">
        <div class="panel-head">
          <h2>Metrics</h2>
          <small>{{ metrics.length }}</small>
        </div>
        <p v-if="loading" class="hint">Loading metrics...</p>
        <ul v-else class="scroll-list">
          <li v-for="metric in metrics" :key="metric.key" class="entity-row">
            <div>
              <strong>{{ metric.name }}</strong>
              <p>{{ metric.description || 'Evaluation metric for clustering/community quality.' }}</p>
            </div>
            <button type="button" @click="openDetail('metric', metric)">View Details</button>
          </li>
        </ul>
      </article>
    </div>

    <p v-if="loadError" class="msg">{{ loadError }}</p>

    <div v-if="detailModal.visible" class="detail-mask" @click.self="closeDetail">
      <article class="detail-modal">
        <header>
          <h2>{{ detailModal.item?.name }}</h2>
          <button type="button" class="close-btn" @click="closeDetail">×</button>
        </header>
        <p><strong>Key:</strong> {{ detailModal.item?.key }}</p>
        <p><strong>Type:</strong> {{ detailModal.type }}</p>
        <p><strong>Description:</strong> {{ detailDescription }}</p>
        <p v-if="detailModal.type === 'method' && detailModal.item"><strong>Implementation:</strong> {{ methodLevelText(detailModal.item) }}</p>
        <p v-if="detailModal.type === 'method' && detailModal.item"><strong>Algorithm Note:</strong> {{ detailModal.item.algorithm_note || detailModal.item.description }}</p>
        <ul v-if="detailModal.type === 'dataset' && detailModal.item" class="meta-list">
          <li><strong>Topology:</strong> Yes</li>
          <li><strong>Features:</strong> {{ detailModal.item.has_features ? 'Yes' : 'No' }}</li>
          <li><strong>Labels:</strong> {{ detailModal.item.has_labels ? 'Yes' : 'No' }}</li>
          <li><strong>Nodes:</strong> {{ detailModal.item.node_count ?? '-' }}</li>
          <li><strong>Edges:</strong> {{ detailModal.item.edge_count ?? '-' }}</li>
          <li><strong>Communities:</strong> {{ detailModal.item.community_count ?? '-' }}</li>
        </ul>
        <ul v-if="detailModal.type === 'method' && detailModal.item" class="meta-list">
          <li><strong>Requires GPU:</strong> {{ detailModal.item.requires_gpu ? 'Yes' : 'No' }}</li>
          <li><strong>Compatibility:</strong> {{ methodCompatText(detailModal.item) }}</li>
        </ul>
        <ul v-if="detailModal.type === 'metric' && detailModal.item" class="meta-list">
          <li><strong>Requires Labels:</strong> {{ detailModal.item.requires_labels ? 'Yes' : 'No' }}</li>
        </ul>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api/client'

const loading = ref(true)
const loadError = ref('')
const methods = ref([])
const datasets = ref([])
const metrics = ref([])

const detailModal = reactive({
  visible: false,
  type: '',
  item: null
})

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

function datasetSummary(dataset) {
  const tags = ['Topology']
  if (dataset.has_features) tags.push('Features')
  if (dataset.has_labels) tags.push('Labels')
  return tags.join(' + ')
}

const detailDescription = computed(() => {
  if (!detailModal.item) return ''
  return detailModal.item.description || 'No additional description.'
})

function openDetail(type, item) {
  detailModal.visible = true
  detailModal.type = type
  detailModal.item = item
}

function closeDetail() {
  detailModal.visible = false
  detailModal.type = ''
  detailModal.item = null
}

onMounted(async () => {
  try {
    methods.value = await api.getMethods()
    datasets.value = await api.getDatasets()
    metrics.value = await api.getMetrics()
  } catch (err) {
    loadError.value = err.message || 'Failed to load public resources'
  } finally {
    loading.value = false
  }
})
</script>
