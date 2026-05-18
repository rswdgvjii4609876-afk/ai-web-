const AI_CONFIG_PATTERNS = [
  /API\s*Key/i,
  /API\s*Token/i,
  /OpenAI\s*Key/i,
  /DeepSeek\s*Key/i,
  /ChatGPT\s*Key/i,
  /AI\s*API/i,
  /个人中心.*API/i,
  /个人设置.*API/i,
  /保存.*API/i,
  /AI\s*配置/i,
  /API\s*配置/i,
  /Base\s*URL/i,
  /模型名/,
  /模型配置/,
  /无法读取当前账号的\s*AI\s*配置/,
  /无效或已失效/,
  /额度不足/,
  /请求过于频繁/,
  /检查\s*API\s*配置/,
  /检查\s*API\s*Token/,
  /provider.*API/i
]

const NON_AI_CONFIG_PATTERNS = [
  /不是\s*API\s*Key\s*问题/i,
  /数据库/,
  /alembic/i,
  /UndefinedColumn/i,
  /文件大小/,
  /仅支持上传/,
  /隐私协议/,
  /登录状态/,
  /权限不足/
]

export function isAiConfigError(error) {
  const text = String(error?.message || error || '').trim()
  if (!text) return false
  if (NON_AI_CONFIG_PATTERNS.some(pattern => pattern.test(text))) return false
  return AI_CONFIG_PATTERNS.some(pattern => pattern.test(text))
}

export function getAiConfigErrorHint(error) {
  const diagnostic = String(error?.message || error || '').trim()
  const matched = isAiConfigError(diagnostic)
  return {
    isAiConfigError: matched,
    title: '需要先配置 AI API',
    message: '当前功能需要调用大模型。请点击右上角个人设置，进入“AI 调用设置”，保存 DeepSeek 或 ChatGPT / OpenAI API Key 后再重试。',
    steps: [
      '点击右上角“个人设置”。',
      '在“AI 调用设置”中选择 DeepSeek 或 ChatGPT / OpenAI。',
      '保存 API Key、Base URL 和模型名后，回到当前页面重试。'
    ],
    diagnostic
  }
}

export function buildAiConfigErrorTips(error) {
  const hint = getAiConfigErrorHint(error)
  return hint.isAiConfigError ? hint.steps : []
}
