<script setup>
import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// one id per page load — groups every question asked in this visit into one Langfuse
// session, matching the backend's memory-recall behavior across follow-up questions
const sessionId = crypto.randomUUID()

const question = ref('')
const loading = ref(false)
const steps = ref([])
const answer = ref('')
const sqlResult = ref('')
const codeResult = ref('')
const error = ref('')

const NODE_META = {
  supervisor: { kind: 'supervisor', label: 'Supervisor' },
  generate: { kind: 'generate', label: 'Generate' },
  critic: { kind: 'critic', label: 'Critic' },
}

function describe(step) {
  if (step.startsWith('supervisor->')) {
    const target = step.slice('supervisor->'.length)
    return { kind: 'supervisor', label: 'Supervisor', detail: `routes to ${target}` }
  }
  if (step.startsWith('critic')) {
    const ok = step.includes('(ok)')
    const reason = step.match(/critic\((.*)\)/)?.[1] ?? ''
    return { kind: ok ? 'critic-ok' : 'critic-revise', label: 'Critic', detail: ok ? 'approved' : reason }
  }
  if (step === 'generate') {
    return { kind: 'generate', label: 'Generate', detail: 'synthesizing answer from evidence' }
  }
  const name = step.split('(')[0]
  return { kind: 'agent', label: name, detail: 'agent executed' }
}

async function ask() {
  if (!question.value.trim() || loading.value) return

  loading.value = true
  steps.value = []
  answer.value = ''
  sqlResult.value = ''
  codeResult.value = ''
  error.value = ''

  try {
    const res = await fetch(`${API_BASE}/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question.value, session_id: sessionId }),
    })
    if (!res.ok || !res.body) throw new Error(`Server returned ${res.status}`)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const events = buffer.split('\n\n')
      buffer = events.pop() // keep the last (possibly incomplete) chunk for next read

      for (const evt of events) {
        if (evt.startsWith('event: done')) continue
        const dataLine = evt.split('\n').find((l) => l.startsWith('data: '))
        if (!dataLine) continue
        const payload = JSON.parse(dataLine.slice('data: '.length))
        if (payload.steps) steps.value = payload.steps
        if (payload.answer) answer.value = payload.answer
        if (payload.sql_result) sqlResult.value = payload.sql_result
        if (payload.code_result) codeResult.value = payload.code_result
      }
    }
  } catch (e) {
    error.value = `Couldn't reach the backend: ${e.message}`
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <header class="header">
      <h1>Multi-Agent AI Analyst</h1>
      <p class="sub">A supervisor routes each question to a retriever, web search, SQL, or code agent — a critic verifies the answer before it's returned.</p>
    </header>

    <form class="ask-form" @submit.prevent="ask">
      <input
        v-model="question"
        type="text"
        placeholder="Ask about the seeded company data, general knowledge, or a calculation…"
        :disabled="loading"
      />
      <button type="submit" :disabled="loading">
        <span v-if="loading" class="spinner" aria-hidden="true"></span>
        {{ loading ? 'Thinking' : 'Ask' }}
      </button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>

    <section v-if="steps.length" class="trace-panel">
      <div class="trace-header">
        <span class="trace-title">Execution trace</span>
        <span class="trace-count">{{ steps.length }} step{{ steps.length === 1 ? '' : 's' }}</span>
      </div>
      <ol class="timeline">
        <li
          v-for="(step, i) in steps"
          :key="i"
          class="timeline-item"
          :class="describe(step).kind"
          :style="{ animationDelay: `${i * 40}ms` }"
        >
          <span class="node-dot"></span>
          <span class="node-body">
            <span class="node-label">{{ describe(step).label }}</span>
            <span class="node-detail">{{ describe(step).detail }}</span>
          </span>
        </li>
      </ol>
    </section>

    <section v-if="answer" class="answer-card">
      <h2>Answer</h2>
      <p class="answer-text">{{ answer }}</p>

      <div v-if="sqlResult" class="evidence">
        <h3>SQL evidence</h3>
        <pre>{{ sqlResult }}</pre>
      </div>
      <div v-if="codeResult" class="evidence">
        <h3>Code evidence</h3>
        <pre>{{ codeResult }}</pre>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* theme tokens (--bg, --ink, --primary, etc.) live in src/style.css — :root can't be
   scoped by a component's <style scoped> block (the scoping attribute never reaches
   <html>), so they have to be global */

.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 2.5rem 1.25rem 4rem;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--ink);
  background: var(--bg);
}

.header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  margin-bottom: 0.35rem;
  letter-spacing: -0.01em;
}

.sub {
  color: var(--ink-soft);
  margin-top: 0;
  line-height: 1.5;
}

.ask-form {
  display: flex;
  gap: 0.6rem;
  margin: 1.75rem 0;
}

.ask-form input {
  flex: 1;
  padding: 0.7rem 0.9rem;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 1rem;
  background: var(--surface);
  color: var(--ink);
  transition: border-color 0.15s ease;
}

.ask-form input:focus {
  outline: none;
  border-color: var(--primary);
}

.ask-form input::placeholder {
  color: var(--ink-faint);
}

.ask-form button {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.4rem;
  border: none;
  border-radius: 10px;
  background: var(--primary);
  color: white;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.ask-form button:hover:not(:disabled) {
  opacity: 0.92;
}

.ask-form button:disabled {
  opacity: 0.65;
  cursor: default;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error {
  color: var(--danger);
  background: var(--danger-soft);
  padding: 0.6rem 0.9rem;
  border-radius: 8px;
  font-size: 0.9rem;
}

/* --- Trace timeline --- */

.trace-panel {
  margin-top: 1.75rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.1rem 1.25rem 1.25rem;
  box-shadow: var(--shadow);
}

.trace-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 0.85rem;
}

.trace-title {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-faint);
}

.trace-count {
  font-size: 0.78rem;
  color: var(--ink-faint);
  font-variant-numeric: tabular-nums;
}

.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  position: relative;
}

.timeline-item {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  padding: 0.4rem 0 0.4rem 0;
  opacity: 0;
  animation: fade-in 0.35s ease forwards;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* connecting line, drawn through the dot column */
.timeline-item:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 1.1rem;
  bottom: -0.4rem;
  width: 2px;
  background: var(--border);
}

.node-dot {
  flex-shrink: 0;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-top: 0.3rem;
  background: var(--ink-faint);
  box-shadow: 0 0 0 3px var(--bg);
  z-index: 1;
}

.node-body {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
  min-width: 0;
}

.node-label {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.86rem;
  font-weight: 600;
}

.node-detail {
  font-size: 0.82rem;
  color: var(--ink-soft);
  overflow-wrap: anywhere;
}

.timeline-item.supervisor .node-dot { background: var(--info); }
.timeline-item.supervisor .node-label { color: var(--info); }

.timeline-item.agent .node-dot { background: var(--primary); }
.timeline-item.agent .node-label { color: var(--primary); }

.timeline-item.generate .node-dot { background: var(--accent); }
.timeline-item.generate .node-label { color: var(--accent); }

.timeline-item.critic-ok .node-dot { background: var(--purple); }
.timeline-item.critic-ok .node-label { color: var(--purple); }

.timeline-item.critic-revise .node-dot { background: var(--danger); }
.timeline-item.critic-revise .node-label { color: var(--danger); }

/* --- Answer --- */

.answer-card {
  margin-top: 1.5rem;
  padding: 1.4rem 1.5rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  box-shadow: var(--shadow-md);
}

.answer-card h2 {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-faint);
  margin: 0 0 0.6rem;
}

.answer-text {
  font-size: 1.05rem;
  line-height: 1.6;
  margin: 0;
}

.evidence {
  margin-top: 1.1rem;
}

.evidence h3 {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-faint);
  margin: 0 0 0.4rem;
}

.evidence pre {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--ink);
  padding: 0.8rem 0.9rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.85rem;
  white-space: pre-wrap;
  margin: 0;
}
</style>
