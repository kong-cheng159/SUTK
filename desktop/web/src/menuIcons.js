import { h } from 'vue'
import { NIcon } from 'naive-ui'
import {
  FolderOpenOutline,
  PeopleOutline,
  PersonAddOutline,
  MapOutline,
  RibbonOutline,
  GridOutline,
  AddCircleOutline,
  FlagOutline,
  GlobeOutline,
  ShieldCheckmarkOutline,
  HardwareChipOutline,
  BookOutline,
  ReaderOutline,
  SettingsOutline,
  BuildOutline,
} from '@vicons/ionicons5'

const ICON_BY_KEY = {
  saves: FolderOpenOutline,
  generalsRoot: PeopleOutline,
  generals: PeopleOutline,
  customGenerals: PersonAddOutline,
  cities: MapOutline,
  officials: RibbonOutline,
  teamsRoot: GridOutline,
  teamPresets: GridOutline,
  teamDeploy: AddCircleOutline,
  teamTroops: FlagOutline,
  diplo: GlobeOutline,
  toolsRoot: BuildOutline,
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
