export const STATS = ['command', 'strength', 'agility', 'intelligence', 'politics', 'charm']
export const STAT_NAME = {
  command: '统率',
  strength: '武力',
  agility: '敏捷',
  intelligence: '智力',
  politics: '政治',
  charm: '魅力',
}

/** 侧栏：一级尽量少；改档/浏览类单独一项，成组功能放二级。 */
export const MENU = [
  { label: '存档', key: 'saves' },
  {
    label: '武将',
    key: 'generalsRoot',
    children: [
      { label: '存档武将', key: 'generals' },
      { label: '自建名录', key: 'customGenerals' },
    ],
  },
  { label: '城市', key: 'cities' },
  {
    label: '编队',
    key: 'teamsRoot',
    children: [
      { label: '编队预设', key: 'teamPresets' },
      { label: '创建编队', key: 'teamDeploy' },
      { label: '存档部队', key: 'teamTroops' },
    ],
  },
  { label: '外交', key: 'diplo' },
  {
    label: '工具',
    key: 'toolsRoot',
    children: [
      { label: '存档检查', key: 'check' },
      { label: '内存修改', key: 'memory' },
      { label: '操作记录', key: 'log' },
    ],
  },
  { label: '说明', key: 'guide' },
  { label: '设置', key: 'settings' },
]

/** 点击仅作分组的父级时，默认打开的子页 */
export const MENU_PARENT_DEFAULT = {
  generalsRoot: 'generals',
  teamsRoot: 'teamPresets',
  toolsRoot: 'check',
}
