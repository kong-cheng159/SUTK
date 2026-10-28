# -*- coding: utf-8 -*-
"""从已有自建模板克隆一名新武将（写 ExternPersonage.sav，可选写入当前存档）。

用法:
  python add_custom_general.py --surname 张 --name 三丰
  python add_custom_general.py --surname 张 --name 三丰 --save AutoSave.sav
  python add_custom_general.py --source 6CD5900E4F37C42335D7F981B59DA06D --surname 李 --name 四
"""
import argparse
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def load_mod():
    path = os.path.join(ROOT, 'SUTKMod.pyw')
    spec = importlib.util.spec_from_file_location('sutkmod', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description='克隆新建自建武将')
    ap.add_argument('--source', default='6CD5900E4F37C42335D7F981B59DA06D', help='源模板 GUID')
    ap.add_argument('--surname', required=True, help='姓')
    ap.add_argument('--name', required=True, help='名')
    ap.add_argument('--save', default='', help='同时写入该存档文件名（如 AutoSave.sav）')
    args = ap.parse_args()
    M = load_mod()
    gid, cn = M.clone_custom_extern(args.source, args.surname, args.name)
    print('模板 OK:', cn, gid)
    if args.save:
        path = os.path.join(M.SAVES_DIR, os.path.basename(args.save))
        sav, data = M._load_save_json(path)
        M.spawn_custom_in_save(data, args.source, gid, args.surname, args.name)
        M._write_save_json(path, sav, data)
        print('存档 OK:', path)


if __name__ == '__main__':
    main()
