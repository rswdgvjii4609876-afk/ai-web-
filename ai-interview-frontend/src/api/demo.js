import api from './request'

export function getCompetitionDemoAssets() {
  return api.get('/demo/competition')
}
