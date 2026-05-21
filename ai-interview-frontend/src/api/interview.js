import api, { fetchWithAuthRetry } from './request'

const startInterviewTimeout = Number(import.meta.env.VITE_START_INTERVIEW_TIMEOUT || 180000)
const answerStreamTimeout = Number(import.meta.env.VITE_ANSWER_STREAM_TIMEOUT || 160000)

export function startInterview(data) {
  return api.post('/interviews/start', data, { timeout: startInterviewTimeout })
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

export function reevaluateAnswer(interviewId, questionIndex) {
  return api.post(`/interviews/${interviewId}/questions/${questionIndex}/reevaluate`)
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

export async function submitAnswerStream(interviewId, answer, questionIndex, onChunk, onDone, onStatus, options = {}) {
  const controller = options.controller || new AbortController()
  const timeoutMs = Number(options.timeout || answerStreamTimeout)
  const timeoutId = setTimeout(() => {
    controller.abort()
  }, timeoutMs)
  let reader = null
  let sawDone = false
  let streamVersionSeen = false

  try {
    const response = await fetchWithAuthRetry(`/interviews/${interviewId}/answer/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        answer,
        question_index: questionIndex
      }),
      signal: controller.signal
    })

    if (!response.ok) {
      throw new Error(await readResponseError(response))
    }
    if (!response.body) {
      throw new Error('流式答题连接不可用，请稍后重试')
    }

    reader = response.body.getReader()
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
      if (data.type === 'stream_version') {
        streamVersionSeen = true
      } else if (data.type === 'chunk') {
        onChunk(data.content)
      } else if (data.type === 'done') {
        sawDone = true
        onDone(data)
      } else if (data.type === 'status') {
        if (!streamVersionSeen) {
          onStatus?.({
            ...data,
            content: '当前服务可能仍是旧版流式接口；如果持续卡住，请部署最新后端并刷新页面。'
          })
          return
        }
        onStatus?.(data)
      } else if (data.type === 'heartbeat') {
        onStatus?.(data)
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

    if (!sawDone) {
      throw new Error(
        streamVersionSeen
          ? '本轮评估连接提前结束，请刷新查看记录或重试。'
          : '当前服务可能仍是旧版或流式响应被代理缓冲，请刷新页面；若仍卡住，请重新部署后端。'
      )
    }
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('本轮评估已停止等待。请刷新查看记录；如果回答未保存，可直接重试。')
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
    if (!sawDone && reader) {
      try {
        await reader.cancel()
      } catch {
        // Ignore cleanup errors.
      }
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
