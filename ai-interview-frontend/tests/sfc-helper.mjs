import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileScript, parse } from '@vue/compiler-sfc'
import * as Vue from 'vue'
import * as aiOptions from '../src/utils/aiRuntimeOptions.js'

export async function loadSfc(file, imports = {}, inlineTemplate = false) {
  const source = await readFile(new URL(file, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const code = compileScript(descriptor, { id: 'regression', inlineTemplate }).content
  const context = vm.createContext({ console, setTimeout })
  const component = new vm.SourceTextModule(code, { context })
  await component.link(specifier => {
    const exports = imports[specifier] ?? (specifier === 'vue' ? Vue
      : specifier === '../utils/aiRuntimeOptions' ? aiOptions
        : specifier.endsWith('.vue') ? { default: {} } : null)
    if (!exports) throw new Error(`Unmocked dependency: ${specifier}`)
    return new vm.SyntheticModule(Object.keys(exports), function () {
      for (const [key, value] of Object.entries(exports)) this.setExport(key, value)
    }, { context })
  })
  await component.evaluate()
  return component.namespace.default
}

export const vueWithoutMount = { ...Vue, onMounted() {} }
export const authImport = { useAuthStore: () => ({ setUserInfo() {}, setAuth() {} }) }
