import { h } from 'vue'
import { NIcon } from 'naive-ui'
import {
  FolderOpenOutline,
  PeopleOutline,
  MapOutline,
  GridOutline,
  AddCircleOutline,
  FlagOutline,
  GlobeOutline,
  ShieldCheckmarkOutline,
  HardwareChipOutline,
  BookOutline,
  ReaderOutline,
  SettingsOutline,
} from '@vicons/ionicons5'

const ICON_BY_KEY = {
  saves: FolderOpenOutline,
  generals: PeopleOutline,
  cities: MapOutline,
  teams: GridOutline,
  teamPresets: GridOutline,
  teamDeploy: AddCircleOutline,
  teamTroops: FlagOutline,
  diplo: GlobeOutline,
  check: ShieldCheckmarkOutline,
  memory: HardwareChipOutline,
  guide: BookOutline,
  log: ReaderOutline,
  settings: SettingsOutline,
}

export function menuIcon(key) {
  const component = ICON_BY_KEY[key]
  if (!component) return undefined
  return () =>
    h(NIcon, { size: 18 }, { default: () => h(component) })
}
