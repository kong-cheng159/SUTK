export const STATS = ['command', 'strength', 'agility', 'intelligence', 'politics', 'charm']
export const STAT_NAME = {
  command: '统率',
  strength: '武力',
  agility: '敏捷',
  intelligence: '智力',
  politics: '政治',
  charm: '魅力',
}

export const MENU = [
  { label: '存档', key: 'saves' },
  { label: '武将', key: 'generals' },
  { label: '城市', key: 'cities' },
  {
    label: '编队',
    key: 'teams',
    children: [
      { label: '编队预设', key: 'teamPresets' },
      { label: '创建编队', key: 'teamDeploy' },
      { label: '存档部队', key: 'teamTroops' },
    ],
  },
  { label: '外交', key: 'diplo' },
  { label: '检查', key: 'check' },
  { label: '内存', key: 'memory' },
  { label: '说明', key: 'guide' },
  { label: '记录', key: 'log' },
  { label: '设置', key: 'settings' },
]
