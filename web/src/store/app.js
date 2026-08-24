import { defineStore } from 'pinia'
import { api } from '../api/client'

let initPromise = null
let loadEpoch = 0

function parseStoredMessage(content) {
  try {
    const j = JSON.parse(content)
    if (j.kind === 'loading' || j.kind === 'error') return { role: 'assistant', ...j }
    if (j.clarification) return { role: 'assistant', kind: 'clarification', clarification: j.clarification }
    if (j.mode === 'chat') return { role: 'assistant', kind: 'chat', final: j }
    if (j.mode === 'research') return { role: 'assistant', kind: 'research', final: j, chainId: j.chain_id }
    return { role: 'assistant', kind: 'error', error: '未知消息' }
  } catch {
    return { role: 'assistant', kind: 'chat', final: { answer: content } }
  }
}

export const useAppStore = defineStore('app', {
  state: () => ({
    ready: false,
    projects: [],
    projectId: null,
    project: null,
    sessions: [],
    sessionId: null,
    messages: [],
    sessionRuns: [],
  }),
  actions: {
    async init() {
      if (this.ready) return
      if (initPromise) return initPromise
      initPromise = (async () => {
        try {
          const d = await api.listProjects()
          this.projects = d.projects
          if (!this.projects.length) {
            await api.createProject({ merchant_id: 'm_001', name: '新项目' })
            this.projects = (await api.listProjects()).projects
          }
          await this.selectProject(this.projects[0].project_id)
          this.ready = true
        } finally {
          initPromise = null
        }
      })()
      return initPromise
    },

    async selectProject(pid) {
      const epoch = ++loadEpoch
      this.projectId = pid
      this.sessionId = null
      this.messages = []
      const [project, sessionsResult] = await Promise.all([
        api.getProject(pid),
        api.listSessions(pid),
      ])
      if (epoch !== loadEpoch || this.projectId !== pid) return
      this.project = project
      this.sessions = sessionsResult.sessions
      if (this.sessions.length) {
        await this.selectSession(this.sessions[0].session_id)
      } else {
        await this.newSession()
      }
    },

    async selectSession(sid) {
      const epoch = ++loadEpoch
      const projectId = this.projectId
      this.sessionId = sid
      this.messages = []
      this.sessionRuns = []
      const [messagesResult, runsResult] = await Promise.all([
        api.listMessages(sid),
        api.listSessionRuns(sid),
      ])
      if (epoch !== loadEpoch || this.projectId !== projectId || this.sessionId !== sid) return
      this.messages = messagesResult.messages.map((m) =>
        m.role === 'user' ? { role: 'user', content: m.content } : parseStoredMessage(m.content),
      )
      this.sessionRuns = runsResult.runs
    },

    async newSession() {
      if (!this.projectId) return
      await api.createSession({ project_id: this.projectId })
      await this.refreshSessions()
      await this.selectSession(this.sessions[0].session_id)
    },

    async newProject() {
      const p = await api.createProject({ merchant_id: 'm_001', name: `新项目 ${this.projects.length + 1}` })
      this.projects = (await api.listProjects()).projects
      await this.selectProject(p.project_id)
    },

    async refreshSessions() {
      if (this.projectId) this.sessions = (await api.listSessions(this.projectId)).sessions
    },

    // 新会话首条消息后自动命名（还是默认名时）
    async suggestSessionName(text) {
      if (!this.sessionId) return
      const s = this.sessions.find((x) => x.session_id === this.sessionId)
      if (s && s.name === '新会话') {
        await api.renameSession(this.sessionId, text.slice(0, 20))
        await this.refreshSessions()
      }
    },

    async renameProjectAction(pid, name) {
      await api.renameProject(pid, name)
      this.projects = (await api.listProjects()).projects
      if (pid === this.projectId) this.project = await api.getProject(pid)
    },

    async deleteProjectAction(pid) {
      await api.deleteProject(pid)
      this.projects = (await api.listProjects()).projects
      if (pid === this.projectId) {
        if (this.projects.length) await this.selectProject(this.projects[0].project_id)
        else {
          this.projectId = null
          this.project = null
          this.sessions = []
          this.sessionId = null
          this.messages = []
        }
      }
    },

    async renameSessionAction(sid, name) {
      await api.renameSession(sid, name)
      await this.refreshSessions()
    },

    async deleteSessionAction(sid) {
      await api.deleteSession(sid)
      await this.refreshSessions()
      if (sid === this.sessionId) {
        if (this.sessions.length) await this.selectSession(this.sessions[0].session_id)
        else {
          this.sessionId = null
          this.messages = []
        }
      }
    },
  },
})
