import api from './request'

export function getCompetitionCases() {
  return api.get('/competition/demo-cases')
}

export function getCompetitionAgentTrace(caseId) {
  return api.get(`/competition/agent-trace/${caseId}`)
}

export function getCompetitionEvalPreview(caseId) {
  return api.get(`/competition/eval-preview/${caseId}`)
}

export function getCompetitionSftPreview() {
  return api.get('/competition/sft-preview')
}
