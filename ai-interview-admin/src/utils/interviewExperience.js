export const interviewAuditStatuses = ['可入库', '仅参考', '不采用', '待核验']
export const interviewDifficultyOptions = ['基础', '中等', '困难']

export function createEmptyInterviewExperience() {
  return {
    question: '',
    answer_points: '',
    reflection: '',
    company_context: '',
    ability: '',
    difficulty: '中等',
    source: '',
    audit_status: '待核验'
  }
}

function normalizeStatus(value) {
  return interviewAuditStatuses.includes(value) ? value : '待核验'
}

function normalizeDifficulty(value) {
  return interviewDifficultyOptions.includes(value) ? value : '中等'
}

function stripListMarker(line) {
  return String(line || '').replace(/^\s*[-*]\s*/, '').trim()
}

function readField(line) {
  const cleaned = stripListMarker(line)
  const match = cleaned.match(/^([^：:]{2,12})[：:]\s*(.*)$/)
  if (!match) return null
  return {
    key: match[1].trim(),
    value: match[2].trim()
  }
}

function applyField(item, key, value) {
  const aliases = {
    真实问题: 'question',
    问题: 'question',
    面试题: 'question',
    参考回答要点: 'answer_points',
    回答要点: 'answer_points',
    参考回答: 'answer_points',
    复盘反思: 'reflection',
    反思: 'reflection',
    公司: 'company_context',
    场景: 'company_context',
    '公司/场景': 'company_context',
    考察能力: 'ability',
    能力: 'ability',
    难度: 'difficulty',
    来源: 'source',
    来源说明: 'source',
    审核状态: 'audit_status'
  }
  const field = aliases[key]
  if (!field) return
  item[field] = value
}

function hasSubstantiveContent(item) {
  return [
    item.question,
    item.answer_points,
    item.reflection,
    item.company_context,
    item.ability,
    item.source
  ].some(value => String(value || '').trim())
}

export function parseInterviewExperienceMarkdown(text) {
  let content = String(text || '').trim()
  if (!content) return { items: [], legacy: '' }

  let trailingLegacy = ''
  const legacyMatch = content.match(/^#{3,5}\s*未结构化问答经验\s*$/m)
  if (legacyMatch?.index !== undefined) {
    trailingLegacy = content.slice(legacyMatch.index + legacyMatch[0].length).trim()
    content = content.slice(0, legacyMatch.index).trim()
  }

  const headingPattern = /^#{3,5}\s*(?:面经|问答|问题)\s*\d*[：:、.\-\s]*(.*)$/gm
  const matches = [...content.matchAll(headingPattern)]
  if (!matches.length) {
    return { items: [], legacy: [content, trailingLegacy].filter(Boolean).join('\n\n') }
  }

  const items = []
  const legacyParts = []
  const beforeFirst = content.slice(0, matches[0].index).trim()
  if (beforeFirst) legacyParts.push(beforeFirst)
  if (trailingLegacy) legacyParts.push(trailingLegacy)

  matches.forEach((match, index) => {
    const start = match.index + match[0].length
    const end = matches[index + 1]?.index ?? content.length
    const block = content.slice(start, end).trim()
    const item = createEmptyInterviewExperience()
    const headingQuestion = (match[1] || '').trim()
    if (headingQuestion) item.question = headingQuestion

    block.split(/\n+/).forEach(line => {
      const field = readField(line)
      if (field) applyField(item, field.key, field.value)
    })

    item.audit_status = normalizeStatus(item.audit_status)
    item.difficulty = normalizeDifficulty(item.difficulty)
    if (hasSubstantiveContent(item)) {
      items.push(item)
    }
  })

  return { items, legacy: legacyParts.join('\n\n') }
}

export function serializeInterviewExperiences(items, legacy = '') {
  const blocks = (items || [])
    .filter(item => hasSubstantiveContent(item || {}))
    .map((item, index) => {
      const question = String(item.question || '').trim() || '待补充真实问题'
      return [
        `### 面经 ${index + 1}：${question}`,
        `- 真实问题：${question}`,
        `- 参考回答要点：${String(item.answer_points || '').trim()}`,
        `- 复盘反思：${String(item.reflection || '').trim()}`,
        `- 公司/场景：${String(item.company_context || '').trim()}`,
        `- 考察能力：${String(item.ability || '').trim()}`,
        `- 难度：${normalizeDifficulty(item.difficulty)}`,
        `- 来源说明：${String(item.source || '').trim()}`,
        `- 审核状态：${normalizeStatus(item.audit_status)}`
      ].join('\n')
    })

  const legacyText = String(legacy || '').trim()
  if (legacyText) {
    blocks.push(`### 未结构化问答经验\n${legacyText}`)
  }
  return blocks.join('\n\n')
}

export function countInterviewExperiences(text) {
  const parsed = parseInterviewExperienceMarkdown(text)
  if (parsed.items.length) return parsed.items.length
  return parsed.legacy.trim() ? 1 : 0
}

export function collectInterviewAuditStatuses(text) {
  const parsed = parseInterviewExperienceMarkdown(text)
  const statuses = parsed.items.map(item => normalizeStatus(item.audit_status))
  if (parsed.legacy.trim()) statuses.push('待核验')
  return [...new Set(statuses)]
}
