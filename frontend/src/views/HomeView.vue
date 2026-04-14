<template>
  <section class="home-view">
    <div class="hero">
      <p class="hero-kicker">Community Detection Platform</p>
      <h1>社区检测集成平台</h1>
      <p>围绕“方法选择、异步运行、结果评估、历史复现”构建完整闭环，帮助你更高效地完成社区检测任务配置、执行与结果分析。</p>
    </div>

    <div class="panel-grid">
      <article id="methods" class="panel-card">
        <div class="panel-head">
          <div>
            <h2>方法库</h2>
            <small>Methods · {{ methods.length }}</small>
          </div>
        </div>
        <p v-if="loading" class="hint">正在加载方法列表...</p>
        <ul v-else class="scroll-list">
          <li v-for="method in methods" :key="method.key" class="entity-row">
            <div>
              <strong>{{ method.name }}</strong>
              <p class="method-badges">
                <span class="badge">{{ methodLevelText(method) }}</span>
              </p>
              <p>{{ method.algorithm_note || method.description || '社区检测方法。' }}</p>
            </div>
            <button type="button" @click="openDetail('method', method)">查看详情</button>
          </li>
        </ul>
      </article>

      <article id="datasets" class="panel-card">
        <div class="panel-head">
          <div>
            <h2>数据集</h2>
            <small>Datasets · {{ datasets.length }}</small>
          </div>
        </div>
        <p v-if="loading" class="hint">正在加载数据集...</p>
        <ul v-else class="scroll-list">
          <li v-for="dataset in datasets" :key="dataset.key" class="entity-row">
            <div>
              <strong>{{ dataset.name }}</strong>
              <p>{{ datasetSummary(dataset) }}</p>
              <p class="hint">节点 N={{ dataset.node_count ?? '-' }}，边 E={{ dataset.edge_count ?? '-' }}，社区 C={{ dataset.community_count ?? '-' }}</p>
            </div>
            <button type="button" @click="openDetail('dataset', dataset)">查看详情</button>
          </li>
        </ul>
      </article>

      <article id="metrics" class="panel-card">
        <div class="panel-head">
          <div>
            <h2>评价指标</h2>
            <small>Metrics · {{ metrics.length }}</small>
          </div>
        </div>
        <p v-if="loading" class="hint">正在加载指标配置...</p>
        <ul v-else class="scroll-list">
          <li v-for="metric in metrics" :key="metric.key" class="entity-row">
            <div>
              <strong>{{ metric.name }}</strong>
              <p>{{ metric.description || '用于评估聚类与社区划分质量的指标。' }}</p>
            </div>
            <button type="button" @click="openDetail('metric', metric)">查看详情</button>
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
        <p><strong>标识 Key：</strong> {{ detailModal.item?.key }}</p>
        <p><strong>类型：</strong> {{ detailTypeText }}</p>
        <p><strong>简介：</strong> {{ detailDescription }}</p>
        <p v-if="detailModal.type === 'method' && detailModal.item"><strong>实现层级：</strong> {{ methodLevelText(detailModal.item) }}</p>
        <p v-if="detailModal.type === 'method' && detailModal.item"><strong>算法说明：</strong> {{ detailModal.item.algorithm_note || detailModal.item.description }}</p>
        <ul v-if="detailModal.type === 'dataset' && detailModal.item" class="meta-list">
          <li><strong>拓扑结构：</strong> 是</li>
          <li><strong>节点特征：</strong> {{ detailModal.item.has_features ? '有' : '无' }}</li>
          <li><strong>标签：</strong> {{ detailModal.item.has_labels ? '有' : '无' }}</li>
          <li><strong>节点数：</strong> {{ detailModal.item.node_count ?? '-' }}</li>
          <li><strong>边数：</strong> {{ detailModal.item.edge_count ?? '-' }}</li>
          <li><strong>社区数：</strong> {{ detailModal.item.community_count ?? '-' }}</li>
        </ul>
        <ul v-if="detailModal.type === 'method' && detailModal.item" class="meta-list">
          <li><strong>是否需要 GPU：</strong> {{ detailModal.item.requires_gpu ? '是' : '否' }}</li>
          <li><strong>兼容范围：</strong> {{ methodCompatText(detailModal.item) }}</li>
        </ul>
        <ul v-if="detailModal.type === 'metric' && detailModal.item" class="meta-list">
          <li><strong>是否依赖标签：</strong> {{ detailModal.item.requires_labels ? '是' : '否' }}</li>
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
  const tags = ['拓扑']
  if (dataset.has_features) tags.push('特征')
  if (dataset.has_labels) tags.push('标签')
  return tags.join(' / ')
}

const detailDescription = computed(() => {
  if (!detailModal.item) return ''
  return detailModal.item.description || '暂无补充说明。'
})

const detailTypeText = computed(() => {
  if (detailModal.type === 'method') return '社区检测方法'
  if (detailModal.type === 'dataset') return '实验数据集'
  if (detailModal.type === 'metric') return '评价指标'
  return '-'
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
    loadError.value = err.message || '公开资源加载失败'
  } finally {
    loading.value = false
  }
})
</script>
