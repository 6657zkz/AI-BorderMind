import { defineStore } from 'pinia'
import { api } from '../api/client'

const TERMINAL_STATUSES = new Set(['succeeded', 'partial_succeeded', 'failed', 'timed_out', 'cancelled'])
const STREAMING_STATUSES = new Set(['planning', 'planned', 'running'])

export const useAnalysisRunStore = defineStore('analysisRun', {
  state: () => ({
    runId: null,
    snapshot: null,
    lastSeq: 0,
    connected: false,
    error: null,
    controller: null,
  }),

  getters: {
    isRunning: (state) => Boolean(state.snapshot && STREAMING_STATUSES.has(state.snapshot.status)),
    canCancel: (state) => Boolean(state.snapshot && !TERMINAL_STATUSES.has(state.snapshot.status)),
    planNodes: (state) => state.snapshot?.execution_plan?.nodes || [],
    nodeMap: (state) => Object.fromEntries((state.snapshot?.nodes || []).map((node) => [node.node_id, node])),
  },

  actions: {
    beginPending(query) {
      this.disconnect()
      this.runId = null
      this.lastSeq = 0
      this.error = null
      this.snapshot = {
        run_id: null,
        status: 'planning',
        query,
        final: {},
        nodes: [],
        execution_plan: { nodes: [] },
        clarifications: [],
      }
    },

    reset() {
      this.disconnect()
      this.runId = null
      this.lastSeq = 0
      this.error = null
      this.snapshot = null
    },

    updateNode(nodeId, role, patch) {
      if (!this.snapshot) return
      this.snapshot.nodes ||= []
      let node = nodeId && this.snapshot.nodes.find((item) => item.node_id === nodeId)
      if (!node && role) node = this.snapshot.nodes.find((item) => item.role === role)
      if (!node) {
        node = { node_id: nodeId || role, role: role || nodeId, status: 'queued' }
        this.snapshot.nodes.push(node)
      }
      Object.assign(node, patch)
    },

    async hydrate(runId) {
      this.runId = runId
      this.snapshot = await api.getAnalysisRun(runId)
      this.error = null
      return this.snapshot
    },

    async attach(runId) {
      this.disconnect()
      this.lastSeq = 0
      await this.hydrate(runId)
      if (this.isRunning) this.connect()
    },

    async connect() {
      if (!this.runId || this.controller) return
      const controller = new AbortController()
      this.controller = controller
      this.connected = true
      try {
        const response = await fetch(`/api/analysis-runs/${this.runId}/events?after=${this.lastSeq}`, {
          headers: { Accept: 'text/event-stream' },
          signal: controller.signal,
        })
        if (!response.ok || !response.body) throw new Error(`运行事件连接失败：${response.status}`)
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (!controller.signal.aborted) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          let separator
          while ((separator = buffer.search(/\r?\n\r?\n/)) >= 0) {
            const match = buffer.match(/\r?\n\r?\n/)
            const chunk = buffer.slice(0, separator)
            buffer = buffer.slice(separator + (match?.[0].length || 2))
            this.applyEvent(chunk)
          }
        }
      } catch (error) {
        if (!controller.signal.aborted) this.error = error.message
      } finally {
        if (this.controller === controller) {
          this.controller = null
          this.connected = false
        }
        if (this.runId && this.isRunning && !controller.signal.aborted) {
          window.setTimeout(() => this.connect(), 1200)
        }
      }
    },

    applyEvent(chunk) {
      const dataLine = chunk.split('\n').find((line) => line.startsWith('data:'))
      if (!dataLine) return
      let event
      try {
        event = JSON.parse(dataLine.slice(5).trim())
      } catch {
        return
      }
      this.lastSeq = Math.max(this.lastSeq, event.seq || 0)
      if (!this.snapshot) return
      const { type, node_id: nodeId, data } = event
      if (nodeId) {
        if (type === 'node_started') this.updateNode(nodeId, data.role, { status: 'running' })
        if (type === 'node_succeeded') this.updateNode(nodeId, data.role, { status: 'succeeded', elapsed_ms: data.elapsed_ms })
        if (type === 'node_failed') this.updateNode(nodeId, data.role, { status: 'failed', error: data.error, elapsed_ms: data.elapsed_ms })
        if (type === 'node_skipped') this.updateNode(nodeId, data.role, { status: 'skipped', skipped: data.skipped })
        if (type === 'node_stage') this.updateNode(nodeId, data.role, { stage: data.stage })
      }
      if (type === 'run_completed' || type === 'run_failed' || type === 'run_cancelled' || type === 'run_waiting_clarification') {
        this.hydrate(this.runId)
      }
    },

    async submitClarification(fieldId, value) {
      if (!this.runId) return
      this.error = null
      if (this.snapshot) this.snapshot.status = 'planning'
      try {
        const result = await api.submitClarification(this.runId, { field_id: fieldId, value })
        await this.hydrate(this.runId)
        if (result.status === 'resumed' && this.isRunning) this.connect()
        return result
      } catch (error) {
        await this.hydrate(this.runId)
        this.error = error.message
        throw error
      }
    },

    async cancel() {
      if (!this.runId) return
      await api.cancelAnalysisRun(this.runId)
      await this.hydrate(this.runId)
      this.disconnect()
    },

    disconnect() {
      this.controller?.abort()
      this.controller = null
      this.connected = false
    },
  },
})
