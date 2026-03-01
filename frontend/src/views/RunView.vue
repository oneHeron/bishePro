<template>
  <section class="run-view">
    <h1>Submit a New Task</h1>
    <p v-if="!token" class="msg">未登录：当前只能配置任务，提交前请先登录。</p>
    <p v-if="loading" class="hint">正在加载方法、数据集和指标...</p>
    <p v-if="loadError" class="msg">{{ loadError }}</p>

    <div class="step-grid">
      <article class="step-card">
        <h2>Step 1: Select Method</h2>
        <div class="quick-filter">
          <button type="button" :class="{ active: methodFilter === 'all' }" @click="methodFilter = 'all'">全部</button>
          <button type="button" :class="{ active: methodFilter === 'attributed' }" @click="methodFilter = 'attributed'">有属性</button>
          <button type="button" :class="{ active: methodFilter === 'unattributed' }" @click="methodFilter = 'unattributed'">无属性</button>
        </div>
        <label>
          Method
          <select v-model="form.method_key" :disabled="loading || !!loadError" required>
            <option v-for="method in filteredMethods" :key="method.key" :value="method.key">{{ method.name }}</option>
          </select>
        </label>
        <p v-if="selectedMethod" class="hint method-note">
          <strong>{{ methodLevelText(selectedMethod) }}</strong>
          · {{ methodCompatText(selectedMethod) }}
          · {{ selectedMethod.algorithm_note || selectedMethod.description }}
        </p>
      </article>

      <article class="step-card">
        <h2>Step 2: Select Dataset</h2>
        <div class="quick-filter">
          <button type="button" :class="{ active: datasetFilter === 'all' }" @click="datasetFilter = 'all'">全部</button>
          <button type="button" :class="{ active: datasetFilter === 'attributed' }" @click="datasetFilter = 'attributed'">有属性</button>
          <button type="button" :class="{ active: datasetFilter === 'unattributed' }" @click="datasetFilter = 'unattributed'">无属性</button>
        </div>

        <div class="scroll-box">
          <label v-for="dataset in filteredDatasets" :key="dataset.key" class="dataset-option">
            <input v-model="form.dataset_key" type="radio" :value="dataset.key" :disabled="loading || !!loadError" />
            <span>
              <strong>{{ dataset.name }}</strong>
              <small>{{ datasetTag(dataset) }}</small>
            </span>
          </label>
          <p v-if="!filteredDatasets.length" class="hint">该筛选条件下暂无数据集</p>
        </div>
      </article>

      <article class="step-card">
        <h2>Step 3: Choose Metrics</h2>
        <div class="scroll-box">
          <label v-for="metric in metrics" :key="metric.key" class="metric-option">
            <input v-model="form.metric_keys" type="checkbox" :value="metric.key" :disabled="loading || !!loadError" />
            <span>
              <strong>{{ metric.name }}</strong>
              <small>{{ metric.description || metric.key }}</small>
            </span>
          </label>
        </div>
      </article>
    </div>

    <article class="config-card">
      <h2>Run Configuration</h2>

      <section class="method-params-box">
        <div class="method-params-head">
          <h3>Method Parameters</h3>
          <button type="button" class="copy-btn" :disabled="!form.method_key" @click="resetCurrentMethodDefaults">恢复默认值</button>
        </div>
        <p class="hint">根据当前方法显示参数表单；提交时会自动写入 `params`。如果数据集有已知社区数，`num_clusters` 会自动填充。</p>
        <div class="method-params-grid">
          <label v-for="field in currentMethodFields" :key="field.key">
            {{ field.label }}
            <input
              v-if="field.type === 'number'"
              v-model.number="methodParams[field.key]"
              :min="field.min"
              :max="field.max"
              :step="field.step || 1"
              :disabled="field.locked === true"
              type="number"
            />
            <input v-else v-model="methodParams[field.key]" :placeholder="field.placeholder || ''" :disabled="field.locked === true" type="text" />
            <small class="hint">{{ field.help }}</small>
            <small v-if="paramErrors[field.key]" class="msg">{{ paramErrors[field.key] }}</small>
          </label>
        </div>
      </section>

      <div class="mode-toggle">
        <button type="button" :class="{ active: runMode === 'local' }" @click="runMode = 'local'">Local</button>
        <button type="button" :class="{ active: runMode === 'remote' }" @click="runMode = 'remote'">Remote Server (Beta)</button>
      </div>
      <div v-if="runMode === 'remote'" class="remote-grid">
        <label>Server IP <input v-model="remote.ip" type="text" placeholder="192.168.1.100" /></label>
        <label>SSH Port <input v-model.number="remote.port" type="number" placeholder="22" /></label>
        <label>Username <input v-model="remote.username" type="text" placeholder="runner" /></label>
        <label>Private Key <input v-model="remote.key_file" type="text" placeholder="~/.ssh/id_rsa" /></label>
      </div>
      <label>
        Random Seed
        <input v-model.number="form.seed" type="number" :disabled="loading || !!loadError" />
      </label>

      <details>
        <summary>Advanced Params (JSON Override)</summary>
        <label>
          Extra Params (JSON)
          <textarea v-model="advancedParamsText" rows="4" placeholder="{}" />
        </label>
      </details>

      <button class="submit-btn" type="button" :disabled="submitDisabled" @click="submitRun">Submit Task</button>
      <p v-if="paramErrorMessage" class="msg">{{ paramErrorMessage }}</p>
      <p :class="messageClass">{{ msg }}</p>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { getToken } from '../stores/auth'
import { pushRunId } from '../stores/history'

const RUN_FORM_CACHE_KEY = 'community_platform_run_form_cache'

const router = useRouter()
const token = ref(getToken())
const loading = ref(true)
const loadError = ref('')
const msg = ref('')
const runMode = ref('local')
const advancedParamsText = ref('{}')

const methods = ref([])
const datasets = ref([])
const metrics = ref([])
const methodFilter = ref('all')
const datasetFilter = ref('all')
const methodParams = reactive({})

const form = reactive({
  method_key: '',
  dataset_key: '',
  metric_keys: [],
  seed: 42
})

const remote = reactive({
  ip: '',
  port: 22,
  username: '',
  key_file: ''
})

const methodParamSchema = {
  louvain: [{ key: 'max_iter', label: 'Max Iterations', type: 'number', min: 1, max: 500, step: 1, default: 24, help: '标签传播最大迭代次数' }],
  kmeans: [{ key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: 'K-Means 聚类簇数' }],
  nmf: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: 'NMF 后聚类簇数' },
    { key: 'nmf_iter', label: 'NMF Iterations', type: 'number', min: 1, max: 2000, step: 1, default: 40, help: 'NMF 分解迭代轮次' }
  ],
  deepwalk: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: 'embedding 后聚类簇数' },
    { key: 'embedding_dim', label: 'Embedding Dim', type: 'number', min: 2, max: 1024, step: 1, default: 16, help: '节点向量维度' },
    { key: 'walk_length', label: 'Walk Length', type: 'number', min: 1, max: 1000, step: 1, default: 20, help: '每次随机游走长度' },
    { key: 'num_walks', label: 'Num Walks', type: 'number', min: 1, max: 1000, step: 1, default: 10, help: '每个节点游走次数' }
  ],
  node2vec: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: 'embedding 后聚类簇数' },
    { key: 'embedding_dim', label: 'Embedding Dim', type: 'number', min: 2, max: 1024, step: 1, default: 16, help: '节点向量维度' },
    { key: 'walk_length', label: 'Walk Length', type: 'number', min: 1, max: 1000, step: 1, default: 24, help: '每次随机游走长度' },
    { key: 'num_walks', label: 'Num Walks', type: 'number', min: 1, max: 1000, step: 1, default: 12, help: '每个节点游走次数' }
  ],
  fn: [{ key: 'max_iter', label: 'Max Iterations', type: 'number', min: 1, max: 500, step: 1, default: 20, help: '层次聚合迭代次数' }],
  sc: [{ key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: '谱聚类目标簇数' }],
  kl: [{ key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 2, help: 'KL 二分默认 2，>2 时回退嵌入聚类' }],
  mdnp: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: '分解后聚类簇数' },
    { key: 'nmf_iter', label: 'NMF Iterations', type: 'number', min: 1, max: 2000, step: 1, default: 32, help: '矩阵分解迭代轮次' }
  ],
  dnr: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: '聚类簇数' },
    { key: 'hidden_dim', label: 'Hidden Dim', type: 'number', min: 2, max: 512, step: 1, default: 8, help: '编码器隐藏维度' }
  ],
  pca: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: '降维后聚类簇数' },
    { key: 'pca_dim', label: 'PCA Dim', type: 'number', min: 1, max: 256, step: 1, default: 2, help: '降维目标维度' }
  ],
  dsacd: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: '聚类簇数' },
    { key: 'sparse_dim', label: 'Sparse Dim', type: 'number', min: 2, max: 512, step: 1, default: 10, help: '稀疏编码维度' }
  ],
  gn: [{ key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: '分裂目标社区数' }],
  le: [{ key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: 'LE 后聚类簇数' }],
  lpa: [{ key: 'max_iter', label: 'Max Iterations', type: 'number', min: 1, max: 500, step: 1, default: 32, help: '标签传播迭代次数' }],
  cnm: [{ key: 'max_iter', label: 'Max Iterations', type: 'number', min: 1, max: 500, step: 1, default: 20, help: '贪心聚合迭代次数' }],
  fua: [{ key: 'max_iter', label: 'Max Iterations', type: 'number', min: 1, max: 500, step: 1, default: 26, help: '模块度优化迭代次数' }],
  infomap: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: '流压缩聚类簇数' },
    { key: 'walk_length', label: 'Walk Length', type: 'number', min: 1, max: 1000, step: 1, default: 18, help: '随机游走长度' },
    { key: 'num_walks', label: 'Num Walks', type: 'number', min: 1, max: 1000, step: 1, default: 10, help: '每个节点游走次数' }
  ],
  edmot: [{ key: 'max_iter', label: 'Max Iterations', type: 'number', min: 1, max: 500, step: 1, default: 24, help: '模体增强后的传播迭代次数' }],
  cdme: [{ key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 1, max: 500, step: 1, default: 4, help: '度效应聚类簇数' }],
  gnn_template: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 2, max: 500, step: 1, default: 4, help: '目标社区数' },
    { key: 'hidden_dim', label: 'Hidden Dim', type: 'number', min: 8, max: 2048, step: 1, default: 64, help: '神经网络隐藏维度' },
    { key: 'num_layers', label: 'Num Layers', type: 'number', min: 1, max: 16, step: 1, default: 2, help: '图神经网络层数' },
    { key: 'dropout', label: 'Dropout x100', type: 'number', min: 0, max: 99, step: 1, default: 30, help: 'Dropout 百分比（30 表示 0.30）' },
    { key: 'lr_milli', label: 'LR x1e-3', type: 'number', min: 1, max: 1000, step: 1, default: 1, help: '学习率（1 表示 1e-3）' },
    { key: 'weight_decay_micro', label: 'Weight Decay x1e-6', type: 'number', min: 0, max: 100000, step: 1, default: 10, help: '权重衰减（10 表示 1e-5）' },
    { key: 'epochs', label: 'Epochs', type: 'number', min: 1, max: 20000, step: 1, default: 200, help: '训练轮次' },
    { key: 'use_gpu_flag', label: 'Use GPU (1/0)', type: 'number', min: 0, max: 1, step: 1, default: 1, help: '1=GPU，0=CPU' }
  ],
  ddgae: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 2, max: 500, step: 1, default: 7, help: '目标社区数（Cora=7, Citeseer=6）' },
    { key: 'hidden_size', label: 'Hidden Size', type: 'number', min: 8, max: 4096, step: 1, default: 256, help: 'GAT 隐藏层维度' },
    { key: 'embedding_size', label: 'Embedding Size', type: 'number', min: 2, max: 1024, step: 1, default: 16, help: '节点嵌入维度' },
    { key: 'max_epoch', label: 'Max Epoch', type: 'number', min: 1, max: 5000, step: 1, default: 200, help: '训练轮次' },
    { key: 'update_interval', label: 'Update Interval', type: 'number', min: 1, max: 200, step: 1, default: 1, help: '聚类中心更新间隔' },
    { key: 'alpha_x100', label: 'Alpha x100', type: 'number', min: 1, max: 200, step: 1, default: 20, help: 'LeakyReLU alpha（20 表示 0.20）' },
    { key: 'lambda1_x100', label: 'Lambda1 x100', type: 'number', min: 0, max: 10000, step: 1, default: 50, help: '重构损失权重（50 表示 0.50）' },
    { key: 'beta_x100', label: 'Beta x100', type: 'number', min: 0, max: 100000, step: 1, default: 1000, help: 'KL 损失权重（1000 表示 10.00）' },
    { key: 'lr_micro', label: 'LR x1e-6', type: 'number', min: 1, max: 1000000, step: 1, default: 1000, help: '学习率（1000 表示 1e-3）' },
    { key: 'weight_decay_micro', label: 'Weight Decay x1e-6', type: 'number', min: 0, max: 1000000, step: 1, default: 5000, help: '权重衰减（5000 表示 5e-3）' },
    { key: 'use_gpu_flag', label: 'Use GPU (1/0)', type: 'number', min: 0, max: 1, step: 1, default: 1, help: 'DDGAE 默认 1（CUDA）' }
  ],
  cdbne: [
    { key: 'num_clusters', label: 'Num Clusters', type: 'number', min: 2, max: 500, step: 1, default: 7, help: '目标社区数（默认：Cora=7, Citeseer=6）' },
    { key: 'middle_size', label: 'Middle Size', type: 'number', min: 8, max: 4096, step: 1, default: 256, help: '中间隐藏层维度（默认 256）' },
    { key: 'representation_size', label: 'Representation Size', type: 'number', min: 2, max: 1024, step: 1, default: 16, help: '表示层维度（默认 16）' },
    { key: 'max_epoch', label: 'Max Epoch', type: 'number', min: 1, max: 5000, step: 1, default: 100, help: '训练轮次（默认 100）' },
    { key: 'update_interval', label: 'Update Interval', type: 'number', min: 1, max: 200, step: 1, default: 1, help: '评估间隔（默认 1）' },
    { key: 'alpha_x100', label: 'Alpha x100', type: 'number', min: 1, max: 200, step: 1, default: 20, help: 'LeakyReLU alpha（20 表示 0.20）' },
    { key: 'lr_micro', label: 'LR x1e-6', type: 'number', min: 1, max: 1000000, step: 1, default: 100, help: '学习率（默认：Cora=100, Citeseer=5000）' },
    { key: 'weight_decay_micro', label: 'Weight Decay x1e-6', type: 'number', min: 0, max: 1000000, step: 1, default: 5000, help: '权重衰减（5000 表示 5e-3）' },
    { key: 'use_gpu_flag', label: 'Use GPU (1/0)', type: 'number', min: 0, max: 1, step: 1, default: 1, help: '1=GPU，0=CPU' }
  ]
}

// Frontend capability fallback map to guarantee quick-filter effect.
const methodCapabilityMap = {
  deepwalk: { attributed: true, unattributed: true },
  node2vec: { attributed: true, unattributed: true },
  kmeans: { attributed: true, unattributed: true },
  nmf: { attributed: true, unattributed: true },
  pca: { attributed: true, unattributed: true },
  dnr: { attributed: true, unattributed: true },
  dsacd: { attributed: true, unattributed: true },
  mdnp: { attributed: true, unattributed: true },
  sc: { attributed: true, unattributed: true },
  le: { attributed: true, unattributed: true },
  louvain: { attributed: false, unattributed: true },
  lpa: { attributed: false, unattributed: true },
  fn: { attributed: false, unattributed: true },
  cnm: { attributed: false, unattributed: true },
  fua: { attributed: false, unattributed: true },
  kl: { attributed: false, unattributed: true },
  gn: { attributed: false, unattributed: true },
  infomap: { attributed: false, unattributed: true },
  edmot: { attributed: false, unattributed: true },
  cdme: { attributed: false, unattributed: true },
  ddgae: { attributed: true, unattributed: false },
  cdbne: { attributed: true, unattributed: false }
}

const selectedMethod = computed(() => methods.value.find((item) => item.key === form.method_key))
const selectedDataset = computed(() => datasets.value.find((item) => item.key === form.dataset_key))
const filteredMethods = computed(() => {
  if (methodFilter.value === 'attributed') {
    return methods.value.filter((m) => methodSupports(m, 'attributed'))
  }
  if (methodFilter.value === 'unattributed') {
    return methods.value.filter((m) => methodSupports(m, 'unattributed'))
  }
  return methods.value
})

const filteredDatasets = computed(() => {
  if (datasetFilter.value === 'attributed') return datasets.value.filter((d) => d.has_features)
  if (datasetFilter.value === 'unattributed') return datasets.value.filter((d) => !d.has_features)
  return datasets.value
})

const currentMethodFields = computed(() => methodParamSchema[form.method_key] || [])

const paramErrors = computed(() => {
  const errors = {}
  for (const field of currentMethodFields.value) {
    const raw = methodParams[field.key]
    if (field.type === 'number') {
      if (raw === '' || raw === null || raw === undefined || Number.isNaN(Number(raw))) {
        errors[field.key] = `${field.label} 必须是数字`
        continue
      }
      const value = Number(raw)
      if (!Number.isInteger(value)) {
        errors[field.key] = `${field.label} 必须是整数`
        continue
      }
      if (field.min !== undefined && value < field.min) {
        errors[field.key] = `${field.label} 不能小于 ${field.min}`
        continue
      }
      if (field.max !== undefined && value > field.max) {
        errors[field.key] = `${field.label} 不能大于 ${field.max}`
      }

      if (field.key === 'dropout' && (value < 0 || value > 99)) {
        errors[field.key] = 'Dropout x100 需在 0-99 之间'
      }
    }
  }
  return errors
})

const hasParamErrors = computed(() => Object.keys(paramErrors.value).length > 0)
const paramErrorMessage = computed(() => (hasParamErrors.value ? '请先修正 Method Parameters 中的错误' : ''))

const submitDisabled = computed(
  () => !token.value || loading.value || !!loadError.value || !form.method_key || !form.dataset_key || !form.metric_keys.length || hasParamErrors.value
)

const messageClass = computed(() => (msg.value.startsWith('提交成功') ? 'ok' : 'msg'))

function methodLevelText(method) {
  const levelMap = { approximate: '近似实现', 'standard-lite': '标准实现（轻量）', standard: '标准实现' }
  return levelMap[method.implementation_level] || method.implementation_level || '近似实现'
}

function methodCompatText(method) {
  const supportsAttr = method.supports_attributed !== false
  const supportsUnattr = method.supports_unattributed !== false
  if (supportsAttr && supportsUnattr) return '支持有属性/无属性网络'
  if (supportsAttr) return '仅支持有属性网络'
  if (supportsUnattr) return '仅支持无属性网络'
  return '兼容性未声明'
}

function methodSupports(method, kind) {
  const fallback = methodCapabilityMap[method.key]
  if (kind === 'attributed') {
    if (fallback) return fallback.attributed
    return method.supports_attributed !== false
  }
  if (kind === 'unattributed') {
    if (fallback) return fallback.unattributed
    return method.supports_unattributed !== false
  }
  return true
}

function datasetTag(dataset) {
  const tags = []
  tags.push(dataset.has_features ? '有属性' : '无属性')
  const n = dataset.node_count ?? '-'
  const m = dataset.edge_count ?? '-'
  const c = dataset.community_count ?? '-'
  tags.push(`节点 ${n}`)
  tags.push(`边 ${m}`)
  tags.push(`社区 ${c}`)
  return tags.join(' | ')
}

function resetMethodParams(methodKey) {
  const fields = methodParamSchema[methodKey] || []
  for (const key of Object.keys(methodParams)) delete methodParams[key]
  for (const field of fields) methodParams[field.key] = field.default

  if (methodKey === 'ddgae') {
    applyDdgaeDatasetDefaults()
    return
  }
  if (methodKey === 'cdbne') {
    applyCdbneDatasetDefaults()
    return
  }

  const c = selectedDataset.value?.community_count
  if (typeof c === 'number' && Number.isInteger(c) && c > 0 && Object.hasOwn(methodParams, 'num_clusters')) {
    methodParams.num_clusters = c
  }
}

function resetCurrentMethodDefaults() {
  if (!form.method_key) return
  resetMethodParams(form.method_key)
}

function applyDdgaeDatasetDefaults() {
  if (!Object.hasOwn(methodParams, 'num_clusters')) return
  const datasetKey = String(form.dataset_key || '').toLowerCase()
  if (datasetKey === 'cora') {
    methodParams.num_clusters = 7
    methodParams.lr_micro = 500 // 5e-4
    methodParams.lambda1_x100 = 50 // 0.5
    methodParams.beta_x100 = 1000 // 10
    return
  }
  if (datasetKey === 'citeseer') {
    methodParams.num_clusters = 6
    methodParams.lr_micro = 10000 // 1e-2
    methodParams.lambda1_x100 = 100 // 1.0
    methodParams.beta_x100 = 100 // 1.0
  }
}

function applyCdbneDatasetDefaults() {
  if (!Object.hasOwn(methodParams, 'num_clusters')) return
  const datasetKey = String(form.dataset_key || '').toLowerCase()
  if (datasetKey === 'cora') {
    methodParams.num_clusters = 7
    methodParams.lr_micro = 100 // 1e-4
    return
  }
  if (datasetKey === 'citeseer') {
    methodParams.num_clusters = 6
    methodParams.lr_micro = 5000 // 5e-3
  }
}

function readRunFormCache() {
  try {
    const raw = localStorage.getItem(RUN_FORM_CACHE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function saveRunFormCache() {
  const cache = {
    method_key: form.method_key,
    dataset_key: form.dataset_key,
    metric_keys: [...form.metric_keys],
    seed: form.seed,
    method_filter: methodFilter.value,
    dataset_filter: datasetFilter.value,
    run_mode: runMode.value,
    advanced_params_text: advancedParamsText.value,
    remote: { ...remote },
    method_params: { ...methodParams }
  }
  localStorage.setItem(RUN_FORM_CACHE_KEY, JSON.stringify(cache))
}

watch(
  [
    () => form.method_key,
    () => form.dataset_key,
    () => JSON.stringify(form.metric_keys),
    () => form.seed,
    () => methodFilter.value,
    () => datasetFilter.value,
    () => runMode.value,
    () => advancedParamsText.value,
    () => JSON.stringify(remote),
    () => JSON.stringify(methodParams)
  ],
  () => {
    if (loading.value) return
    saveRunFormCache()
  }
)

watch(filteredDatasets, (items) => {
  if (!items.length) {
    form.dataset_key = ''
    return
  }
  if (!items.some((item) => item.key === form.dataset_key)) {
    form.dataset_key = items[0].key
  }
})

watch(filteredMethods, (items) => {
  if (!items.length) {
    form.method_key = ''
    return
  }
  if (!items.some((item) => item.key === form.method_key)) {
    form.method_key = items[0].key
  }
})

watch(
  () => form.method_key,
  (methodKey) => {
    if (!methodKey) return
    resetMethodParams(methodKey)
  }
)

watch(
  () => form.dataset_key,
  () => {
    if (form.method_key === 'ddgae') {
      applyDdgaeDatasetDefaults()
      return
    }
    if (form.method_key === 'cdbne') {
      applyCdbneDatasetDefaults()
      return
    }
    const c = selectedDataset.value?.community_count
    if (typeof c === 'number' && Number.isInteger(c) && c > 0 && Object.hasOwn(methodParams, 'num_clusters')) {
      methodParams.num_clusters = c
    }
  }
)

onMounted(async () => {
  try {
    methods.value = await api.getMethods()
    datasets.value = await api.getDatasets()
    metrics.value = await api.getMetrics()

    methods.value.sort((a, b) => a.name.localeCompare(b.name))
    const cached = readRunFormCache()

    if (cached) {
      methodFilter.value = ['all', 'attributed', 'unattributed'].includes(cached.method_filter)
        ? cached.method_filter
        : 'all'
      datasetFilter.value = ['all', 'attributed', 'unattributed'].includes(cached.dataset_filter)
        ? cached.dataset_filter
        : 'all'
      runMode.value = ['local', 'remote'].includes(cached.run_mode) ? cached.run_mode : 'local'
      advancedParamsText.value = typeof cached.advanced_params_text === 'string' ? cached.advanced_params_text : '{}'
      form.seed = Number.isInteger(Number(cached.seed)) ? Number(cached.seed) : 42

      if (cached.remote && typeof cached.remote === 'object') {
        remote.ip = cached.remote.ip || ''
        remote.port = Number(cached.remote.port) || 22
        remote.username = cached.remote.username || ''
        remote.key_file = cached.remote.key_file || ''
      }

      if (methods.value.some((item) => item.key === cached.method_key)) {
        form.method_key = cached.method_key
      } else if (methods.value.length) {
        form.method_key = methods.value[0].key
      }

      if (datasets.value.some((item) => item.key === cached.dataset_key)) {
        form.dataset_key = cached.dataset_key
      } else if (datasets.value.length) {
        form.dataset_key = datasets.value[0].key
      }

      const validMetricKeys = new Set(metrics.value.map((item) => item.key))
      const cachedMetrics = Array.isArray(cached.metric_keys)
        ? cached.metric_keys.filter((key) => validMetricKeys.has(key))
        : []
      form.metric_keys = cachedMetrics.length
        ? cachedMetrics
        : metrics.value.slice(0, 2).map((item) => item.key)

      const cachedParams = cached.method_params && typeof cached.method_params === 'object' ? cached.method_params : {}
      resetMethodParams(form.method_key)
      for (const field of currentMethodFields.value) {
        if (Object.hasOwn(cachedParams, field.key)) {
          methodParams[field.key] = cachedParams[field.key]
        }
      }
    } else {
      if (methods.value.length) form.method_key = methods.value[0].key
      if (datasets.value.length) form.dataset_key = datasets.value[0].key
      form.metric_keys = metrics.value.slice(0, 2).map((item) => item.key)
    }
  } catch (err) {
    loadError.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
})

function normalizeMethodParams() {
  const out = { ...methodParams }
  if (form.method_key === 'gnn_template') {
    out.dropout = Number(methodParams.dropout || 0) / 100
    out.lr = Number(methodParams.lr_milli || 1) * 1e-3
    out.weight_decay = Number(methodParams.weight_decay_micro || 0) * 1e-6
    out.use_gpu = Number(methodParams.use_gpu_flag || 0) === 1
    delete out.lr_milli
    delete out.weight_decay_micro
    delete out.use_gpu_flag
  }
  if (form.method_key === 'ddgae') {
    out.alpha = Number(methodParams.alpha_x100 || 20) / 100
    out.lambda1 = Number(methodParams.lambda1_x100 || 50) / 100
    out.beta = Number(methodParams.beta_x100 || 1000) / 100
    out.lr = Number(methodParams.lr_micro || 1000) * 1e-6
    out.weight_decay = Number(methodParams.weight_decay_micro || 5000) * 1e-6
    out.use_gpu = Number(methodParams.use_gpu_flag || 0) === 1
    delete out.alpha_x100
    delete out.lambda1_x100
    delete out.beta_x100
    delete out.lr_micro
    delete out.weight_decay_micro
    delete out.use_gpu_flag
  }
  if (form.method_key === 'cdbne') {
    out.alpha = Number(methodParams.alpha_x100 || 20) / 100
    out.lr = Number(methodParams.lr_micro || 100) * 1e-6
    out.weight_decay = Number(methodParams.weight_decay_micro || 5000) * 1e-6
    out.use_gpu = Number(methodParams.use_gpu_flag || 0) === 1
    delete out.alpha_x100
    delete out.lr_micro
    delete out.weight_decay_micro
    delete out.use_gpu_flag
  }
  return out
}

async function submitRun() {
  token.value = getToken()
  if (!token.value) {
    msg.value = '请先登录后再提交运行任务'
    return
  }

  if (hasParamErrors.value) {
    msg.value = 'Method 参数校验失败，请修正后再提交'
    return
  }

  let advancedParams = {}
  try {
    advancedParams = JSON.parse(advancedParamsText.value || '{}')
  } catch {
    msg.value = 'Advanced Params 不是合法 JSON'
    return
  }

  const payload = {
    method_key: form.method_key,
    dataset_key: form.dataset_key,
    metric_keys: form.metric_keys,
    seed: form.seed,
    params: {
      ...normalizeMethodParams(),
      ...advancedParams,
      run_mode: runMode.value,
      remote: runMode.value === 'remote' ? { ...remote } : null
    }
  }

  try {
    const result = await api.createRun(payload)
    pushRunId(result.run_id, Date.now())
    msg.value = `提交成功: ${result.run_id}`
    router.push(`/result/${result.run_id}`)
  } catch (err) {
    msg.value = err.message || '提交失败'
  }
}
</script>
