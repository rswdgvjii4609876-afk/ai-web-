import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

async function apiHarness() {
  const calls = []
  const api = Object.fromEntries(['get', 'post', 'patch', 'delete'].map(method => [
    method, async (...args) => { calls.push({ method, args }); return { tasks: [] } }
  ]))
  const context = vm.createContext({})
  const code = await readFile(new URL('../src/api/learningTasks.js', import.meta.url), 'utf8')
  const module = new vm.SourceTextModule(code, { context })
  await module.link(() => new vm.SyntheticModule(['default'], function () {
    this.setExport('default', api)
  }, { context }))
  await module.evaluate()
  return { api: module.namespace, calls }
}

test('all learning-task save callers send null for empty optional integers', async () => {
  const { api, calls } = await apiHarness()
  const task = { title: 'fixture', resume_id: 1, interview_id: '', learning_plan_id: '',
    step_order: '', estimated_minutes: '', note: '' }
  await api.bulkUpsertLearningTasks([task], { replaceProgress: false })
  const payload = calls[0].args[1]
  for (const key of ['interview_id', 'learning_plan_id', 'step_order', 'estimated_minutes']) {
    assert.equal(payload.tasks[0][key], null, key)
  }
  assert.equal(payload.tasks[0].resume_id, 1)
  assert.equal(payload.tasks[0].note, '')
  assert.equal(payload.replace_progress, false)
  assert.equal(task.interview_id, '', 'submission must not mutate local task progress')
})

test('numeric edits preserve zero and do not add absent fields', async () => {
  const { api, calls } = await apiHarness()
  await api.patchLearningTask('task/one', { estimated_minutes: '', step_order: 0, note: 'kept' })
  const [path, payload] = calls[0].args
  assert.equal(path, '/learning-tasks/task%2Fone')
  assert.equal(payload.estimated_minutes, null)
  assert.equal(payload.step_order, 0)
  assert.equal(payload.note, 'kept')
  assert.equal(Object.hasOwn(payload, 'resume_id'), false)
})
