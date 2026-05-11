const STATUS_LABELS = {
  direct: '已具备证据',
  indirect: '有间接证据',
  claimed_only: '声明待验证',
  missing: '暂无证据',
  needs_verification: '待面试验证'
}

const STATUS_HINTS = {
  direct: '简历已有较直接证据，面试可继续深挖责任边界和结果。',
  indirect: '简历有相近经历或技术线索，需要通过面试确认能否迁移到目标岗位。',
  claimed_only: '简历写了相关能力，但缺少项目或职责证据，需要通过面试验证。',
  missing: '简历暂未提供足够证据，建议用基础理解题和场景题验证。',
  needs_verification: '该能力需要通过模拟面试继续验证掌握程度。'
}

export function evidenceStatusLabel(status) {
  return STATUS_LABELS[status] || STATUS_LABELS.needs_verification
}

export function evidenceStatusClass(status) {
  return `evidence-status-${status || 'needs_verification'}`
}

export function evidenceStatusHint(status) {
  return STATUS_HINTS[status] || STATUS_HINTS.needs_verification
}
