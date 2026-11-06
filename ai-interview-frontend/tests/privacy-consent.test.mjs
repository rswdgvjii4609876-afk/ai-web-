import test from 'node:test'
import assert from 'node:assert/strict'
import * as Vue from 'vue'
import { loadSfc, vueWithoutMount, authImport } from './sfc-helper.mjs'

test('base consent and optional contribution are unchecked and emit independently', async () => {
  const component = await loadSfc('../src/components/PrivacyConsentNotice.vue', {
    vue: { ...Vue, resolveComponent: name => name }
  }, true)
  assert.equal(component.props.baseAgreed.default, false)
  assert.equal(component.props.dataContributionConsent.default, false)
  const events = []
  const render = component.setup({ baseAgreed: false, dataContributionConsent: false,
    showBaseConsent: true, showDataContribution: true, compact: false, title: 'Privacy' },
  { emit: (...args) => events.push(args), expose() {} })
  const inputs = []
  function visit(node) {
    if (!node || typeof node !== 'object') return
    if (node.type === 'input') inputs.push(node)
    if (Array.isArray(node.children)) node.children.forEach(visit)
  }
  visit(render({}, []))
  assert.equal(inputs.length, 2)
  inputs[0].props.onChange({ target: { checked: true } })
  assert.deepEqual(events, [['update:baseAgreed', true]])
  inputs[1].props.onChange({ target: { checked: true } })
  assert.deepEqual(events, [['update:baseAgreed', true], ['update:dataContributionConsent', true]])
})

test('registration can accept base privacy while declining contribution', async () => {
  const requests = []
  const component = await loadSfc('../src/views/Register.vue', {
    vue: vueWithoutMount,
    '../stores/auth': authImport,
    'vue-router': { useRouter: () => ({ push() {} }) },
    '../api/auth': {
      register: async body => { requests.push(body); return { verification_required: true, email: body.email } },
      sendVerificationCode() {}, verifyEmail() {}
    }
  })
  const state = component.setup({}, { expose() {} })
  assert.equal(state.privacyAgreed.value, false)
  assert.equal(state.dataContributionConsent.value, false)
  state.privacyAgreed.value = true
  await state.handleRegister()
  assert.equal(requests[0].privacy_agreed, true)
  assert.equal(requests[0].data_contribution_consent, false)
})

test('saving a model key preserves opt-out and explicit consent changes are sent', async () => {
  const requests = []
  let profile = { email: 'fixture@example.com', privacy_base_consent_valid: true,
    data_contribution_consent: false, data_contribution_consent_valid: false,
    ai_provider: 'deepseek', deepseek_model: 'deepseek-v4-pro' }
  const component = await loadSfc('../src/views/Profile.vue', {
    vue: vueWithoutMount,
    '../stores/auth': authImport,
    '../api/user': {
      getProfile: async () => profile,
      updateProfile: async body => { requests.push(body); return { message: 'saved' } },
      changePassword() {}, testAiConnection() {}, uploadAvatar() {}
    }
  })
  const state = component.setup({}, { expose() {} })
  state.applyProfile(profile)
  state.providerApiKeyInputs.value.deepseek = 'fixture-token-not-a-real-key'
  await state.handleSaveProfile()
  assert.equal(Object.hasOwn(requests[0], 'data_contribution_consent'), false)
  assert.equal(requests[0].deepseek_api_key, 'fixture-token-not-a-real-key')
  state.privacyForm.value.data_contribution_consent = true
  await state.handleSaveProfile()
  assert.equal(requests[1].data_contribution_consent, true)
  profile = { ...profile, data_contribution_consent: true, data_contribution_consent_valid: true }
  state.applyProfile(profile)
  state.privacyForm.value.data_contribution_consent = false
  await state.handleSaveProfile()
  assert.equal(requests[2].data_contribution_consent, false)
})
