import api, { fetchWithAuthRetry } from './request'

export function startInterview(data) {
  return api.post('/interviews/start', data)
}

export function submitAnswer(interviewId, answer, questionIndex) {
  if (!Number.isInteger(questionIndex) || questionIndex < 0) {
    return Promise.reject(new Error('question_index is required'))
  }
  return api.post(`/interviews/${interviewId}/answer`, {
    answer,
    question_index: questionIndex
  })
}

async function readResponseError(response) {
  try {
    const payload = await response.clone().json()
    if (payload?.message) return payload.message
    if (payload?.detail) {
      if (Array.isArray(payload.detail)) {
        return payload.detail.map(item => item.msg || item.message || JSON.stringify(item)).join('; ')
      }
      return String(payload.detail)
    }
  } catch {
    // Ignore non-JSON errors and fall through to text.
  }
  try {
    const text = await response.text()
    if (text) return text.slice(0, 300)
  } catch {
    // Ignore body read errors.
  }
  return `请求失败（HTTP ${response.status}）`
}

export async function submitAnswerStream(interviewId, answer, questionIndex, onChunk, onDone) {
  const response = await fetchWithAuthRetry(`/interviews/${interviewId}/answer/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      answer,
      question_index: questionIndex
    })
  })

  if (!response.ok) {
    throw new Error(await readResponseError(response))
  }
  if (!response.body) {
    throw new Error('流式答题连接不可用，请稍后重试')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const handleLine = line => {
    if (!line.startsWith('data: ')) return
    let data
    try {
      data = JSON.parse(line.slice(6))
    } catch {
      throw new Error('流式响应格式异常，请稍后重试')
    }
    if (data.type === 'chunk') {
      onChunk(data.content)
    } else if (data.type === 'done') {
      onDone(data)
    } else if (data.type === 'error') {
      throw new Error(data.content)
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      buffer += decoder.decode()
      if (buffer.trim()) {
        for (const line of buffer.split('\n')) handleLine(line.trimEnd())
      }
      break
    }
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      handleLine(line.trimEnd())
    }
  }
}

export function getReport(interviewId) {
  return api.get(`/interviews/${interviewId}/report`)
}

export function updateCaseDataContributionConsent(interviewId, consent) {
  return api.put(`/interviews/${interviewId}/case-data-contribution-consent`, {
    data_contribution_consent: !!consent
  })
}

export function getMessages(interviewId) {
  return api.get(`/interviews/${interviewId}/messages`)
}

export function getInterviews() {
  return api.get('/interviews')
}

export function deleteInterview(interviewId) {
  return api.delete(`/interviews/${interviewId}`)
}
