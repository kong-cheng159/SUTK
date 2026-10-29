# -*- coding: utf-8 -*-
"""从游戏 pak 或本地 locres 生成官职/爵位列表。"""
import json
import os
import re
import struct
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.dirname(HERE)
DOCS = os.path.join(os.path.dirname(DESKTOP), 'docs')
LOCres_LOCAL = os.path.join(HERE, 'Game.zh-CN.locres')
REPAK = os.path.join(HERE, 'repak.exe')
OO2 = os.path.join(HERE, 'oo2core_9_win64.dll')
PAK_DEFAULT = (
    r'D:\Program Files (x86)\Steam\steamapps\common\Seres Universalis Three Kingdoms Demo'
    r'\Seres Universalis Three Kingdoms Demo\ProjectA\Content\Paks\pakchunk0-Windows.pak'
)
LOCres_IN_PAK = 'ProjectA/Content/Localization/Game/zh-CN/Game.locres'


def parse_locres_bytes(data):
    d = data
    pos = 17
    str_off = struct.unpack_from('<q', d, pos)[0]
    pos = 29

    def u32(p):
        return struct.unpack_from('<I', d, p)[0], p + 4

    def i32(p):
        return struct.unpack_from('<i', d, p)[0], p + 4

    def read_fstring(p):
        n, p = i32(p)
        if n == 0:
            return '', p
        if n < 0:
            n = -n
            s = d[p : p + n * 2].decode('utf-16le')
            p += n * 2
        else:
            s = d[p : p + n].decode('utf-8', 'replace')
            p += n
        return s.rstrip('\x00'), p

    def read_key(p):
        _, p = u32(p)
        return read_fstring(p)

    sp = str_off
    count, sp = i32(sp)
    strings = []
    for _ in range(count):
        s, sp = read_fstring(sp)
        _, sp = i32(sp)
        strings.append(s)
    ns_count, pos = i32(pos)
    by_ns = {}
    for _ in range(ns_count):
        ns, pos = read_key(pos)
        kc, pos = i32(pos)
        mp = by_ns.setdefault(ns, {})
        for __ in range(kc):
            key, pos = read_key(pos)
            _, pos = u32(pos)
            idx, pos = i32(pos)
            if 0 <= idx < len(strings):
                mp[key] = strings[idx]
    return by_ns


def load_locres():
    if os.path.isfile(PAK_DEFAULT) and os.path.isfile(REPAK):
        env = os.environ.copy()
        env.setdefault('EPIC_GAMES_OODLE_PATH', OO2)
        proc = subprocess.run(
            [REPAK, 'get', PAK_DEFAULT, LOCres_IN_PAK],
            capture_output=True,
            env=env,
        )
        if proc.returncode == 0 and proc.stdout:
            return parse_locres_bytes(proc.stdout)
    if not os.path.isfile(LOCres_LOCAL):
        raise SystemExit('缺少 locres，请放置 %s 或安装游戏' % LOCres_LOCAL)
    return parse_locres_bytes(open(LOCres_LOCAL, 'rb').read())


def sort_id(k):
    try:
        return (0, int(k))
    except ValueError:
        return (1, k)


def build():
    by_ns = load_locres()
    officials = [
        {'id': k.split('_', 1)[1], 'name': v}
        for k, v in by_ns.get('ST_Official', {}).items()
        if k.startswith('OfficialName_')
    ]
    officials.sort(key=lambda x: sort_id(x['id']))

    ranks = [
        {'id': k.split('_', 1)[1], 'name': v}
        for k, v in by_ns.get('ST_FactionRank', {}).items()
        if k.startswith('Name_')
    ]
    ranks.sort(key=lambda x: sort_id(x['id']))

    # 同名不同 id（如两个「司空」）
    by_name = {}
    for o in officials:
        by_name.setdefault(o['name'], []).append(o['id'])

    doc_off = {
        'source': 'DT_Official / ST_Official（任免武将职名）',
        'count': len(officials),
        'note': '与 personages.info.official 一致；当前 Demo pak 内共此条数',
        'officials': officials,
        'duplicate_names': {
            n: ids for n, ids in sorted(by_name.items()) if len(ids) > 1
        },
    }
    with open(os.path.join(DESKTOP, 'officials_zh.json'), 'w', encoding='utf-8') as f:
        json.dump(doc_off, f, ensure_ascii=False, indent=2)

    catalog = {
        'central_official_count': len(officials),
        'faction_rank_count': len(ranks),
        'total_entries': len(officials) + len(ranks),
        'central_officials': officials,
        'faction_ranks': ranks,
    }
    with open(os.path.join(DESKTOP, 'game_titles_zh.json'), 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    lines = [
        '# 游戏职名全集（任免官职 + 势力爵位）',
        '',
        '从 **pak 内** `Game/zh-CN/Game.locres` 解析（与本地 `desktop/tools/Game.zh-CN.locres` 一致）。',
        '',
        '## 任免武将职名（`ST_Official`）',
        '',
        '**共 %d 条**。存档字段 `personages.info.official` = 下表 **id**。'
        ' 例：平东将军 = **110**。' % len(officials),
        '',
        '| id | 官职名 |',
        '|----|--------|',
    ]
    for o in officials:
        lines.append('| %s | %s |' % (o['id'], o['name']))
    lines += [
        '',
        '## 势力爵位（`ST_FactionRank`，官爵面板，不是任免槽 id）',
        '',
        '**共 %d 条**。存档在 `factions.info.rankId` / 晋升用，**不要**与 `info.official` 混用。'
        % len(ranks),
        '',
        '| rankId | 爵位名 |',
        '|--------|--------|',
    ]
    for r in ranks:
        lines.append('| %s | %s |' % (r['id'], r['name']))
    if doc_off['duplicate_names']:
        lines += ['', '## 同名不同 id（任免职名）', '']
        for n, ids in sorted(doc_off['duplicate_names'].items()):
            lines.append('- **%s**：%s' % (n, ', '.join(ids)))
    lines += [
        '',
        '## 为何不是「上千条」？',
        '',
        '- **任免武将**在数据表里就是 **710** 个职名（`DT_Official` 行数 = `ST_Official` 键数）。',
        '- 游戏里「9 级官职」是 **9 个槽位**，每槽从表中选 **1 个职名 + 1 名武将**，不是 9×N 个不同中文名。',
        '- **太守任命**、**城内建筑岗位（祭室/访贤台等）**、**军师/储君** 不算在这 710 条里。',
        '',
    ]
    os.makedirs(DOCS, exist_ok=True)
    md_path = os.path.join(DOCS, '官职列表.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print('officials:', len(officials))
    print('faction ranks:', len(ranks))
    print('wrote officials_zh.json, game_titles_zh.json,', md_path)


if __name__ == '__main__':
    build()
