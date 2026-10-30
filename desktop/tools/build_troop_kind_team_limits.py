# -*- coding: utf-8 -*-
"""从游戏 DT_TroopKind 解析各兵种 base 的可创建部队数上限，写入 troop_kind_team_limits.json。"""
import json
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.dirname(HERE)
OUT = os.path.join(DESKTOP, 'data', 'troop_kind_team_limits.json')
UNIQUE_OUT = os.path.join(DESKTOP, 'data', 'troop_kind_unique_bases.json')
REPAK = os.path.join(HERE, 'repak.exe')
OO2 = os.path.join(HERE, 'oo2core_9_win64.dll')
UEXP_REL = 'ProjectA/Content/DataTable/Generate/Common/DT_TroopKind.uexp'
DEFAULT_PAK = (
    r'D:\Program Files (x86)\Steam\steamapps\common\Seres Universalis Three Kingdoms Demo'
    r'\Seres Universalis Three Kingdoms Demo\ProjectA\Content\Paks\pakchunk0-Windows.pak'
)
# 拥有城市解锁的特殊兵种（locres ST_ArchitectureFeature Explain_TroopKind*）
CITY_SPECIAL_BASES = frozenset(
    '31 32 33 38 41 42 43 47 48 49'.split()
)
# 武将/剧情解锁且实测为唯一兵种（DT 常未写 CreatedLimit）
UNIQUE_UNLOCK_BASES = frozenset('39 59'.split())
DEFAULT_MAX = 999


def load_uexp(pak_path):
    env = os.environ.copy()
    env.setdefault('EPIC_GAMES_OODLE_PATH', OO2)
    env.setdefault('OO2PATH', HERE)
    proc = subprocess.run(
        [REPAK, 'get', pak_path, UEXP_REL],
        capture_output=True,
        env=env,
    )
    proc.check_returncode()
    return proc.stdout


def _parse_row_limit(uexp, name_pos):
    for delta in range(96, 220, 4):
        if name_pos + delta + 8 > len(uexp):
            break
        v = struct.unpack_from('<i', uexp, name_pos + delta)[0]
        v2 = struct.unpack_from('<i', uexp, name_pos + delta + 4)[0]
        if v in (1, 2, 3) and v2 in (1, 2, 3, 4, 5):
            return v
    return 0


def parse_limits_from_uexp(uexp):
    by_kind = {}
    for m in re.finditer(rb'Name_(\d+(?:_\d+)?)', uexp):
        tid = m.group(1).decode()
        by_kind[tid] = _parse_row_limit(uexp, m.start())
    by_base = {}
    for tid, lim in by_kind.items():
        if lim <= 0:
            continue
        base = tid.split('_')[0]
        prev = by_base.get(base)
        if prev is None or lim < prev:
            by_base[base] = lim
    for base in CITY_SPECIAL_BASES:
        prev = by_base.get(base)
        if prev is None or prev > 1:
            by_base[base] = 1
    for base in UNIQUE_UNLOCK_BASES:
        prev = by_base.get(base)
        if prev is None or prev > 1:
            by_base[base] = 1
    return by_kind, by_base


def main():
    pak = DEFAULT_PAK
    if len(sys.argv) >= 2:
        pak = sys.argv[1]
    if not os.path.isfile(pak):
        print('找不到 pak：%s' % pak, file=sys.stderr)
        print('用法: build_troop_kind_team_limits.py [pakchunk0-Windows.pak 路径]', file=sys.stderr)
        sys.exit(1)
    uexp = load_uexp(pak)
    by_kind, by_base = parse_limits_from_uexp(uexp)
    overrides = {}
    if os.path.isfile(OUT):
        try:
            prev = json.load(open(OUT, encoding='utf-8'))
            overrides = prev.get('overrides') or {}
        except Exception:
            pass
    payload = {
        'source': 'DT_TroopKind（CreatedLimit 字段）+ 城市解锁特殊兵',
        'default_max': DEFAULT_MAX,
        'by_base': {k: by_base[k] for k in sorted(by_base.keys(), key=lambda x: (len(x), x))},
        'note': (
            '同 base 的变体（如 45、45_3）共享名额；0 或未列出的 base 视为 default_max。'
            '重新生成: desktop/tools/build_troop_kind_team_limits.py'
        ),
    }
    if overrides:
        payload['overrides'] = overrides
        payload['overrides_note'] = prev.get('overrides_note') or (
            '部分城市特殊兵在 DT 中未标上限，以本地存档实测同势力最大支数补正'
        )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    unique = sorted(b for b, n in by_base.items() if n == 1)
    with open(UNIQUE_OUT, 'w', encoding='utf-8') as f:
        json.dump(
            {
                'unique_bases': unique,
                'note': '由 build_troop_kind_team_limits.py 自动生成（max=1 的 base）',
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print('已写入 %s（%d 个受限 base）' % (OUT, len(by_base)))
    print('已同步 %s' % UNIQUE_OUT)


if __name__ == '__main__':
    main()
