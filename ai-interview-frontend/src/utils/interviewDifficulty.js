export const INTERVIEW_DIFFICULTY_PROFILES = {
  easy: {
    level: 'easy',
    public_label: '简单',
    company_archetype: '基础执行型面试',
    question_strategy_summary: '基础知识、常见框架使用、项目复述和日常问题处理。',
    rubric_summary: '能讲清基础概念、自己做过什么、常见错误如何处理，就能获得较好评价。',
    pressure: '低压力',
    short: '基础题和项目复述为主'
  },
  medium: {
    level: 'medium',
    public_label: '中等',
    company_archetype: '标准岗位能力面试',
    question_strategy_summary: '项目职责、技术取舍、证据验证、能力短板和复盘。',
    rubric_summary: '需要证明自己真实参与、能解释方案选择，并能说明不足与改进。',
    pressure: '中等压力',
    short: '岗位能力追问为主'
  },
  hard: {
    level: 'hard',
    public_label: '困难',
    company_archetype: '高强度综合面试',
    question_strategy_summary: '项目深挖、系统设计、高并发、稳定性、性能、成本和复杂工程取舍。',
    rubric_summary: '不仅要讲做了什么，还要讲边界、失败模式、扩展性、成本和可验证结果。',
    pressure: '高压力',
    short: '项目深挖与系统设计为主'
  }
}

export function normalizeInterviewDifficulty(value) {
  return Object.prototype.hasOwnProperty.call(INTERVIEW_DIFFICULTY_PROFILES, value) ? value : 'medium'
}

export function getInterviewDifficultyProfile(value, override = null) {
  const normalized = normalizeInterviewDifficulty(value)
  return {
    ...INTERVIEW_DIFFICULTY_PROFILES[normalized],
    ...(override && typeof override === 'object' ? override : {}),
    level: normalized
  }
}
