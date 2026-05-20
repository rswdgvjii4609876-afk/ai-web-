export const aiProviderOptions = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai', label: 'ChatGPT / OpenAI' }
]

export const aiProviderLabels = {
  deepseek: 'DeepSeek',
  openai: 'ChatGPT / OpenAI'
}

export const aiProviderDefaults = {
  deepseek: {
    baseUrl: 'https://api.deepseek.com',
    model: 'deepseek-v4-pro'
  },
  openai: {
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-5.2-chat-latest'
  }
}

export const aiProviderModelOptions = {
  deepseek: [
    { value: 'deepseek-v4-pro', label: 'deepseek-v4-pro (recommended)' },
    { value: 'deepseek-v4-flash', label: 'deepseek-v4-flash (fast / low cost)' }
  ],
  openai: [
    { value: 'gpt-5.2-chat-latest', label: 'gpt-5.2-chat-latest' },
    { value: 'gpt-5.2', label: 'gpt-5.2' },
    { value: 'gpt-5-mini', label: 'gpt-5-mini' }
  ]
}
