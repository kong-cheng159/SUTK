# -*- coding: utf-8 -*-
"""从 Game.locres 生成 desktop/troop_kinds_zh.json（需先解压 locres）。"""
import json
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.dirname(HERE)
LOCres_DEFAULT = os.path.join(HERE, 'Game.zh-CN.locres')
OUT = os.path.join(DESKTOP, 'troop_kinds_zh.json')
REPAK = os.path.join(HERE, 'repak.exe')
LOCres_IN_PAK = 'ProjectA/Content/Localization/Game/zh-CN/Game.locres'


def parse_locres(path):
    d = open(path, 'rb').read()
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
    mapping = {}
    for _ in range(ns_count):
        ns, pos = read_key(pos)
        kc, pos = i32(pos)
        for __ in range(kc):
            key, pos = read_key(pos)
            _, pos = u32(pos)
            idx, pos = i32(pos)
            if not (0 <= idx < len(strings)):
                continue
            val = strings[idx]
            if ns != 'ST_TroopKind':
                continue
            if key.startswith('Name_'):
                tid = key[5:]
                if re.match(r'^\d+(?:_\d+)?$', tid):
                    mapping[tid] = val
    return mapping


def fetch_locres(pak_path, dest):
    env = os.environ.copy()
    env.setdefault('OO2PATH', HERE)
    with open(dest, 'wb') as f:
        subprocess.run(
            [REPAK, 'get', pak_path, LOCres_IN_PAK],
            check=True,
            stdout=f,
            env=env,
        )


def main():
    locres = LOCres_DEFAULT
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg.lower().endswith('.pak'):
            fetch_locres(arg, locres)
        else:
            locres = arg
    if not os.path.isfile(locres):
        print('缺少 locres，用法: build_troop_kinds.py [pak路径|locres路径]', file=sys.stderr)
        sys.exit(1)
    mapping = parse_locres(locres)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2, sort_keys=True)
    print('已写入 %d 条 -> %s' % (len(mapping), OUT))


if __name__ == '__main__':
    main()
