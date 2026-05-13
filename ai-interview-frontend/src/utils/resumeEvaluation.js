export const RESUME_EVALUATION_VERSION = 'resume_evaluation_v1'

function objectOf(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function arrayOf(value) {
  return Array.isArray(value) ? value : []
}

export function normalizeResumeEvaluation(payload = {}) {
  const root = objectOf(payload)
  const metrics = objectOf(root.matching_metrics)
  const snapshot = objectOf(root.resume_evaluation_snapshot || metrics.resume_evaluation_snapshot)
  const scores = objectOf(snapshot.scores)
  const keywordCoverage = objectOf(scores.keyword_coverage || metrics.keyword_coverage || root.keyword_coverage)
  const keywordEvidence = objectOf(snapshot.keyword_evidence)
  const abilityProfile = objectOf(
    snapshot.ability_profile
    || root.ability_gap_profile
    || metrics.ability_gap_profile
  )
  const learningPlan = objectOf(
    snapshot.learning_plan
    || root.learning_plan
    || metrics.learning_plan
  )
  const learningPrioritySummary = arrayOf(
    snapshot.learning_priority_summary
    || root.learning_priority_summary
    || metrics.learning_priority_summary
  )

  return {
    version: snapshot.version || RESUME_EVALUATION_VERSION,
    snapshot,
    matchingMetrics: {
      ...metrics,
      final_score: scores.final_score ?? metrics.final_score ?? root.final_score,
      keyword_coverage: keywordCoverage,
      semantic_score: scores.semantic_score ?? metrics.semantic_score ?? root.semantic_score,
      tfidf_semantic_score: scores.tfidf_semantic_score ?? metrics.tfidf_semantic_score,
      rule_score: scores.rule_score ?? metrics.rule_score ?? root.rule_score,
      ability_gap_profile: abilityProfile,
      learning_plan: learningPlan,
      learning_priority_summary: learningPrioritySummary
    },
    scores,
    keywordCoverage,
    keywordEvidence: {
      matched: arrayOf(keywordEvidence.matched || keywordCoverage.matched),
      missing: arrayOf(keywordEvidence.missing || keywordCoverage.missing || metrics.missing_keywords || root.missing_keywords),
      direct_matches: arrayOf(keywordEvidence.direct_matches || keywordCoverage.direct_matches || metrics.direct_matches),
      related_matches: arrayOf(keywordEvidence.related_matches || keywordCoverage.related_matches || metrics.related_matches),
      verification_needed: arrayOf(keywordEvidence.verification_needed || keywordCoverage.verification_needed || metrics.verification_needed),
      evidence_statuses: arrayOf(keywordEvidence.evidence_statuses || keywordCoverage.evidence_statuses || metrics.evidence_statuses)
    },
    abilityProfile,
    abilityItems: abilityItemsFromProfile(abilityProfile),
    learningPlan,
    learningPlanTasks: arrayOf(learningPlan.tasks),
    learningPrioritySummary,
    targetPosition: snapshot.target_position || root.target_position || metrics.target_position || learningPlan.target_position || ''
  }
}

export function abilityItemsFromProfile(profile = {}) {
  const payload = objectOf(profile)
  const topGaps = arrayOf(payload.top_gaps)
  const items = topGaps.length ? topGaps : arrayOf(payload.items)
  return items
}

export function shouldInterviewVerifyAbility(item = {}) {
  const status = item.evidence_status || 'needs_verification'
  return ['claimed_only', 'indirect', 'missing', 'needs_verification'].includes(status)
}
