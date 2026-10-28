# -*- coding: utf-8 -*-
"""按 custom_roster_parallel.json 修正第二批 30 人的 closees / idelPersonage GUID。"""
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main():
    roster_path = os.path.join(ROOT, 'desktop', 'custom_roster_parallel.json')
    if not os.path.isfile(roster_path):
        raise SystemExit('缺少映射表: %s' % roster_path)
    roster = json.load(open(roster_path, encoding='utf-8'))
    guid_remap = {}
    for row in roster:
        s = str(row.get('source_guid') or '').strip().upper()
        n = str(row.get('new_guid') or '').strip().upper()
        if s and n:
            guid_remap[s] = n

    path = os.path.join(ROOT, 'SUTKMod.pyw')
    spec = importlib.util.spec_from_file_location('m', path)
    M = importlib.util.module_from_spec(spec)
    M.EXTERN_PATH = os.path.join(
        os.environ.get('LOCALAPPDATA', ''), 'ProjectA', 'Saved', 'ExternPersonage.sav')
    spec.loader.exec_module(M)

    d, _ = M.read_extern()
    if not d:
        raise SystemExit('找不到 ExternPersonage.sav')

    fixed = 0
    for row in roster:
        new_gid = row.get('new_guid')
        _k, v = M._find_newinfo_entry(d, new_gid)
        if not v:
            print('跳过（无模板）:', row.get('new'))
            continue
        before = (list(v.get('closees') or []), v.get('idelPersonage'))
        M.remap_custom_relations(v, guid_remap)
        after = (list(v.get('closees') or []), v.get('idelPersonage'))
        if before != after:
            fixed += 1
            print('%s  closees %s -> %s  idel %s -> %s' % (
                row.get('new'),
                before[0], after[0], before[1], after[1]))

    if not M.write_extern(d):
        raise SystemExit('写入失败')
    print('已更新 %d 人亲近/相性引用' % fixed)


if __name__ == '__main__':
    main()
