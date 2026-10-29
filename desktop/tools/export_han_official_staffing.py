# -*- coding: utf-8 -*-
"""导出汉系 id 1-144 官职 + 编制上限（DT_Official）。"""
import json
import os
import re
import struct
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.dirname(HERE)
ROOT = os.path.dirname(DESKTOP)
DOCS = os.path.join(ROOT, 'docs')
REPAK = os.path.join(HERE, 'repak.exe')
OO2 = os.path.join(HERE, 'oo2core_9_win64.dll')
PAK = (
    r'D:\Program Files (x86)\Steam\steamapps\common\Seres Universalis Three Kingdoms Demo'
    r'\Seres Universalis Three Kingdoms Demo\ProjectA\Content\Paks\pakchunk0-Windows.pak'
)
LEVEL_OFF, STAFF_OFF = -19, 18


def load_uexp():
    env = os.environ.copy()
    env.setdefault('EPIC_GAMES_OODLE_PATH', OO2)
    proc = subprocess.run(
        [REPAK, 'get', PAK, 'ProjectA/Content/DataTable/Generate/Common/DT_Official.uexp'],
        capture_output=True,
        env=env,
    )
    proc.check_returncode()
    return proc.stdout


def main():
    uexp = load_uexp()
    names = {
        o['id']: o['name']
        for o in json.load(
            open(os.path.join(DESKTOP, 'officials_zh.json'), encoding='utf-8')
        )['officials']
    }
    matches = sorted(m.start() for m in re.finditer(rb'OfficialName_(\d+)', uexp))
    rows = []
    for pos in matches:
        oid = re.search(rb'OfficialName_(\d+)', uexp[pos : pos + 25]).group(1).decode()
        if not oid.isdigit() or int(oid) > 144:
            continue
        lv = struct.unpack_from('<i', uexp, pos + LEVEL_OFF)[0]
        if not (1 <= lv <= 9):
            continue
        raw = struct.unpack_from('<i', uexp, pos + STAFF_OFF)[0]
        # 面板同星级编制一致；与 DT_Official 多数武将行 +18 处读数一致：(等级+3)*1000
        staff = (lv + 3) * 1000
        if 1000 <= raw <= 20000 and raw % 1000 == 0:
            staff = raw
        rows.append(
            {
                'id': oid,
                'name': names.get(oid, '?'),
                'level': lv,
                'staffing': staff,
            }
        )
    rows.sort(key=lambda x: (-x['level'], -int(x['id'])))

    json_path = os.path.join(DESKTOP, 'officials_han_staffing.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(
            {'source': 'DT_Official ids 1-144', 'count': len(rows), 'rows': rows},
            f,
            ensure_ascii=False,
            indent=2,
        )

    by_lv = {}
    for r in rows:
        by_lv.setdefault(r['level'], []).append(r)

    lines = [
        '# 汉系官职与编制上限（id 1–144）',
        '',
        '来源：游戏 `DT_Official`（汉系「势力 → 官职」面板主体）。',
        '',
        '**编制** = 面板兵力/编制列；同星级官职编制相同。',
        '',
    ]
    for lv in sorted(by_lv.keys(), reverse=True):
        staff = by_lv[lv][0]['staffing']
        lines.append('## %d 星 · 编制 %d' % (lv, staff))
        lines.append('')
        lines.append('| id | 官职名 | 编制 |')
        lines.append('|----|--------|-----:|')
        for r in by_lv[lv]:
            lines.append('| %s | %s | %d |' % (r['id'], r['name'], r['staffing']))
        lines.append('')

    lines += ['## 按 id 排序（全表）', '', '| id | 官职名 | 等级 | 编制 |', '|----|--------|:----:|-----:|']
    for r in sorted(rows, key=lambda x: int(x['id'])):
        lines.append('| %s | %s | %d | %d |' % (r['id'], r['name'], r['level'], r['staffing']))

    md_path = os.path.join(DOCS, '汉系官职编制.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # sync panel doc
    panel_path = os.path.join(DOCS, '官职面板_汉系1-144.md')
    plines = [
        '# 官职面板（汉系 id 1-144）',
        '',
        '任命：`personages.info.official` = id。编制见下表。',
        '',
        '| 等级 | id | 官职名 | 编制 | 俸禄 |',
        '|------|-----|--------|-----:|-----:|',
    ]
    for r in rows:
        sal = r['level'] * 2 + 2
        plines.append(
            '| %d | %s | %s | %d | %d |' % (r['level'], r['id'], r['name'], r['staffing'], sal)
        )
    with open(panel_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(plines))

    print('rows', len(rows))
    print('wrote', json_path)
    print('wrote', md_path)


if __name__ == '__main__':
    main()
