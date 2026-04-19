import { createI18n } from 'vue-i18n'
import languages from '../../../locales/languages.json'

const localeFiles = import.meta.glob('../../../locales/!(languages).json', { eager: true })

const messages = {}
const availableLocales = []

for (const path in localeFiles) {
  const key = path.match(/\/([^/]+)\.json$/)[1]
  if (languages[key]) {
    messages[key] = localeFiles[path].default
    availableLocales.push({ key, label: languages[key].label })
  }
}

let savedLocale = localStorage.getItem('locale') || 'es'
// Migracion: usuarios con 'zh' guardado de antes deben pasar a 'es' (rebrand)
if (savedLocale === 'zh') {
  savedLocale = 'es'
  localStorage.setItem('locale', 'es')
}

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'es',
  messages
})

export { availableLocales }
export default i18n
