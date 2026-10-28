# -*- coding: utf-8 -*-
"""按十支预设顺序克隆 30 名自建武将：改姓，并换第二套编组字（角色字不变）。"""
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

# 第一套编组字（原版）：骠骧骏澜霆烬岳朔晟霄
TEAM_CHARS_A = ['骠', '骧', '骏', '澜', '霆', '烬', '岳', '朔', '晟', '霄']
# 第二套编组字（本批克隆）：同队三人共享中间字，便于与第一套区分
TEAM_CHARS_B = ['铁', '锋', '虹', '崖', '磐', '焰', '鸿', '启', '耀', '云']

# 30 个新单姓（与原版 30 姓错开，仍为一字姓）
NEW_SURNAMES = [
    '张', '李', '王',  # 骠 队
    '刘', '陈', '杨',  # 骧
    '黄', '赵', '吴',  # 骏
    '徐', '孙', '朱',  # 澜
    '胡', '郭', '何',  # 霆
    '高', '林', '郑',  # 烬
    '梁', '宋', '唐',  # 岳
    '冯', '于', '董',  # 朔
    '袁', '潘', '蒋',  # 晟
    '蔡', '余', '魏',  # 霄
]


def load_mod(app_dir=None):
    path = os.path.join(ROOT, 'SUTKMod.pyw')
    spec = importlib.util.spec_from_file_location('sutkmod', path)
    M = importlib.util.module_from_spec(spec)
    if app_dir:
        os.environ['SUTK_APP_DIR'] = app_dir
    spec.loader.exec_module(M)
    return M


def preset_guids(cfg):
    out = []
    for p in cfg.get('team_presets') or []:
        for g in p.get('generals') or []:
            out.append(str(g).strip())
    return out


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument('--save', default='AutoSave.sav', help='同时写入的存档名')
    ap.add_argument('--no-save', action='store_true', help='只写 ExternPersonage.sav')
    ap.add_argument('--config', default='', help='config.json 路径')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    app_dir = os.path.join(ROOT, 'desktop-app', 'dist', 'SUTK修改器')
    cfg_path = args.config or os.path.join(app_dir, 'config.json')
    if not os.path.isfile(cfg_path):
        cfg_path = os.path.join(ROOT, 'config.json')
    cfg = json.load(open(cfg_path, encoding='utf-8'))
    guids = preset_guids(cfg)
    if len(guids) != 30:
        raise SystemExit('预设武将 GUID 数量不是 30：%d' % len(guids))

    M = load_mod(app_dir if os.path.isdir(app_dir) else None)
    M.EXTERN_PATH = os.path.join(
        os.environ.get('LOCALAPPDATA', ''), 'ProjectA', 'Saved', 'ExternPersonage.sav')
    if app_dir and os.path.isdir(app_dir):
        M.APP_DIR = app_dir
        M.BACKUP_DIR = os.path.join(app_dir, 'backup')
        M.CONFIG_PATH = os.path.join(app_dir, 'config.json')

    ext, _ = M.read_extern()
    if ext is None:
        raise SystemExit('找不到 ExternPersonage.sav')

    pairs = []
    for i, gid in enumerate(guids):
        _k, v = M._find_newinfo_entry(ext, gid)
        if not v:
            raise SystemExit('模板缺少 GUID: %s' % gid)
        nm = str(v.get('name') or '').strip()
        old_sn = str(v.get('surname') or '').strip()
        new_sn = NEW_SURNAMES[i]
        team_i = i // 3
        if len(nm) == 2:
            new_nm = TEAM_CHARS_B[team_i] + nm[1]
        else:
            new_nm = nm
        pairs.append((gid, old_sn, new_sn, new_nm, old_sn + nm))

    if args.dry_run:
        for i, (g, osn, nsn, nm, old_full) in enumerate(pairs, 1):
            print('%2d %s -> %s%s  [编组%s] (%s..)' % (
                i, old_full, nsn, nm, TEAM_CHARS_B[(i - 1) // 3], g[:8]))
        return

    created = []
    guid_remap = {}
    for gid, _osn, new_sn, new_nm, old_full in pairs:
        new_gid, cn = M.clone_custom_extern(gid, new_sn, new_nm)
        guid_remap[str(gid).strip().upper()] = new_gid
        created.append((old_full, cn, new_gid, gid))

    ext, _ = M.read_extern()
    for _old_full, _cn, new_gid, _src in created:
        _k, v = M._find_newinfo_entry(ext, new_gid)
        if v:
            M.remap_custom_relations(v, guid_remap)
    if not M.write_extern(ext):
        raise SystemExit('写入亲近/相性映射失败')

    lines = ['ExternPersonage.sav 已克隆 %d 人（已重映射亲近/相性 GUID）' % len(created)]

    if not args.no_save:
        path = os.path.join(M.SAVES_DIR, os.path.basename(args.save))
        sav, data = M._load_save_json(path)
        for i, (_old_full, _cn, new_gid, src_gid) in enumerate(created):
            M.spawn_custom_in_save(
                data, src_gid, new_gid, NEW_SURNAMES[i], pairs[i][3])  # new_nm
        M._write_save_json(path, sav, data, snapshot=True)
        lines.append('已写入存档: %s' % path)

    out_json = os.path.join(ROOT, 'desktop', 'custom_roster_parallel.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(
            [
                {
                    'old': c[0],
                    'new': c[1],
                    'new_guid': c[2],
                    'source_guid': c[3],
                }
                for c in created
            ],
            f,
            ensure_ascii=False,
            indent=2,
        )
    lines.append('映射表: %s' % out_json)
    print('\n'.join(lines))
    for c in created:
        print('  %s -> %s  %s' % (c[0], c[1], c[2]))


if __name__ == '__main__':
    main()
