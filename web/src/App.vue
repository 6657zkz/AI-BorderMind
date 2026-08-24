<script setup>
import { onMounted, ref } from 'vue'
import { useAppStore } from './store/app'

const store = useAppStore()
const editing = ref(null) // { type: 'project'|'session', id, value }
onMounted(() => store.init())

async function pickProject(p) {
  if (p.project_id !== store.projectId) await store.selectProject(p.project_id)
}
async function pickSession(s) {
  if (s.session_id !== store.sessionId) await store.selectSession(s.session_id)
}

function startEdit(type, id, value) {
  editing.value = { type, id, value }
}
async function saveEdit() {
  const e = editing.value
  if (!e) return
  const name = e.value.trim()
  if (name) {
    if (e.type === 'project') await store.renameProjectAction(e.id, name)
    else await store.renameSessionAction(e.id, name)
  }
  editing.value = null
}
async function confirmDelete(type, id, label) {
  if (!confirm(`确定删除${type === 'project' ? '项目' : '会话'}「${label}」？该操作不可恢复。`)) return
  if (type === 'project') await store.deleteProjectAction(id)
  else await store.deleteSessionAction(id)
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <router-link to="/" class="brand"><span class="brand-mark">A</span>AI-BorderMind</router-link>
      <nav>
        <router-link to="/">研判</router-link>
        <router-link to="/signals">监控信号</router-link>
        <router-link to="/evidence">证据回溯</router-link>
      </nav>
      <span class="project-tag">AI 市场洞察</span>
    </header>

    <div class="body">
      <aside class="sidebar">
        <div class="side-head">
          <span>项目 / 会话</span>
          <button class="mini" @click="store.newProject()">＋新项目</button>
        </div>
        <div class="side-scroll">
          <div
            v-for="p in store.projects"
            :key="p.project_id"
            class="project"
            :class="{ active: p.project_id === store.projectId }"
          >
            <div class="p-name" @click="pickProject(p)">
              <template v-if="editing && editing.type === 'project' && editing.id === p.project_id">
                <input v-model="editing.value" class="edit-input" @keyup.enter="saveEdit" @keyup.esc="editing = null" @blur="saveEdit" autofocus />
              </template>
              <template v-else>
                <span class="p-label">{{ p.name }}</span>
                <span class="tag" :class="{ on: p.scoped }">{{ p.scoped ? '已定范围' : '待定范围' }}</span>
                <span class="ops">
                  <button class="op" title="重命名" @click.stop="startEdit('project', p.project_id, p.name)">✎</button>
                  <button class="op del" title="删除" @click.stop="confirmDelete('project', p.project_id, p.name)">✕</button>
                </span>
              </template>
            </div>
            <div class="sessions" v-if="p.project_id === store.projectId">
              <div
                v-for="s in store.sessions"
                :key="s.session_id"
                class="session"
                :class="{ active: s.session_id === store.sessionId }"
                @click="pickSession(s)"
              >
                <template v-if="editing && editing.type === 'session' && editing.id === s.session_id">
                  <input v-model="editing.value" class="edit-input" @keyup.enter="saveEdit" @keyup.esc="editing = null" @blur="saveEdit" autofocus />
                </template>
                <template v-else>
                  <span class="s-label">{{ s.name }}</span>
                  <span class="s-count">{{ s.message_count }} 条</span>
                  <span class="ops">
                    <button class="op" title="重命名" @click.stop="startEdit('session', s.session_id, s.name)">✎</button>
                    <button class="op del" title="删除" @click.stop="confirmDelete('session', s.session_id, s.name)">✕</button>
                  </span>
                </template>
              </div>
              <button class="mini new-session" @click="store.newSession()">＋ 新会话</button>
            </div>
          </div>
        </div>
      </aside>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style>
:root {
  --bg: #0b101b;
  --panel: #111a2a;
  --border: #263650;
  --text: #edf3ff;
  --muted: #8090ad;
  --accent: #5a8dff;
  --ok: #22c55e;
  --warn: #f59e0b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.app-shell { display: flex; flex-direction: column; height: 100vh; }
.topbar {
  display: flex; align-items: center; gap: 24px;
  padding: 0 20px; height: 52px;
  background: radial-gradient(circle at 40% -30%, #1f396f 0, transparent 42%), var(--panel); border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.brand { display: flex; align-items: center; gap: 8px; font-weight: 750; letter-spacing: -.02em; font-size: 17px; color: var(--text); text-decoration: none; }
.brand-mark { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 8px; color: #fff; font-size: 13px; background: linear-gradient(145deg, #6e9cff, #6957ed); box-shadow: 0 5px 18px rgba(73, 117, 245, .3); }
.topbar nav { display: flex; gap: 4px; flex: 1; }
.topbar nav a {
  color: var(--muted); text-decoration: none; padding: 6px 14px; border-radius: 8px;
}
.topbar nav a.router-link-active { color: var(--text); background: #22304c; }
.project-tag { color: var(--muted); font-size: 13px; }
.body { display: flex; flex: 1; overflow: hidden; }
.sidebar {
  width: 280px; flex-shrink: 0; border-right: 1px solid var(--border);
  background: var(--panel); display: flex; flex-direction: column;
}
.side-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--muted);
}
.side-scroll { flex: 1; overflow-y: auto; padding: 10px; }
.project { margin-bottom: 8px; border-radius: 8px; }
.project.active { background: #1c2740; }
.p-name {
  display: flex; align-items: center; gap: 6px;
  padding: 9px 10px; cursor: pointer; font-size: 14px;
}
.p-name:hover { background: #22304c; border-radius: 8px; }
.p-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag { font-size: 11px; padding: 1px 8px; border-radius: 10px; color: var(--muted); background: #22304c; flex-shrink: 0; }
.tag.on { color: var(--ok); }
.ops { display: none; gap: 2px; flex-shrink: 0; }
.p-name:hover .ops, .session:hover .ops { display: flex; }
.op {
  border: none; background: transparent; color: var(--muted); cursor: pointer;
  padding: 0 3px; font-size: 13px;
}
.op:hover { color: var(--text); }
.op.del:hover { color: var(--warn); }
.sessions { padding: 0 6px 8px 12px; display: flex; flex-direction: column; gap: 4px; }
.session {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--muted); padding: 6px 8px; border-radius: 6px; cursor: pointer;
}
.session:hover { background: #22304c; }
.session.active { color: var(--text); background: #2a3a5c; }
.s-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.s-count { color: var(--muted); font-size: 11px; flex-shrink: 0; }
.edit-input {
  flex: 1; padding: 3px 6px; border: 1px solid var(--accent); border-radius: 4px;
  background: var(--bg); color: var(--text); outline: none; font-size: 13px;
}
.mini {
  border: 1px solid var(--border); background: transparent; color: var(--text);
  padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 12px;
}
.mini:hover { border-color: var(--accent); }
.new-session { align-self: flex-start; margin-top: 2px; }
.content { flex: 1; overflow: hidden; }
</style>
