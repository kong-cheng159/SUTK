# -*- coding: utf-8 -*-
"""将第二批 30 人名的编组字改为与第一套不同的十字（角色字不变）。"""
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

# 第一套（原版 30 人）编组字
TEAM_CHARS_A = ['骠', '骧', '骏', '澜', '霆', '烬', '岳', '朔', '晟', '霄']
# 第二套（平行克隆 30 人）编组字 — 同队三人共享中间字
TEAM_CHARS_B = ['铁', '锋', '虹', '崖', '磐', '焰', '鸿', '启', '耀', '云']


def load_mod():
    path = os.path.join(ROOT, 'SUTKMod.pyw')
    spec = importlib.util.spec_from_file_location('sutkmod', path)
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    M.EXTERN_PATH = os.path.join(
        os.environ.get('LOCALAPPDATA', ''), 'ProjectA', 'Saved', 'ExternPersonage.sav')
    return M


def remap_name(full, team_index):
    """full = 姓 + 两字名；只替换名的第一字（编组字）。"""
    if len(full) < 3:
        raise ValueError('姓名过短: %s' % full)
    sn, nm = full[0], full[1:]
    if len(nm) != 2:
        raise ValueError('名应为两字: %s' % full)
    role = nm[1]
    mid = TEAM_CHARS_B[team_index]
    return sn, mid + role, sn + mid + role


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument('--save', default='AutoSave.sav')
    ap.add_argument('--no-save', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    roster_path = os.path.join(ROOT, 'desktop', 'custom_roster_parallel.json')
    roster = json.load(open(roster_path, encoding='utf-8'))
    if len(roster) != 30:
        raise SystemExit('映射表条目不是 30：%d' % len(roster))

    M = load_mod()
    ext, _ = M.read_extern()
    if ext is None:
        raise SystemExit('找不到 ExternPersonage.sav')

    updates = []
    for i, row in enumerate(roster):
        team_i = i // 3
        old_full = row['new']
        gid = row['new_guid']
        sn, nm, cn = remap_name(old_full, team_i)
        updates.append({
            'guid': gid,
            'was': old_full,
            'now': cn,
            'surname': sn,
            'name': nm,
            'team_char': TEAM_CHARS_B[team_i],
            'maps_to_a': TEAM_CHARS_A[team_i],
        })

    if args.dry_run:
        for u in updates:
            print('%s -> %s  (编组 %s 对应原版 %s)' % (
                u['was'], u['now'], u['team_char'], u['maps_to_a']))
        return

    for u in updates:
        _k, v = M._find_newinfo_entry(ext, u['guid'])
        if not v:
            raise SystemExit('Extern 缺少 GUID: %s' % u['guid'])
        v['surname'] = u['surname']
        v['name'] = u['name']

    if not M.write_extern(ext):
        raise SystemExit('写入 ExternPersonage.sav 失败')

    if not args.no_save:
        path = os.path.join(M.SAVES_DIR, os.path.basename(args.save))
        sav, data = M._load_save_json(path)
        for u in updates:
            _pk, per = M._find_personage_entry(data, u['guid'])
            if per is None:
                print('存档无此人，跳过: %s' % u['was'])
                continue
            M._set_save_person_display(
                per.setdefault('baseInfo', {}), u['surname'], u['name'])
        M._write_save_json(path, sav, data, snapshot=True)

    for row, u in zip(roster, updates):
        row['new'] = u['now']
        row['team_char_b'] = u['team_char']
        row['team_char_a'] = u['maps_to_a']

    with open(roster_path, 'w', encoding='utf-8') as f:
        json.dump(roster, f, ensure_ascii=False, indent=2)

    print('已更新 Extern + 存档（若存在）共 %d 人' % len(updates))
    for u in updates:
        print('  %s -> %s' % (u['was'], u['now']))


if __name__ == '__main__':
    main()
