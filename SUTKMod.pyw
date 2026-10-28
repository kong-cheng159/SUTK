#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SUTK 存档修改器（常驻版）
=================================
目标游戏: Seres Universalis: Three Kingdoms (Demo)

特性
----
* 随游戏启动自动生效（常驻监视 SUTK-Win64-Shipping.exe）
* 游戏启动时弹出原生弹窗：保持启用 / 全部撤销 / 完全卸载
* 作用于 Saves 目录下**所有**存档，不限存档位
* 原档全部备份，随时一键还原；不修改游戏本体任何文件
* 可自由安装 / 卸载（只写 HKCU 一个 Run 键）

用法
----
    pythonw SUTKMod.pyw            常驻监视（安装后开机自动运行）
    python  SUTKMod.pyw --install  安装（加入开机启动）
    python  SUTKMod.pyw --uninstall 卸载并还原全部存档
    python  SUTKMod.pyw --apply    立刻对所有存档应用
    python  SUTKMod.pyw --restore  立刻还原全部存档
    python  SUTKMod.pyw --report   查看状态
"""
import sys, os, io, json, zlib, struct, shutil, time, subprocess, ctypes, threading, copy, uuid
import unicodedata
import re

# ----------------------------------------------------------------- 常量
GAME_PROC = "SUTK-Win64-Shipping.exe"
APP_NAME = "SUTKMod"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

LOCAL = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
SAVES_DIR = os.path.join(LOCAL, r'ProjectA\Saved\Saves')
# 自建武将（编辑器里捏的）模板文件，UTF-16 JSON
EXTERN_PATH = os.path.join(LOCAL, r'ProjectA\Saved\ExternPersonage.sav')

SELF = os.path.abspath(__file__)
# 便携模式: 同目录下有 python\ 子目录时, 一切数据都存在自己旁边
_PORTABLE = os.path.isdir(os.path.join(os.path.dirname(SELF), 'python'))
APP_DIR = os.path.dirname(SELF) if _PORTABLE else os.path.join(LOCAL, APP_NAME)
BACKUP_DIR = os.path.join(APP_DIR, 'backup')
HISTORY_DIR = os.path.join(APP_DIR, 'history')   # 工具自己的历史快照
HIST_KEEP = 30                                    # 每个存档保留份数
TRASH_DIR = os.path.join(HISTORY_DIR, '_trash')   # 存档删掉后的本地副本挪到这
TRASH_KEEP_DAYS = 7                               # 回收站保留天数
REAP_STRIKES = 15                                 # 连续多少次看不到才算真删（约 30 秒）
_SAVES_DEFAULT = SAVES_DIR                        # 加载时的真实存档目录


# 修改上限
CAP_MONEY = 999_999_999
CAP_CONSCRIPTION = 99_999_999
CAP_FOOD = 99_999_999
CAP_TECH = 99_999_999
CAP_TACTICAL = 100

# 可自定义的目标数值（config.json 的 caps 段 / 命令行参数 会覆盖这里）
INT32_MAX = 2147483647
# 科技树 id 空间 1..90（5 个存档实测覆盖 89 个，缺口仅 56）
TECH_ID_MAX = 90
# 各兵种的兵力天花板：由 17 个原始存档统计得出（勿手工乱改）
# 不同兵种差别很大（55_2=16000 / 27=15000 / 36_1=1404），不能用一个固定值
TROOP_CAP_BY_KIND = {
    '55_2': 16000, '27': 15000, '13': 14000, '17': 14000,
    '19': 14000, '21': 14000, '23': 14000, '25': 14000,
    '31_3': 14000, '38_3': 14000, '42_3': 14000, '44': 14000,
    '64': 14000, '65': 14000, '30_2': 13000, '32_2': 13000,
    '33_2': 13000, '48_2': 13000, '53_2': 13000, '54_2': 13000,
    '61': 13000, '62': 13000, '7': 13000, '15': 12000,
    '36_2': 12000, '43_2': 12000, '48_3': 12000, '2': 11000,
    '32_3': 11000, '45_3': 11000, '47_2': 11000, '5': 11000,
    '53': 10000, '54': 10000, '54_1': 10000, '38_2': 9000,
    '11': 8000, '33_3': 8000, '40_3': 8000, '49_3': 8000,
    '39_1': 7000, '4': 7000, '41_2': 7000, '41_3': 7000,
    '43_3': 7000, '49_1': 7000, '9': 7000, '1': 6000,
    '3': 6000, '31_1': 6000, '39': 6000, '40_2': 6000,
    '42_2': 6000, '47_3': 6000, '50_2': 6000, '36_3': 5000,
    '37_3': 5000, '38': 5000, '38_1': 5000, '39_2': 5000,
    '40_1': 5000, '47': 5000, '47_1': 5000, '48': 5000,
    '48_1': 5000, '49': 5000, '50_1': 5000, '60': 5000,
    '31': 4000, '40': 4000, '41': 4000, '41_1': 4000,
    '50': 4000, '30': 3299, '43': 3000, '45_2': 3000,
    '53_1': 3000, '55': 3000, '55_1': 3000, '36_1': 1404,
}
TROOP_STAFF_FALLBACK = 0      # 未收录兵种: 0 = 保持原样不动

# 武将六维（游戏上限 100，采样 23962 人全部落在 1~100）
STAT_KEYS = ('command', 'strength', 'agility', 'intelligence', 'politics', 'charm')
STAT_LABEL = {'command': '统率', 'strength': '武力', 'agility': '敏捷',
              'intelligence': '智力', 'politics': '政治', 'charm': '魅力'}
STAT_MAX = 100
STATS = {k: STAT_MAX for k in STAT_KEYS}      # attr 模块的目标值，可由 config 覆盖
CAPS = {'money': CAP_MONEY, 'conscription': CAP_CONSCRIPTION,
        'food': CAP_FOOD, 'tech': CAP_TECH, 'tactical': CAP_TACTICAL,
        'supply': 9999999, 'troop': 0}
CAP_LABEL = {'money': '金钱', 'conscription': '兵役', 'food': '粮食',
             'tech': '科技点数', 'tactical': '（已停用·原为战法ID）', 'supply': '可供给上限',
             'troop': '单队兵力上限(0=按兵种自动)'}
# 这些字段游戏里是 int32, 超过就会溢出 -> 必须钳制
CLAMP_KEYS = ('money', 'conscription', 'food', 'tech', 'supply', 'troop')


def clamp_cap(k, v):
    """把数值限制在游戏能接受的范围内, 返回 (值, 是否被钳制)"""
    try:
        v = int(v)
    except Exception:
        return CAPS.get(k), False
    if k in CLAMP_KEYS and v > INT32_MAX:
        return INT32_MAX, True
    if v < 0:
        return 0, True
    return v, False

NOGUI = False

MB_OK, MB_OKCANCEL, MB_YESNOCANCEL = 0, 1, 3
MB_YESNO = 4
MB_ICONINFO, MB_ICONQUESTION, MB_ICONWARN = 0x40, 0x20, 0x30
MB_TOPMOST, MB_SETFOREGROUND = 0x40000, 0x10000
IDOK, IDYES, IDNO, IDCANCEL = 1, 6, 7, 2


# ----------------------------------------------------------------- 弹窗
def popup(text, title="SUTK 修改器", flags=MB_OK | MB_ICONINFO):
    if NOGUI:
        log("[popup] " + text)
        return IDYES
    try:
        return ctypes.windll.user32.MessageBoxW(None, text, title,
                                                flags | MB_TOPMOST | MB_SETFOREGROUND)
    except Exception:
        print(text)
        return IDOK


RESULT_FILE = None


def log(msg):
    if sys.stdout is not None:
        print(msg)
    if RESULT_FILE:
        try:
            with open(RESULT_FILE, 'a', encoding='utf-8') as f:
                f.write(str(msg) + '\n')
        except Exception:
            pass


LOG_PATH = None


def flog(msg):
    """写日志文件, 便于无人值守时排查"""
    global LOG_PATH
    if LOG_PATH is None:
        LOG_PATH = os.path.join(APP_DIR, 'mod.log')
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        line = time.strftime('[%Y-%m-%d %H:%M:%S] ') + msg + '\n'
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass


# ----------------------------------------------------------------- 存档读写
MAGIC = "BO-QI-DAO-ProjectA-ZLIB-1"


def read_sav(path):
    b = open(path, 'rb').read()
    mlen = struct.unpack_from('<i', b, 0)[0]
    if not (0 < mlen < 256):
        raise ValueError("魔数长度异常")
    magic = b[4:4 + mlen - 1].decode('utf-8', 'replace')
    p = 4 + mlen
    hlen = struct.unpack_from('<i', b, p)[0]; p += 4
    header = b[p:p + hlen]; p += hlen
    hcrc, usize, csz = struct.unpack_from('<III', b, p); p += 12
    comp = b[p:p + csz]; p += csz
    body = zlib.decompress(comp)
    if len(body) != usize:
        raise ValueError("解压长度不符")
    return dict(magic=magic, header=header, body=body)


def build_sav(sav, body):
    comp = zlib.compress(body, 6)
    out = io.BytesIO()
    m = MAGIC.encode('utf-8') + b'\x00'
    out.write(struct.pack('<i', len(m))); out.write(m)
    out.write(struct.pack('<i', len(sav['header']))); out.write(sav['header'])
    out.write(struct.pack('<III', zlib.crc32(sav['header']),
                          len(body), len(comp)))
    out.write(comp)
    out.write(struct.pack('<I', zlib.crc32(comp)))
    return out.getvalue()


# ----------------------------------------------------------------- 修改核心
# ！！绝对禁止写入的字段（都是 ID / 引用，写错会毁档）
#   tactical = 战法 ID（曾把它当"技巧"写成 100，导致全势力战法消失）
FORBIDDEN_WRITE = {
    'tactical',          # 战法 ID
    'talentTreeId',      # 天赋树 ID
    'awakentTalent',     # 觉醒天赋 ID
    'factionId', 'troopId', 'troopKindId', 'resId',
}


def _set(holder, key, value):
    """按原字段类型写入 —— 存档里同一字段可能是 int / float / str,
    类型写错会导致游戏反序列化失败, 因此严格保持原类型。
    黑名单里的字段一律拒绝写入。"""
    if key in FORBIDDEN_WRITE:
        flog("BLOCKED write to forbidden key: %s (value=%r)" % (key, value))
        return False
    if key not in holder:
        return False
    cur = holder[key]
    if isinstance(cur, bool):
        holder[key] = bool(value)
    elif isinstance(cur, str):
        # 字符串型数值要保持字符串形态, 且不带多余小数
        if isinstance(value, float) and value.is_integer():
            holder[key] = str(int(value))
        else:
            holder[key] = str(value)
    elif isinstance(cur, float):
        holder[key] = float(value)
    elif isinstance(cur, int):
        holder[key] = int(value)
    else:
        holder[key] = value
    return True


# 每个模块互相独立，可任意组合
SECTIONS_ALL = ('money', 'conscript', 'food', 'tech', 'supply', 'troop', 'auto', 'attr')
SECTIONS_NAME = {
    'money': '金钱', 'conscript': '兵役', 'food': '粮食',
    'tech': '科技全满', 'supply': '可供给上限', 'troop': '部队满编',
    'auto': '自动开关', 'attr': '武将六维'}
SECTIONS_TIP = {
    'money': 'info.money 拉满',
    'conscript': 'info.conscription 拉满（人力池）',
    'food': 'faction.food 拉满',
    'tech': '1~90 全部激活 + 点数满 + 清空队列',
    'supply': 'suppportMaxAdd 提高编制上限',
    'troop': '每队 staffing/healthyNum=14000、伤兵清零、士气气力经验满',
    'auto': '自动学天赋 / 赏赐 / 升建筑',
    'attr': '武将 统率/武力/敏捷/智力/政治/魅力 = 100（不动战法）'}
# 兼容旧名
SECTION_ALIAS = {
    'res': ('money', 'conscript', 'food'),
    'supplyall': ('supply', 'troop'),
    'army': ('supply', 'troop'),
    '部队': ('supply', 'troop'),
    '资源': ('money', 'conscript', 'food'),
}
SCOPE_NAME = {'player': '仅玩家势力', 'all': '所有势力(含AI)'}


def parse_sections(text):
    """None/空/'all' -> 全部；否则按逗号解析（支持旧别名 res）"""
    if text is None:
        return None
    t = str(text).strip().lower()
    if not t or t == 'all':
        return set(SECTIONS_ALL)
    out = set()
    for x in t.replace('，', ',').split(','):
        x = x.strip()
        if not x:
            continue
        if x in SECTION_ALIAS:
            out |= set(SECTION_ALIAS[x])
        elif x in SECTIONS_ALL:
            out.add(x)
    return out


def sections_label(secs):
    """给用户看的一行"""
    secs = set(SECTIONS_ALL) if secs is None else set(secs)
    if secs == set(SECTIONS_ALL):
        return '全部'
    if not secs:
        return '（未选任何项目）'
    return '、'.join(SECTIONS_NAME[x] for x in SECTIONS_ALL if x in secs)


def troop_cap(kind, cur):
    """该兵种的目标兵力：只升不降
    - CAPS['troop'] > 0  -> 用户指定固定值
    - 否则按兵种表；未收录的兵种保持原样
    """
    try:
        cur = int(cur or 0)
    except Exception:
        cur = 0
    user = 0
    try:
        user = int(CAPS.get('troop') or 0)
    except Exception:
        user = 0
    if user > 0:
        return max(cur, user)
    base = TROOP_CAP_BY_KIND.get(str(kind), TROOP_STAFF_FALLBACK)
    return max(cur, base)


def _target_factions(data, scope):
    """scope: player(默认) | all | ids:1,2,3"""
    facs = data.get('factions') or {}
    if scope == 'all':
        return list(facs.items())
    if scope and str(scope).lower().startswith('ids:'):
        want = {x.strip().lower() for x in str(scope)[4:].split(',') if x.strip()}
        return [(k, v) for k, v in facs.items() if str(k).lower() in want]
    return [(k, v) for k, v in facs.items() if v.get('bIsPlayerCtrl')]


def patch_faction(data, fid, fac, secs):
    """对单个势力应用选中的模块"""
    st = dict(tech=0, troop=0, attr=0)

    if 'money' in secs:
        _set(fac.setdefault('info', {}), 'money', CAPS['money'])
    if 'conscript' in secs:
        _set(fac.setdefault('info', {}), 'conscription', CAPS['conscription'])
    if 'food' in secs:
        _set(fac, 'food', CAPS['food'])

    if 'tech' in secs:
        # 一键全满: 直接把 1..TECH_ID_MAX 全部写入已激活列表
        tech = fac.setdefault('technology', {})
        ids = [str(i) for i in range(1, TECH_ID_MAX + 1)]
        tech['activatedList'] = ids
        tech['queue'] = []
        tech['points'] = {i: CAPS['tech'] for i in ids}
        if 'lastPoint' in tech:
            tech['lastPoint'] = 0
        st['tech'] = len(ids)

    if 'supply' in secs:
        # 势力级"可供给上限"：决定你能编制多少部队
        _set(fac, 'suppportMaxAdd', CAPS['supply'])

    if 'troop' in secs:
        for tid, t in (fac.get('troops') or {}).items():
            if t.get('bDestroyed'):
                continue
            # 满编: 按兵种上限补到满, 只升不降; 伤兵清零
            cap = troop_cap(t.get('troopKindId'), t.get('staffing'))
            if cap > 0:
                _set(t, 'staffing', cap)
                _set(t, 'healthyNum', cap)
            _set(t, 'injuriedNum', 0)
            _set(t, 'supplyPriority', 'High')
            _set(t, 'lastSupplyLevel', 'Max')
            _set(t, 'lastSupplyNum', 99999)
            _set(t, 'supplyWeakStartTick', 0)
            _set(t, 'bAutoUpdateMaxStaff', True)
            _set(t, 'bAutoUseTactical', True)
            _set(t, 'experience', 999999)
            _set(t, 'morale', 1000)
            _set(t, 'vigor', 1000)
            _set(t, 'anger', 1000)
            st['troop'] += 1

    if 'auto' in secs:
        for k in ('bAutoLearnTalent', 'bAutoReward', 'bAutoUpArchitecture'):
            _set(fac, k, True)

    if 'attr' in secs:
        # 只改六维属性(command/strength/agility/intelligence/politics/charm)
        # ！！绝对不要动 baseInfo.tactical —— 那是【战法ID】，不是属性值，
        #    写成 100 会让所有武将的战法变成同一个不存在的战法（战法"消失"）
        for pid, per in (data.get('personages') or {}).items():
            pinfo = per.get('info') or {}
            # 注意: 势力键为 "new_0", 武将身上写作 "New_0", 必须忽略大小写
            if str(pinfo.get('faction', '')).lower() != str(fid).lower():
                continue
            if pinfo.get('tag1') in ('Death', 'Dead'):
                continue
            bi = per.get('baseInfo') or {}
            n = 0
            for k in STAT_KEYS:
                if k in bi and _set(bi, k, STATS[k]):
                    n += 1
            if n:
                st['attr'] += 1

    return st


def patch_body(data, scope='player', secs=None):
    secs = set(SECTIONS_ALL) if secs is None else set(secs)
    tot = dict(factions=0, ids=[], tech=0, troop=0, attr=0)
    for fid, fac in _target_factions(data, scope):
        st = patch_faction(data, fid, fac, secs)
        tot['factions'] += 1
        tot['ids'].append(str(fid))
        for k in ('tech', 'troop', 'attr'):
            tot[k] += st[k]
    return tot


def backup_path(sav_path):
    return os.path.join(BACKUP_DIR, os.path.basename(sav_path) + '.orig')


APPLY_VERSION = 8


def _signature(scope, secs):
    # 数值配置也进签名: 改了目标数值就必须重新打一遍
    capsig = ','.join('%s=%s' % (k, CAPS.get(k)) for k in sorted(CAPS))
    statsig = ','.join('%s=%s' % (k, STATS.get(k)) for k in STAT_KEYS)
    return "%d|%s|%s|%s|%s" % (APPLY_VERSION, scope, ','.join(sorted(secs)),
                               capsig, statsig)


def _marker(sav_path):
    return os.path.join(BACKUP_DIR, os.path.basename(sav_path) + '.applied')


def _is_current(sav_path, sig):
    """已按同一套设置处理过, 且文件之后没被游戏重写"""
    m = _marker(sav_path)
    if not (os.path.exists(m) and os.path.exists(sav_path)):
        return False
    try:
        if open(m, encoding='utf-8').read().strip() != sig:
            return False
        return os.path.getmtime(m) >= os.path.getmtime(sav_path)
    except Exception:
        return False


def apply_all(saves_dir=None, only=None, scope='player', secs=None, force=False,
              min_age=0, recent_secs=None):
    """对所有存档应用修改。
    min_age: 只处理修改时间早于 N 秒的文件(避开游戏正在写)
    recent_secs: 只处理最近 N 秒内被写过的文件(即"游戏刚存的那个档")"""
    apply_caps(load_cfg())
    d = saves_dir or SAVES_DIR
    secs = set(SECTIONS_ALL) if secs is None else set(secs)
    sig = _signature(scope, secs)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    done = skipped = failed = 0
    lines = []
    if not os.path.isdir(d):
        return 0, 0, 1, ["  存档目录不存在: " + d]
    names = [n for n in os.listdir(d) if n.lower().endswith('.sav')]
    for n in names:
        if only and n != only:
            continue
        p = os.path.join(d, n)
        try:
            age = time.time() - os.path.getmtime(p)
            if min_age > 0 and age < min_age:
                skipped += 1
                lines.append("  [跳过] %s 刚被写入, 稍后再试" % n)
                continue
            if recent_secs is not None and age > recent_secs:
                continue
            sav = read_sav(p)
            if not force and _is_current(p, sig):
                skipped += 1
                lines.append("  [已是最新] " + n)
                continue
            bak = backup_path(p)
            if not os.path.exists(bak):
                shutil.copy2(p, bak)
            if _in_real_saves(p):
                snapshot_save(p, 'apply')      # 改之前先留底，随时能退
            data = json.loads(sav['body'].decode('utf-8'))
            st = patch_body(data, scope, secs)
            if not st['factions']:
                failed += 1
                lines.append("  [跳过] %s 找不到目标势力" % n)
                continue
            body = json.dumps(data, ensure_ascii=False,
                              separators=(',', ':'), allow_nan=False).encode('utf-8')
            blob = build_sav(sav, body)
            tmp = p + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(blob)
            os.replace(tmp, p)
            with open(_marker(p), 'w', encoding='utf-8') as f:
                f.write(sig)
            done += 1
            lines.append("  [完成] %-26s 势力[%s] 科技%d 部队%d 武将%d"
                         % (n, ','.join(st['ids'])[:20], st['tech'], st['troop'], st['attr']))
        except Exception as e:
            failed += 1
            lines.append("  [失败] %s : %s" % (n, e))
    return done, skipped, failed, lines


def newest_save(saves_dir=None):
    """返回最近修改的存档文件名(通常就是正在玩的那个)"""
    d = saves_dir or SAVES_DIR
    if not os.path.isdir(d):
        return None
    items = [(os.path.getmtime(os.path.join(d, n)), n)
             for n in os.listdir(d) if n.lower().endswith('.sav')]
    return max(items)[1] if items else None


def restore_all(saves_dir=None, only=None, confirm=False):
    """还原存档。only=None 表示全部 —— 必须显式 confirm=True，
    否则拒绝执行（历史上误触一次，把 25 个备份全写成 .sav，用户以为存档炸了）。"""
    if only is None and not confirm:
        bdir = BACKUP_DIR
        n = len([x for x in os.listdir(bdir) if x.endswith('.orig')]) \
            if os.path.isdir(bdir) else 0
        return 0, ['⚠ 已阻止：全量还原需要 confirm=True（会把 %d 个备份档全部写回）' % n,
                   '  想还原单个档请用 --only 指定，或在控制台按 4 选编号']
    """从备份还原全部存档。返回 (n, lines)"""
    if not os.path.isdir(BACKUP_DIR):
        return 0, ["  没有备份记录"]
    n = 0
    lines = []
    for bak in sorted(os.listdir(BACKUP_DIR)):
        if not bak.lower().endswith('.orig'):
            continue
        name = bak[:-5]
        if only and name != only:
            continue
        target = os.path.join(saves_dir or SAVES_DIR, name)
        try:
            shutil.copy2(os.path.join(BACKUP_DIR, bak), target)
            n += 1
            lines.append("  [还原] " + name)
        except Exception as e:
            lines.append("  [失败] %s : %s" % (name, e))
    # 清掉"已处理"标记, 下次会重新应用
    for m in os.listdir(BACKUP_DIR):
        if m.lower().endswith('.applied'):
            try:
                os.remove(os.path.join(BACKUP_DIR, m))
            except Exception:
                pass
    return n, lines


# ----------------------------------------------------------------- 进程检测
def _pids():
    """返回游戏进程 PID 列表"""
    pids = []
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        out = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq %s" /FO CSV /NH' % GAME_PROC,
            shell=True, startupinfo=si, creationflags=0x08000000)
        for line in out.decode('gbk', 'ignore').splitlines():
            parts = [x.strip('"') for x in line.split('","')]
            if len(parts) >= 2 and parts[0].lower() == GAME_PROC.lower():
                try:
                    pids.append(int(parts[1]))
                except ValueError:
                    pass
    except Exception:
        pass
    return pids


def _has_window(pid):
    """该进程是否有可见且带标题的窗口 —— 用来排除退出后残留的僵尸进程"""
    found = []
    try:
        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(hwnd, lp):
            u = ctypes.windll.user32
            if not u.IsWindowVisible(hwnd):
                return True
            p = ctypes.c_ulong()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and u.GetWindowTextLengthW(hwnd) > 0:
                found.append(hwnd)
            return True

        ctypes.windll.user32.EnumWindows(CB(cb), 0)
    except Exception:
        return True  # 检测失败时保守放行
    return len(found) > 0


def game_running():
    for pid in _pids():
        if _has_window(pid):
            return True
    return False


# ----------------------------------------------------------------- 安装卸载
def exe_dir():
    return os.path.dirname(sys.executable)


def python_exe():
    for d in (os.path.join(APP_DIR, 'python'), os.path.join(os.path.dirname(SELF), 'python'),
              exe_dir()):
        p = os.path.join(d, 'python.exe')
        if os.path.exists(p):
            return p
    return sys.executable


def pythonw():
    for d in (os.path.join(APP_DIR, 'python'), os.path.join(os.path.dirname(SELF), 'python'),
              exe_dir()):
        p = os.path.join(d, 'pythonw.exe')
        if os.path.exists(p):
            return p
    return sys.executable


def startup_vbs():
    """开机启动用的 vbs 路径（启动文件夹，纯文件，可验证可删除）"""
    base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                        r'Microsoft\Windows\Start Menu\Programs\Startup')
    return os.path.join(base, APP_NAME + '.vbs')


SHORTCUT_NAMES = ('SUTK 修改器.bat', 'SUTK 控制台.bat', 'SUTK 后台.bat')


def _write_gbk(path, text):
    """写 GBK + CRLF。
    注意: 必须用二进制写 —— 文本模式 + encoding='mbcs' 会把 \r\n 变成 \r\r\n，
    多出来的 \r 会被 cmd 当成路径的一部分，导致 call "带中文的路径" 被截断。
    """
    data = text.replace('\r\n', '\n').replace('\r', '\n')
    data = data.replace('\n', '\r\n')
    with open(path, 'wb') as f:
        f.write(data.encode('gbk', 'replace'))


def desktop_dirs():
    cands = [os.path.join(os.path.expanduser('~'), 'Desktop'),
             os.path.join(os.environ.get('OneDrive', ''), 'Desktop'),
             os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')]
    out = []
    for d in cands:
        if d and os.path.isdir(d) and os.path.abspath(d) not in out:
            out.append(os.path.abspath(d))
    return out


def make_shortcut():
    """在桌面放一个入口，指向本目录的「2 启动修改器.bat」"""
    dirs = desktop_dirs()
    if not dirs:
        return None
    entry = os.path.join(APP_DIR, '2 启动修改器.bat')
    if not os.path.exists(entry):
        entry = os.path.join(APP_DIR, '控制台.bat')
    made = None
    path = os.path.join(dirs[0], 'SUTK 修改器.bat')
    body = ('@echo off\nchcp 936 >nul\ncd /d "%%~dp0"\n'
            'title SUTK 修改器\ncall "%s"\n' % entry)
    try:
        _write_gbk(path, body)
        made = path
        flog("shortcut created: " + path)
    except Exception as e:
        flog("shortcut failed: %s" % e)

    # 清理历史遗留图标
    for desk in dirs:
        for nm in SHORTCUT_NAMES:
            q = os.path.join(desk, nm)
            if os.path.exists(q) and (made is None or
                                      os.path.abspath(q) != os.path.abspath(made)):
                try:
                    os.remove(q)
                    flog("old shortcut removed: " + q)
                except Exception:
                    pass
    return made


def start_watcher():
    """静默拉起后台（已有实例会自己退出）"""
    try:
        flags = 0x00000008 | 0x00000200        # DETACHED_PROCESS | NEW_PROCESS_GROUP
        errf = open(os.path.join(APP_DIR, 'watch_err.log'), 'ab', buffering=0)
        p = subprocess.Popen([pythonw(), SELF, '--watch'],
                             creationflags=flags, close_fds=True, cwd=APP_DIR,
                             stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,
                             stderr=errf)
        flog("watcher launched pid=%s" % p.pid)
        return p.pid
    except Exception as e:
        flog("watcher launch failed: %s" % e)
        return None


def _write_startup_vbs():
    vbs = startup_vbs()
    dst = os.path.join(APP_DIR, APP_NAME + '.pyw')
    target = dst if os.path.exists(dst) else SELF
    line = 'sh.Run """"%s"" ""%s"" --watch""", 0, False' % (pythonw(), target)
    body = ("' SUTK 存档修改器 - 开机静默启动\n"
            "Set sh = CreateObject(\"WScript.Shell\")\n" + line + "\n")
    try:
        os.makedirs(os.path.dirname(vbs), exist_ok=True)
        _write_gbk(vbs, body)
        return os.path.exists(vbs)
    except Exception as e:
        flog("startup vbs failed: %s" % e)
        return False


def setup(quiet=False, with_startup=False):
    """一键安装：处理存档 + 桌面图标 + 后台热键"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    lines = []

    done, skipped, failed, _il = apply_all()
    lines.append("[1/4] 存档处理   完成 %d / 已是最新 %d / 失败 %d"
                 % (done, skipped, failed))

    sc = make_shortcut()
    lines.append("[2/4] 桌面图标   " + (sc if sc else "创建失败(可直接用 2 启动修改器.bat)"))

    if with_startup:
        ok = _write_startup_vbs()
        lines.append("[3/4] 开机启动   " + ("已开启" if ok else "设置失败"))
    else:
        lines.append("[3/4] 开机启动   未开启(默认不装)")

    pid = start_watcher()
    lines.append("[4/4] 后台热键   " + ("已启动 pid=%s" % pid if pid else "启动失败"))

    msg = ("安装完成\n"
           "------------------------------\n"
           + "\n".join(lines) +
           "\n------------------------------\n"
           "程序目录: %s\n\n"
           "以后每次玩: 双击桌面「SUTK 修改器」\n"
           "游戏里按 Ctrl+Alt+F9 呼出控制台" % APP_DIR)
    log(msg)
    if not quiet:
        popup(msg, title="SUTK 修改器 - 安装完成", flags=MB_OK | MB_ICONINFO)
    return True


def install(quiet=False):
    import winreg
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dst = os.path.join(APP_DIR, APP_NAME + '.pyw')
    if (not _PORTABLE) and os.path.abspath(SELF) != os.path.abspath(dst):
        shutil.copy2(SELF, dst)

    # 控制台 + 命令行启动器
    src_dir = os.path.dirname(SELF)
    for fn in ('SUTK控制台.hta', 'launcher.cmd', '控制台.bat'):
        sp = os.path.join(src_dir, fn)
        if os.path.exists(sp) and os.path.abspath(sp) != os.path.abspath(os.path.join(APP_DIR, fn)):
            shutil.copy2(sp, os.path.join(APP_DIR, fn))
    # 文档 / 辅助脚本一并同步，避免安装版长期停留在旧版
    for fn in ('经验总结.md', '使用说明.md', '安装教程.txt', 'MemScan.py', '诊断.bat'):
        sp = os.path.join(src_dir, fn)
        dp = os.path.join(APP_DIR, fn)
        if not os.path.exists(sp) or os.path.abspath(sp) == os.path.abspath(dp):
            continue
        try:
            if (not os.path.exists(dp)
                    or os.path.getmtime(sp) > os.path.getmtime(dp)):
                shutil.copy2(sp, dp)
        except Exception as e:
            flog("sync %s failed: %s" % (fn, e))
    cmd_path = os.path.join(APP_DIR, 'launcher.cmd')
    if not os.path.exists(cmd_path):
        _write_gbk(cmd_path, '@echo off\n"%s" "%%~dp0%s.pyw" %%*\n'
                   % (python_exe(), APP_NAME))

    # 方式一：启动文件夹 vbs（主用，文件可验证）
    vbs = startup_vbs()
    body = ("' SUTK 存档修改器 - 开机静默启动\n"
            "Set sh = CreateObject(\"WScript.Shell\")\n"
            "sh.Run \"\"\"%s\"\" \"\"%s\"\" --watch\", 0, False\n"
            % (pythonw(), dst))
    ok_file = False
    try:
        os.makedirs(os.path.dirname(vbs), exist_ok=True)
        _write_gbk(vbs, body)
        ok_file = os.path.exists(vbs)
    except Exception as e:
        flog("startup vbs failed: %s" % e)

    # 方式二：注册表 Run 键（备份手段）
    cmd = '"%s" "%s" --watch' % (pythonw(), dst)
    ok_reg = False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, APP_NAME)
            ok_reg = (val == cmd)
    except Exception:
        ok_reg = False

    sc = make_shortcut()
    flog("installed: vbs=%s reg=%s shortcut=%s" % (ok_file, ok_reg, bool(sc)))
    if not ok_file and not ok_reg:
        msg = ("开机启动设置失败。\n\n"
               "请手动把下面这行放进启动文件夹：\n"
               "%s\n\n内容：\n%s" % (vbs, body))
        log(msg)
        if not quiet:
            popup(msg, flags=MB_ICONWARN)
        return False

    msg = ("安装完成。\n\n"
           "程序目录：%s\n"
           "开机启动：%s（每次登录自动后台运行）\n"
           "当前状态：已对存档应用一次修改\n\n"
           "⚠ 后台只负责热键，不会自动改档。\n"
           "   要改档请在控制台按 1 / 4-8，自己选存档。\n"
           "   想让游戏启动时自动改：控制台按 A 开启。\n\n"
           "游戏本体未被改动，双击「卸载.bat」即可干净卸载。"
           % (APP_DIR, "已加入" if ok_file else "已加入(注册表)"))
    log(msg)
    if not quiet:
        popup(msg)
    return True


def uninstall(quiet=False):
    import winreg
    n, lines = restore_all(confirm=True)

    state = []
    vbs = startup_vbs()
    try:
        if os.path.exists(vbs):
            os.remove(vbs)
            state.append("启动项已删除")
        else:
            state.append("启动项不存在")
    except Exception as e:
        state.append("启动项删除失败: %s" % e)

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
        state.append("注册表项已删除")
    except FileNotFoundError:
        pass
    except Exception as e:
        state.append("注册表: %s" % e)

    # 删桌面图标
    for desk in desktop_dirs():
        for nm in SHORTCUT_NAMES:
            q = os.path.join(desk, nm)
            if os.path.exists(q):
                try:
                    os.remove(q)
                    state.append("桌面图标已删除")
                except Exception:
                    pass

    flog("uninstall: restored=%d %s" % (n, " / ".join(state)))
    msg = ("卸载完成。\n\n已还原 %d 个存档：\n%s\n\n%s\n\n"
           "程序目录可直接删除：\n%s"
           % (n, "\n".join(lines) or "  (无)", " / ".join(state), APP_DIR))
    log(msg)
    if not quiet:
        popup(msg)
    return True


# ----------------------------------------------------------------- 配置
CONFIG_PATH = os.path.join(APP_DIR, 'config.json')

# 内置三人编队预设（主将名 = 预设名；来自典型自建将部队配置）
# 内置十支三人编队（来自玩家 AutoSave 编组 1/2 主将部队）
DEFAULT_TEAM_PRESETS = [
    {
        'id': 'huo_piao_lei',
        'name': '霍骠垒',
        'troopKindId': '49_2',
        'generals': [
            '6CD5900E4F37C42335D7F981B59DA06D',
            '41C0A6BC45871BAFDE21B4AE8ABC2B46',
            'D2F74D744AF146645CD692B44A273D83',
        ],
        'staffing': 0,
        'gameTeamId': 1,
    },
    {
        'id': 'wei_xiang_cheng',
        'name': '卫骧城',
        'troopKindId': '38_2',
        'generals': [
            'CA7F1D7B4AC4A6ED7450FF9D268CD804',
            '730821634495A78221B9A6B07262E4CE',
            'A0B9C1E84E602BE52930CAA4AFE5F6B3',
        ],
        'staffing': 0,
        'gameTeamId': 1,
    },
    {
        'id': 'jiang_jun_yue',
        'name': '江骏岳',
        'troopKindId': '59_2',
        'generals': [
            '2DEF536E48FD36C72BFA49875A1DFCE2',
            '358B5B6945D9DE51E43B6D8A32ECBCA7',
            '56E2FC3C4944380267008891DC5D4B92',
        ],
        'staffing': 0,
        'gameTeamId': 1,
    },
    {
        'id': 'han_lan_jing',
        'name': '韩澜靖',
        'troopKindId': '66_3',
        'generals': [
            '9547BA294273067B4675F9A5BB02C5BF',
            '7C30DA8C4308F11DEAD6FE8FBDC38736',
            '16E026D74454F25DE6EE50AF1B774083',
        ],
        'staffing': 0,
        'gameTeamId': 2,
    },
    {
        'id': 'qin_ting_lie',
        'name': '秦霆烈',
        'troopKindId': '41_2',
        'generals': [
            '57DA2E7146AB0E03CE644DBA84BC5C67',
            'E22F020243D5563E834102AA27ADB803',
            '8DEED9344CC360B21F3046B73EAC8572',
        ],
        'staffing': 0,
        'gameTeamId': 2,
    },
    {
        'id': 'duan_jin_bi',
        'name': '段烬壁',
        'troopKindId': '33_2',
        'generals': [
            'E999FE1C42A1FE53DCE154B07352FF1A',
            '5A4B3D96433B662301F581988C4B1E95',
            '2D5490EC44C44DCFFD65629A646C91D7',
        ],
        'staffing': 0,
        'gameTeamId': 2,
    },
    {
        'id': 'shen_yue_chuan',
        'name': '沈岳川',
        'troopKindId': '55_2',
        'generals': [
            'CBCDA3C646BC03EB0948939F19AE4EB7',
            'C0DC6C66474153135CA41C8018F050C4',
            '771E8B884CC72102DA9D31ABE65018BB',
        ],
        'staffing': 0,
        'gameTeamId': 2,
    },
    {
        'id': 'zhao_shuo_chuan',
        'name': '赵朔川',
        'troopKindId': '41_2',
        'generals': [
            'CA4DF5114B33F46B7397DA980518C509',
            'F7A0B9D94259190B605EDC82682D88A4',
            '609EEB434715EFAC62DC66ACBACA2CD1',
        ],
        'staffing': 0,
        'gameTeamId': 2,
    },
    {
        'id': 'zhou_sheng_lei',
        'name': '周晟垒',
        'troopKindId': '45_3',
        'generals': [
            'DF87C0C540D5DB62A4C774B8C7063DA6',
            '2EADA85B43664646618BE5AB7F4BC88A',
            '2A285CCA47ED0B5B037BFDB4F6E4E1A6',
        ],
        'staffing': 0,
        'gameTeamId': 2,
    },
    {
        'id': 'wei_xiao_cheng',
        'name': '卫霄城',
        'troopKindId': '43_3',
        'generals': [
            '58A46E394011E4DE0DB666BE2573F157',
            '685DCD5F4EFA05C4A00D05893C34548D',
            '002DB39B40A41CE8E1CA4389CDE22C84',
        ],
        'staffing': 0,
        'gameTeamId': 2,
    },
]

DEFAULT_CFG = {'scope': 'player', 'sections': 'all', 'hotkey': True,
               'ui': 'bat', 'target': 'all',
               'auto_apply': False,     # 游戏启动时自动改档（默认关）
               'snapshot_game': False,  # 游戏自己存档时本地留底（默认关）
               'saves_dir': '',         # 空=系统默认 ProjectA\Saved\Saves
               'extern_path': '',      # 空=存档目录上一级的 ExternPersonage.sav
               'team_presets': []}     # 空则使用 DEFAULT_TEAM_PRESETS


def default_saves_dir():
    return os.path.join(LOCAL, r'ProjectA\Saved\Saves')


def default_extern_path():
    return os.path.join(LOCAL, r'ProjectA\Saved\ExternPersonage.sav')


def _norm_user_path(raw):
    if raw is None:
        return ''
    s = str(raw).strip()
    if not s:
        return ''
    return os.path.normpath(os.path.expandvars(os.path.expanduser(s)))


def apply_path_cfg(cfg):
    """按 config.json 刷新全局 SAVES_DIR / EXTERN_PATH"""
    global SAVES_DIR, EXTERN_PATH
    custom = _norm_user_path(cfg.get('saves_dir'))
    if custom:
        SAVES_DIR = custom
    else:
        SAVES_DIR = default_saves_dir()
    custom_e = _norm_user_path(cfg.get('extern_path'))
    if custom_e:
        EXTERN_PATH = custom_e
    else:
        EXTERN_PATH = os.path.join(os.path.dirname(SAVES_DIR), 'ExternPersonage.sav')


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    if cfg.get('sections') not in ('all',) and isinstance(cfg.get('sections'), list):
        cfg['sections'] = ','.join(cfg['sections'])
    apply_path_cfg(cfg)
    return cfg


def apply_caps(cfg):
    """把 config 里的 caps / stats 套进来；非法值忽略"""
    st = (cfg or {}).get('stats') or {}
    for k in STAT_KEYS:
        if k not in st:
            continue
        try:
            v = int(st[k])
        except Exception:
            continue
        STATS[k] = max(1, min(STAT_MAX, v))
    c = (cfg or {}).get('caps') or {}
    for k in CAPS:
        if k not in c:
            continue
        try:
            nv, cut = clamp_cap(k, c[k])
            CAPS[k] = nv
            if cut:
                log("  [钳制] %s=%s 超出游戏上限, 已限制为 %s"
                    % (CAP_LABEL.get(k, k), c[k], format(nv, ',')))
        except Exception:
            pass


def save_cfg(cfg):
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        flog("save_cfg failed: %s" % e)



# ----------------------------------------------------------------- 存档编号选择
def _saves_sorted():
    """按修改时间倒序返回 [(mtime, name, size)]，最新的在最前"""
    d = SAVES_DIR
    items = []
    if not os.path.isdir(d):
        return items
    for n in os.listdir(d):
        if not n.lower().endswith('.sav'):
            continue
        p = os.path.join(d, n)
        try:
            st = os.stat(p)
        except OSError:
            continue
        items.append((st.st_mtime, n, st.st_size))
    items.sort(reverse=True)
    return items


def _save_state(p):
    """已修改 / 原档 / 读取失败"""
    try:
        data = json.loads(read_sav(p)['body'].decode('utf-8'))
        pf = [f for f in (data.get('factions') or {}).values() if f.get('bIsPlayerCtrl')]
        if not pf:
            return '无玩家势力'
        money = (pf[0].get('info') or {}).get('money')
        return '已修改' if money == CAPS['money'] else '原档'
    except Exception:
        return '读取失败'


def _dw(text):
    """字符串显示宽度：东亚全角字符算 2"""
    w = 0
    for ch in str(text):
        w += 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
    return w


def _pad(text, width):
    """按显示宽度左对齐补空格，超长则截断"""
    out, w = '', 0
    for ch in str(text):
        cw = 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
        if w + cw > width:
            break
        out += ch
        w += cw
    return out + ' ' * max(0, width - w)


def print_saves():
    """打印带编号的存档列表，返回按编号顺序的文件名"""
    items = _saves_sorted()
    if not items:
        log('存档目录里没有 .sav 文件')
        return []
    log('')
    log('  编号  ' + _pad('存档名', 40) + ' 修改时间   大小   状态')
    log('  ' + '-' * 72)
    for i, (mt, n, sz) in enumerate(items, start=1):
        tag = _save_state(os.path.join(SAVES_DIR, n))
        mark = '  <- 最近游玩' if i == 1 else ''
        log('   [%2d] %s %s  %5.0fK  %s%s'
            % (i, _pad(n, 40),
               time.strftime('%m-%d %H:%M', time.localtime(mt)),
               sz / 1024.0, tag, mark))
    return [n for _, n, _ in items]


def ask_saves(title='选择存档'):
    """打印编号列表并让用户选。返回 (names, is_all)"""
    names = print_saves()
    if not names:
        return [], False
    log('')
    log('  %s：输入编号  1 / 1,3 / 1-3      A=全部     回车=最近游玩      Q=取消' % title)
    try:
        c = input('  选择: ').strip()
    except EOFError:
        return [], False
    low = c.lower()
    if low == 'q':
        return [], False
    if low in ('a', 'all', '*'):
        return names, True
    if not c:
        return [names[0]], False
    idx = set()
    for tok in c.replace('，', ',').split(','):
        tok = tok.strip()
        if '-' in tok:
            a, b = tok.split('-', 1)
            if a.strip().isdigit() and b.strip().isdigit():
                x, y = int(a), int(b)
                if x > y:
                    x, y = y, x
                idx.update(range(x, y + 1))
        elif tok.isdigit():
            idx.add(int(tok))
    picked = [names[i - 1] for i in sorted(idx) if 1 <= i <= len(names)]
    return picked, False


# ----------------------------------------------------------------- 外交控制
ARMISTICE_TICKS = 43800        # 停战时长 ≈ 10 年（实测 12 tick/天 推算）


def _sav_json(sav):
    return json.loads(sav['body'].decode('utf-8'))


def _player_fid(d):
    for k, v in (d.get('factions') or {}).items():
        if v.get('bIsPlayerCtrl'):
            return k
    return None


def _header_tick(sav):
    try:
        h = json.loads(sav['header'].decode('utf-8'))
        return int((h.get('gameTime') or {}).get('tickCount') or 0)
    except Exception:
        return 0


def diplo_table(sav_path):
    """读取存档的外交概况: 玩家势力/君主名/与各势力关系/双方人情
    势力 ID 大小写不统一: 势力表键是 new_6, 关系表里却写成 New_6,
    必须小写归一后再匹配, 否则自建势力的外交表会整个是空的。
    关系条目里后缀 1/2 的字段分属 factionId1/factionId2 两侧
    (favourValue1=1方持有的人情, favourValue2=2方持有的)。
    人情: 帮助/捐赠对方获得, 请求支援等操作时消耗, 上限约 20, 随时间衰减。"""
    sav = read_sav(sav_path)
    d = _sav_json(sav)
    pfid = _player_fid(d)
    if pfid is None:
        return None
    facs = d.get('factions') or {}
    king = {k: ((v.get('info') or {}).get('kingId') or '?') for k, v in facs.items()}
    plow = str(pfid).lower()
    canon = {str(k).lower(): k for k in facs}     # 小写ID -> 势力表真实键
    rels, side = {}, {}
    for r in d.get('factionRelations') or []:
        i = r.get('info') or {}
        a, b = str(i.get('factionId1')), str(i.get('factionId2'))
        if a.lower() == plow:
            rels[canon.get(b.lower(), b)] = r; side[canon.get(b.lower(), b)] = 1
        elif b.lower() == plow:
            rels[canon.get(a.lower(), a)] = r; side[canon.get(a.lower(), a)] = 2
    return dict(sav=sav, d=d, pfid=pfid, king=king, facs=facs, rels=rels,
                canon=canon, side=side)


def _favour_vals(r, side):
    """返回 (我方人情, 对方人情) —— 玩家是 side 侧"""
    try:
        f1 = float(r.get('favourValue1') or 0)
        f2 = float(r.get('favourValue2') or 0)
    except Exception:
        f1 = f2 = 0.0
    return (f1, f2) if side == 1 else (f2, f1)


def diplo_write(tbl, sav_path, changes):
    """把外交改动写回存档。
    changes: [{fid, relation?, friend?, armistice?, favour?, favour_other?}]
    favour = 我方人情(请求支援时消耗的), favour_other = 对方人情"""
    d, rels = tbl['d'], tbl['rels']
    canon = tbl.get('canon') or {}
    side = tbl.get('side') or {}
    tick = _header_tick(tbl['sav'])
    n = 0
    for ch in changes:
        fid = str(ch.get('fid'))
        key = canon.get(fid.lower(), fid)         # 输入大小写归一
        r = rels.get(key)
        if r is None:
            continue
        i = r['info']
        sd = side.get(key, 2)
        rel = ch.get('relation')
        if rel is not None:
            _set(r, 'relationValue', rel)
            if 'relationEventValue' in r:
                r['relationEventValue'] = {}      # 清掉事件修正, 防止被拉回去
        fr = ch.get('friend')
        if fr is True:
            i['isFriend'] = True
            cur = r.get('relationValue')
            try:
                if float(cur) < 100:
                    _set(r, 'relationValue', 100)
            except Exception:
                pass
            if 'relationEventValue' in r:
                r['relationEventValue'] = {}
        elif fr is False:
            i['isFriend'] = False
        am = ch.get('armistice')
        if am is True:
            i['isArmistice'] = True
            i['armisticeTime'] = tick + ARMISTICE_TICKS
        elif am is False:
            i['isArmistice'] = False
        # 人情: 写到对应一侧, 并刷新衰减计时, 避免写入后立即衰减
        for fk, mine in (('favour', True), ('favour_other', False)):
            v = ch.get(fk)
            if v is None:
                continue
            v = max(0, min(100, float(v)))
            vkey = 'favourValue%d' % sd if mine else 'favourValue%d' % (3 - sd)
            tkey = 'favourChangeTick%d' % sd if mine else 'favourChangeTick%d' % (3 - sd)
            if vkey in r:
                _set(r, vkey, v)
                if tkey in r:
                    r[tkey] = tick                 # 重置衰减计时
        n += 1

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = backup_path(sav_path)
    if not os.path.exists(bak):
        shutil.copy2(sav_path, bak)
    body = json.dumps(d, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')
    blob = build_sav(tbl['sav'], body)
    tmp = sav_path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(blob)
    os.replace(tmp, sav_path)
    return n


def _diplo_print(tbl):
    facs, king, rels = tbl['facs'], tbl['king'], tbl['rels']
    side = tbl.get('side') or {}
    rows = []
    for fid, r in rels.items():
        i = r['info']
        mine, other = _favour_vals(r, side.get(fid, 2))
        rows.append((float(r.get('relationValue') or 0), fid, king.get(fid, '?'),
                     facs.get(fid, {}).get('bDestroyed', False),
                     i.get('isFriend'), i.get('isArmistice'), mine, other))
    rows.sort(reverse=True)
    print('\n  %-5s %-12s %-12s %-5s %-5s %-5s %-8s %-8s'
          % ('关系', '势力ID', '君主', '已灭', '同盟', '停战', '人情(我)', '人情(他)'))
    for rel, fid, k, dead, fr, am, mine, other in rows:
        print('  %-5.0f %-12s %-12s %-5s %-5s %-5s %-8s %-8s'
              % (rel, fid, str(k)[:10], '是' if dead else '-',
                 '√' if fr else '-', '√' if am else '-',
                 '%g' % mine if mine else '-', '%g' % other if other else '-'))
    return [r[1] for r in rows]      # 顺序的 fid 列表


def diplo_wizard(only=None):
    name = only or newest_save()
    if not name:
        log('存档目录里没有 .sav'); return
    sav_path = os.path.join(SAVES_DIR, name)
    if not os.path.exists(sav_path):
        log('找不到存档: ' + name); return
    tbl = diplo_table(sav_path)
    if tbl is None:
        log('这个档里找不到玩家势力'); return

    log('目标存档: %s   玩家势力: %s (%s)' % (name, tbl['pfid'],
        tbl['king'].get(tbl['pfid'], '?')))
    if game_running():
        log('⚠ 游戏正在运行: 改动在你【读档】时才生效; 若再存档会被覆盖, 需重新执行')

    while True:
        order = _diplo_print(tbl)
        log('\n  输入势力ID 操作单个 | A=关系全拉满 B=全部同盟 C=全部停战')
        log('  D=解除所有同盟 E=解除所有停战  Q=退出')
        log('  F=我方人情全拉满(20, 请求支援用)')
        c = input('选择: ').strip()
        if not c:
            continue
        low = c.lower()
        try:
            if low == 'q':
                return
            elif low == 'a':
                n = diplo_write(tbl, sav_path,
                                [{'fid': f, 'relation': 100} for f in order])
                log('已把 %d 个势力关系设为 100' % n)
            elif low == 'f':
                n = diplo_write(tbl, sav_path,
                                [{'fid': f, 'favour': 20} for f in order])
                log('已把对 %d 个势力的我方人情设为 20' % n)
                log('(人情会随时间自然衰减, 是游戏机制)')
            elif low == 'b':
                n = diplo_write(tbl, sav_path,
                                [{'fid': f, 'friend': True} for f in order])
                log('已与 %d 个势力结盟(关系同步拉满)' % n)
            elif low == 'c':
                n = diplo_write(tbl, sav_path,
                                [{'fid': f, 'armistice': True} for f in order])
                log('已与 %d 个势力停战(约10年)' % n)
            elif low == 'd':
                n = diplo_write(tbl, sav_path,
                                [{'fid': f, 'friend': False} for f in order])
                log('已解除 %d 个同盟' % n)
            elif low == 'e':
                n = diplo_write(tbl, sav_path,
                                [{'fid': f, 'armistice': False} for f in order])
                log('已解除 %d 个停战' % n)
            else:
                canon = tbl.get('canon') or {}
                fid = canon.get(c.lower(), c)
                if fid not in tbl['rels']:
                    log('没有这个势力ID: ' + c); continue
                log('\n  对 %s (%s):' % (fid, tbl['king'].get(fid, '?')))
                log('  1=设关系  2=结盟  3=解除同盟  4=停战  5=取消停战')
                log('  6=设我方人情(请求支援用)  7=设对方人情  0=返回')
                op = input('选择: ').strip()
                ch = None
                if op == '1':
                    v = input('  关系值 (-100~100): ').strip()
                    try:
                        ch = {'fid': fid, 'relation': max(-100, min(100, int(float(v))))}
                    except Exception:
                        log('  不是数字')
                elif op == '6':
                    v = input('  我方人情值 (0~100, 游戏内上限约20): ').strip()
                    try:
                        ch = {'fid': fid, 'favour': max(0, min(100, float(v)))}
                    except Exception:
                        log('  不是数字')
                elif op == '7':
                    v = input('  对方人情值 (0~100): ').strip()
                    try:
                        ch = {'fid': fid, 'favour_other': max(0, min(100, float(v)))}
                    except Exception:
                        log('  不是数字')
                elif op == '2':
                    ch = {'fid': fid, 'friend': True}
                elif op == '3':
                    ch = {'fid': fid, 'friend': False}
                elif op == '4':
                    ch = {'fid': fid, 'armistice': True}
                elif op == '5':
                    ch = {'fid': fid, 'armistice': False}
                if ch:
                    diplo_write(tbl, sav_path, [ch])
                    log('  已写入')
            tbl = diplo_table(sav_path)     # 重新读, 刷新显示
        except Exception as e:
            log('出错: %s' % e)


def diplo_cli(only=None, set_rel=None, friend=None, armistice=None, favour=None):
    """非交互: --diplo-set <fid> <val> / --diplo-friend <fid|all> on|off /
    --diplo-armistice <fid|all> on|off / --diplo-favour <fid|all> <val>"""
    name = only or newest_save()
    if not name:
        log('没有存档'); return
    sav_path = os.path.join(SAVES_DIR, name)
    tbl = diplo_table(sav_path)
    if tbl is None:
        log('找不到玩家势力'); return
    fids = list(tbl['rels'].keys())
    changes = []
    if set_rel:
        fid, val = set_rel[0], set_rel[1]
        changes.append({'fid': fid, 'relation': max(-100, min(100, int(float(val))))})
    if friend:
        want = str(friend[1]).lower() in ('on', '1', 'true', '是')
        targets = fids if friend[0].lower() == 'all' else [friend[0]]
        changes += [{'fid': f, 'friend': want} for f in targets]
    if armistice:
        want = str(armistice[1]).lower() in ('on', '1', 'true', '是')
        targets = fids if armistice[0].lower() == 'all' else [armistice[0]]
        changes += [{'fid': f, 'armistice': want} for f in targets]
    if favour:
        val = max(0, min(100, float(favour[1])))
        targets = fids if favour[0].lower() == 'all' else [favour[0]]
        changes += [{'fid': f, 'favour': val} for f in targets]
    if not changes:
        log('目标: %s (玩家势力 %s)' % (name, tbl['pfid']))
        _diplo_print(tbl)
        return
    n = diplo_write(tbl, sav_path, changes)
    log('已写入 %d 条外交改动 → %s' % (n, name))
    if game_running():
        log('⚠ 游戏运行中: 读档后生效; 若再存档会被覆盖')


# ----------------------------------------------------------------- 热键 / 控制台
def console_path():
    """优先用安装目录里的控制台"""
    for d in (APP_DIR, os.path.dirname(SELF)):
        p = os.path.join(d, 'SUTK控制台.hta')
        if os.path.exists(p):
            return p
    return None


def watcher_alive(pid):
    """检查 pid 是否还活着"""
    if not pid:
        return False
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
        k32.CloseHandle(ctypes.c_void_p(h))
        return code.value == 259        # STILL_ACTIVE
    except Exception:
        return False


def run_all():
    """日常入口：拉起后台 + 打开控制台，每一步都留痕，失败会弹窗说明"""
    flog("=== run_all begin ===")
    try:
        # 已有实例就不再起第二个（避免热键互抢）
        running = [p for p in _list_watcher_pids()]
        if running:
            flog("watcher already alive: %s" % running)
            pid = running[0]
        else:
            pid = start_watcher()
            flog("run_all: start_watcher -> %s" % pid)
            time.sleep(1.6)
            if not watcher_alive(pid):
                flog("run_all: watcher died right after start")
        # 优先在当前窗口里直接跑控制台：双击图标后窗口不会闪一下就消失
        bat = os.path.join(APP_DIR, '控制台.bat')
        ok = False
        if os.path.exists(bat):
            try:
                flog("run_all: console inline")
                rc = os.system('"%s"' % bat)
                ok = (rc == 0)
                flog("run_all: inline rc=%s" % rc)
            except Exception as e:
                flog("run_all: inline failed: %s" % e)
        if not ok:
            ok = launch_console()
            flog("run_all: launch_console -> %s" % ok)
        if not ok:
            popup("控制台没能打开。\n\n后台热键已启动（Ctrl+Alt+F9），\n"
                  "你仍可以在游戏里按热键呼出。\n\n"
                  "若热键也没反应，请双击：\n" + os.path.join(APP_DIR, '控制台.bat'),
                  title="SUTK 修改器", flags=MB_OK | MB_ICONWARN)
        return True
    except Exception as e:
        import traceback
        flog("run_all FAILED: %s\n%s" % (e, traceback.format_exc()))
        popup("启动失败：%s\n\n详细信息已写入：\n%s"
              % (e, os.path.join(APP_DIR, 'mod.log')),
              title="SUTK 修改器 · 启动失败", flags=MB_OK | MB_ICONWARN)
        return False


def _list_watcher_pids():
    """列出正在跑 --watch 的 python 进程 pid（用 WMI，失败返回空）"""
    out = []
    try:
        import subprocess as sp
        si = sp.STARTUPINFO()
        si.dwFlags |= 1
        ps = ('Get-CimInstance Win32_Process -Filter "Name=\'pythonw.exe\' or '
              'Name=\'python.exe\'" | Where-Object { $_.CommandLine -like '
              "'*SUTKMod*--watch*' } | Select-Object -ExpandProperty ProcessId")
        r = sp.run(['powershell', '-NoProfile', '-Command', ps],
                   capture_output=True, text=True, startupinfo=si,
                   creationflags=0x08000000, timeout=12)
        for line in (r.stdout or '').splitlines():
            line = line.strip()
            if line.isdigit():
                out.append(int(line))
    except Exception as e:
        flog("list watcher failed: %s" % e)
    return out


def diagnose():
    """一键自检：把每一项写进日志并打印，供排查"""
    lines = []

    def add(k, v):
        lines.append('  %-26s %s' % (k, v))
        flog("DIAG %s = %s" % (k, v))

    add('程序目录', APP_DIR)
    add('存档目录', SAVES_DIR)
    add('python.exe', python_exe())
    add('pythonw.exe', pythonw())
    add('SUTKMod.pyw', SELF)
    add('控制台.bat', os.path.join(APP_DIR, '控制台.bat'))
    add('控制台存在', os.path.exists(os.path.join(APP_DIR, '控制台.bat')))
    add('桌面图标', ' / '.join(p for p in
                              [os.path.join(d, 'SUTK 修改器.bat')
                               for d in desktop_dirs()]
                              if os.path.exists(p)) or '未找到')
    pids = _list_watcher_pids()
    add('后台进程', pids or '未运行')
    add('热键占用', '见上方后台进程')
    add('存档数量', len([n for n in os.listdir(SAVES_DIR)
                        if n.lower().endswith('.sav')]) if os.path.isdir(SAVES_DIR) else 0)
    for l in lines:
        log(l)
    return lines


def launch_console(force_bat=False):
    """打开控制台。三重回退：startfile（等价双击）→ cmd start → 当前窗口内联运行"""
    bat = os.path.join(APP_DIR, '控制台.bat')
    if not os.path.exists(bat):
        flog("console not found in " + APP_DIR)
        popup("找不到控制台文件，请重新运行安装.bat\n目录: " + APP_DIR)
        return False
    # ① os.startfile：和资源管理器里双击完全一致，最不容易被终端环境干扰
    try:
        os.startfile(bat)
        flog("console launched (startfile)")
        return True
    except Exception as e:
        flog("startfile failed: %s" % e)
    # ② 显式 cmd /c start
    try:
        subprocess.Popen('cmd /c start "SUTK" "%s"' % bat, shell=True,
                         creationflags=0x00000008)
        flog("console launched (cmd start)")
        return True
    except Exception as e:
        flog("cmd start failed: %s" % e)
    # ③ 实在打不开新窗口，就在当前窗口里跑（至少用户能看到界面）
    try:
        flog("console fallback: inline")
        os.system('"%s"' % bat)
        return True
    except Exception as e:
        flog("inline console failed: %s" % e)
    popup("控制台打不开。\n请直接双击这个文件：\n" + bat)
    return False


# (修饰键, 虚拟键, 名称)  修饰: 1=Alt 2=Ctrl 4=Shift
HOTKEYS = [
    (2 | 1, 0x78, "Ctrl+Alt+F9"),
    (2 | 1, 0x79, "Ctrl+Alt+F10"),
    (2 | 4, 0x78, "Ctrl+Shift+F9"),
    (2 | 1, 0x7A, "Ctrl+Alt+F11"),
    (2 | 1, 0x53, "Ctrl+Alt+S"),
]


def _hotkey_loop():
    """注册多组全局热键, 任意一组都能呼出控制台"""
    import ctypes.wintypes as wt
    u = ctypes.windll.user32
    ok = []
    for i, (mods, vk, name) in enumerate(HOTKEYS, start=1):
        if u.RegisterHotKey(None, i, mods, vk):
            ok.append((i, name))
    if not ok:
        flog("hotkey: ALL register FAILED")
        return
    flog("hotkey registered: " + ", ".join(n for _, n in ok))
    msg = wt.MSG()
    last = 0.0
    while True:
        r = u.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if r == 0 or r == -1:
            flog("hotkey loop exited, GetMessageW=%d" % r)
            return
        if msg.message == 0x0312:      # WM_HOTKEY
            now2 = time.time()
            if now2 - last < 2.0:      # 防连按, 2 秒内只响应一次
                continue
            last = now2
            flog("hotkey fired id=%d, launching console" % msg.wParam)
            try:
                launch_console()
            except Exception as e:
                flog("launch_console error: %s" % e)


def start_hotkey():
    try:
        threading.Thread(target=_hotkey_loop, daemon=True).start()
    except Exception as e:
        flog("hotkey thread failed: %s" % e)


# ----------------------------------------------------------------- 常驻
_SINGLETON_HANDLE = None


def _acquire_singleton():
    """全局互斥：只允许一个 --watch 实例，否则热键互抢"""
    global _SINGLETON_HANDLE
    try:
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = ctypes.c_void_p
        h = k32.CreateMutexW(None, False, 'Global\\SUTKMod_Watcher_9F2A')
        err = ctypes.get_last_error()
        if err == 183:          # ERROR_ALREADY_EXISTS
            return False
        _SINGLETON_HANDLE = h
        return True
    except Exception as e:
        flog("singleton check failed: %s" % e)
        return True             # 拿不到锁也放行，别把用户堵死


def watch():
    # 单实例（64 位句柄必须用 c_void_p，错误码必须从 use_last_error 取）
    globals()['_WATCH_MUTEX'] = None
    try:
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        h = k32.CreateMutexW(None, False, 'Global\\SUTKModWatcher')
        if ctypes.get_last_error() == 183:      # ERROR_ALREADY_EXISTS
            log('已有实例在运行，本实例退出')
            flog('watcher skip: another instance is running')
            return
        globals()['_WATCH_MUTEX'] = h            # 保持句柄引用，防被回收
    except Exception as e:
        flog('mutex failed: %s' % e)

    cfg = load_cfg()
    scope = cfg.get('scope') or 'player'
    secs = parse_sections(cfg.get('sections'))
    if cfg.get('hotkey', True):
        start_hotkey()

    log("SUTK 修改器已启动，等待游戏...")
    flog("watcher start, scope=%s sections=%s saves=%s"
         % (scope, ','.join(sorted(secs)), SAVES_DIR))
    try:
        _watch_loop(scope, secs)
    except BaseException as e:
        import traceback
        flog("watcher CRASHED: %r\n%s" % (e, traceback.format_exc()))
        raise


def _watch_loop(scope, secs):
    running = False
    suppressed = False          # 用户本局选了"否", 退出时不再补打
    last_scan = 0.0
    known_saves = set(os.listdir(SAVES_DIR)) if os.path.isdir(SAVES_DIR) else set()
    # 记录见过的存档时间戳：游戏自己存档时也留一份本地副本（只读复制，绝不改档）
    seen_mtime = {}
    if os.path.isdir(SAVES_DIR):
        for n in os.listdir(SAVES_DIR):
            if n.lower().endswith('.sav'):
                try:
                    seen_mtime[n] = os.path.getmtime(os.path.join(SAVES_DIR, n))
                except Exception:
                    pass
    missing = {}                 # 连续几次看不到 -> 认定在游戏里被删了
    while True:
        try:
            if os.path.isdir(SAVES_DIR):
                names_now = {n for n in os.listdir(SAVES_DIR)
                             if n.lower().endswith('.sav')}
                # a) 游戏自己存档：默认不留底，避免本地越堆越多
                if load_cfg().get('snapshot_game', False):
                    for n in names_now:
                        fp = os.path.join(SAVES_DIR, n)
                        try:
                            mt = os.path.getmtime(fp)
                        except Exception:
                            continue
                        if seen_mtime.get(n) != mt and (time.time() - mt) > 3:
                            seen_mtime[n] = mt
                            snapshot_save(fp, 'game')
                else:
                    for n in names_now:
                        try:
                            seen_mtime[n] = os.path.getmtime(
                                os.path.join(SAVES_DIR, n))
                        except Exception:
                            pass
                # b) 游戏里删档 -> 本地副本跟着移进回收站
                for n in list(missing):
                    if n in names_now:
                        missing.pop(n, None)
                for n in (known_saves - names_now):
                    missing[n] = missing.get(n, 0) + 1
                    if missing[n] >= REAP_STRIKES:
                        mv = reap_target(n, with_backup=False)
                        flog('save removed in game: %s -> %d local copies to trash'
                             % (n, mv))
                        if mv:
                            log('  [i] 存档「%s」已在游戏里删除，本地 %d 份历史副本'
                                '移入回收站（原始备份保留）' % (n, mv))
                            flog('   .orig 保留，如需一并清理请用 M→8')
                        known_saves.discard(n)
                        missing.pop(n, None)
                known_saves |= names_now
                purge_trash()
        except Exception as e:
            flog('watch snapshot error: %s' % e)
        now = game_running()
        if now and not running:
            running = True
            suppressed = False
            cfg = load_cfg()
            scope = cfg.get('scope') or 'player'
            secs = parse_sections(cfg.get('sections'))
            auto = bool(cfg.get('auto_apply', False))
            if auto:
                log("检测到游戏启动，按配置自动应用修改...")
                flog("game detected, auto_apply=on")
                # 自动模式只处理"最近 10 分钟内游戏写过"的档，不再全量扫
                done, skipped, failed, lines = apply_all(
                    scope=scope, secs=secs, min_age=3, recent_secs=600)
                log("\n".join(lines))
                flog("apply result: done=%d skipped=%d failed=%d"
                     % (done, skipped, failed))
                for l in lines:
                    flog("   " + l)
                if done and not NOGUI:
                    popup("已自动修改 %d 个最近存档。\n\n"
                          "改的是存档文件，需要重新读档才生效。" % done,
                          title="SUTK · 自动修改", flags=MB_OK | MB_ICONINFO)
            else:
                log("检测到游戏启动（自动修改已关闭，不会动任何存档）")
                log("  要改档请在控制台按 1 / 5-8，手动选择存档")
                flog("game detected, auto_apply=off -> 不改档")
        elif now and running:
            # 游戏运行中巡检：仅在 auto_apply 开启时执行
            cfg2 = load_cfg()
            if not cfg2.get('auto_apply', False):
                time.sleep(2.0)
                continue
            if not suppressed and time.time() - last_scan > 5:
                last_scan = time.time()
                try:
                    sc2 = cfg2.get('scope') or 'player'
                    se2 = parse_sections(cfg2.get('sections'))
                    # target=current: 只处理最近 5 分钟内游戏写过的档(即当前在玩的)
                    rec = 300 if cfg2.get('target') == 'current' else None
                    d2, s2, f2, l2 = apply_all(scope=sc2, secs=se2, min_age=3,
                                               recent_secs=rec)
                    if d2:
                        flog("live scan: patched %d save(s)" % d2)
                        for l in l2:
                            if '[完成]' in l:
                                flog("   " + l)
                        # 新存档(之前没见过) -> 提示用户去重新读档
                        names_now = {n for n in os.listdir(SAVES_DIR)
                                     if n.lower().endswith('.sav')}
                        fresh = names_now - known_saves
                        known_saves.update(fresh)
                        if fresh and not NOGUI:
                            flog("new save(s) detected: %s" % ', '.join(sorted(fresh)))
                            t = popup(
                                "检测到新存档并已自动修改：\n\n"
                                + "\n".join("  " + x for x in sorted(fresh)) + "\n\n"
                                "金钱 %s / 兵役 %s / 粮食 %s\n"
                                "科技全满 / 可供给 %s / 武将技巧 %d\n\n"
                                "⚠ 修改写在存档文件里，当前这局内存中的数值不会变。\n"
                                "需要「退出到主菜单 → 重新载入该存档」才生效。"
                                % ("{:,}".format(CAPS['money']),
                                   "{:,}".format(CAPS['conscription']),
                                   "{:,}".format(CAPS['food']),
                                   "{:,}".format(CAPS['supply']), CAPS['tactical']),
                                title="SUTK · 新存档已修改", flags=MB_OK | MB_ICONINFO)
                except Exception as e:
                    flog("live scan error: %s" % e)
        elif not now and running:
            running = False
            log("游戏已退出，等待下次启动...")
            if not suppressed and load_cfg().get('auto_apply', False):
                time.sleep(8.0)      # 等游戏把手上的存档写完
                try:
                    c2 = load_cfg()
                    d2, s2, f2, _l = apply_all(scope=c2.get('scope') or 'player',
                                               secs=parse_sections(c2.get('sections')))
                    flog("exit re-apply: done=%d skipped=%d failed=%d" % (d2, s2, f2))
                except Exception as e:
                    flog("exit re-apply failed: %s" % e)
        time.sleep(2.0)


# ----------------------------------------------------------------- 入口
def _argval(name, default=None):
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a.lower() == name and i + 1 < len(args):
            return args[i + 1]
    for a in args:
        if a.lower().startswith(name + '='):
            return a.split('=', 1)[1]
    return default


def main():
    global NOGUI, RESULT_FILE
    args = [a.lower() for a in sys.argv[1:]]
    if '--nogui' in args:
        NOGUI = True
    try:
        migrate_old_snapshots()
    except Exception:
        pass
    try:
        reap_orphans()          # 上次运行时删掉的存档，本地副本一并清走
    except Exception:
        pass
    rf = _argval('--result-file')
    if rf:
        RESULT_FILE = rf
        try:
            open(rf, 'w', encoding='utf-8').close()
        except Exception:
            pass

    scope = _argval('--scope', 'player')
    _sec_arg = _argval('--sections')          # 未指定 -> 用配置里的
    secs = parse_sections(_sec_arg)
    if secs is None:
        secs = parse_sections(load_cfg().get('sections')) or set(SECTIONS_ALL)

    # 自定义目标数值: --money 5000000 --food 20000000 ...
    over = {}
    for k in CAPS:
        v = _argval('--' + k)
        if v is not None:
            try:
                nv, cut = clamp_cap(k, float(v))
                over[k] = nv
                if cut:
                    log("  [钳制] --%s %s 超出游戏上限, 用 %s"
                        % (k, v, format(nv, ',')))
            except Exception:
                log("  [忽略] --%s %s 不是数字" % (k, v))
    if over:
        cfgv = load_cfg()
        cfgv.setdefault('caps', {}).update(over)
        save_cfg(cfgv)
        apply_caps(cfgv)
        log("数值已设置: " + ", ".join("%s=%s" % (CAP_LABEL[k], format(v, ','))
                                      for k, v in over.items()))
    apply_caps(load_cfg())

    if '--run' in args:
        run_all()
        return
    if '--setup' in args:
        setup(with_startup=('--with-startup' in args)); return
    if '--install' in args:
        install(); return
    if '--uninstall' in args:
        uninstall(); return
    def _after(flag, n):
        argv = sys.argv[1:]
        for i, a in enumerate(argv):
            if a.lower() == flag:
                return [argv[i + 1 + k] for k in range(n) if i + 1 + k < len(argv)]
        return []

    _only = _argval('--only')
    if '--diplo' in args:
        diplo_wizard(only=_after('--diplo', 1) or _only); return
    ds = _after('--diplo-set', 2)
    df = _after('--diplo-friend', 2)
    da = _after('--diplo-armistice', 2)
    dv = _after('--diplo-favour', 2)
    if ds or df or da or dv:
        diplo_cli(_only,
                  set_rel=tuple(ds) if len(ds) == 2 else None,
                  friend=tuple(df) if df else None,
                  armistice=tuple(da) if da else None,
                  favour=tuple(dv) if len(dv) == 2 else None)
        return
    if '--memscan' in args:
        rest = [x for x in sys.argv[1:] if x.lower() != '--memscan']
        mp = os.path.join(os.path.dirname(SELF), 'MemScan.py')
        if not os.path.exists(mp):
            log("找不到 MemScan.py，请重新安装")
            return
        log("=== 内存扫描（需要读写游戏进程，权限不足请用管理员运行）===")
        subprocess.call([sys.executable, mp] + rest)
        return
    if '--console' in args:
        launch_console(); return
    if '--shortcut' in args:
        pth = make_shortcut()
        log("桌面入口: %s" % (pth or "创建失败")); return
    if '--get-config' in args:
        cfg = load_cfg()
        log("scope=%s" % cfg.get('scope', 'player'))
        log("sections=%s" % cfg.get('sections', 'all'))
        log("hotkey=%s" % cfg.get('hotkey', True))
        return
    if '--set-config' in args:
        cfg = load_cfg()
        cfg['scope'] = scope
        cfg['sections'] = ('all' if set(secs) == set(SECTIONS_ALL)
                           else ','.join(x for x in SECTIONS_ALL if x in secs))
        save_cfg(cfg)
        log("已保存配置: 范围=%s 模块=%s" % (SCOPE_NAME.get(scope, scope), cfg['sections']))
        return
    tgt = _argval('--target')
    if tgt in ('all', 'current'):
        cfgt = load_cfg(); cfgt['target'] = tgt; save_cfg(cfgt)
        log("自动修改范围已设为: %s" % ('全部存档' if tgt == 'all' else '仅最近游玩的存档'))

    only = _argval('--only')
    if '--current' in args:
        only = newest_save()
        log("目标存档(最近修改): %s" % only)
    if '--list' in args:
        print_saves()
        return

    if '--pick-save' in args:
        names, is_all = ask_saves('撤销还原' if '--restore' in args else '应用到哪个存档')
        if not names:
            log('  已取消，未改动任何存档')
            return
        if '--restore' in args:
            tot = 0
            for nm in names:
                n1, lg = restore_all(only=nm)
                tot += n1
                for l in lg:
                    log('   ' + l)
            log('')
            log('已还原 %d 个存档' % tot)
            return
        tot_d = tot_s = tot_f = 0
        for nm in names:
            d1, s1, f1, l1 = apply_all(scope=scope, secs=secs, only=nm)
            tot_d += d1
            tot_s += s1
            tot_f += f1
            for l in l1:
                log(l)
        log('')
        log('模块：%s' % sections_label(secs))
        log('完成 %d / 已是最新 %d / 失败 %d' % (tot_d, tot_s, tot_f))
        return

    if '--apply' in args:
        done, skipped, failed, lines = apply_all(scope=scope, secs=secs, only=only)
        log("范围=%s 模块=%s" % (SCOPE_NAME.get(scope, scope), sections_label(secs)))
        log("完成 %d / 已是最新 %d / 失败 %d" % (done, skipped, failed))
        log("\n".join(lines)); return
    if '--restore' in args:
        n, lines = restore_all(only=only)
        log("已还原 %d 个存档" % n); log("\n".join(lines)); return
    if '--pick' in args:
        pick_sections(); return
    if '--custom' in args:
        custom_caps(); return
    if '--custom-stats' in args:
        custom_stats(); return
    if '--edit-general' in args or '--generals' in args:
        edit_general(only=_argval('--only')); return
    if '--set-auto' in args:
        v = (_argval('--set-auto') or '').lower()
        on = v in ('on', '1', 'true', 'yes')
        c = load_cfg(); c['auto_apply'] = on; save_cfg(c)
        log('自动修改已%s' % ('开启（游戏启动时自动改档）' if on else '关闭（只保留热键，改档全靠手动）'))
        return
    if '--set-snap' in args:
        v = (_argval('--set-snap') or '').lower()
        on = v in ('on', '1', 'true', 'yes')
        c = load_cfg(); c['snapshot_game'] = on; save_cfg(c)
        log('游戏自己存档时本地留底：%s'
            % ('开（每次自动存档都存一份，占空间）' if on
               else '关（默认，只在工具改档前留底）'))
        return
    if '--cleanup' in args:
        cleanup_ui(); return
    if '--audit' in args:
        e, w = audit_save(only=_argval('--only'))
        return
    if '--diagnose' in args:
        diagnose(); return
    if '--cities' in args or '--map' in args:
        map_report(only=_argval('--only')); return
    if '--history' in args:
        show_history(only=_argval('--only')); return
    if '--undo-transfer' in args:
        undo_transfer(only=_argval('--only')); return
    if '--health' in args:
        check_save_health(only=_argval('--only')); return
    if '--repair-annex' in args:
        repair_annex(only=_argval('--only'), src=_argval('--from')); return
    if '--transfer' in args:
        transfer_ui(only=_argval('--only')); return
    if '--transfer-city' in args:
        transfer_cli(only=_argval('--only'), city_arg=_argval('--transfer-city'),
                     to=_argval('--to'),
                     move_officers=('--move-officers' in args))
        return
    if '--check-map' in args:
        name = _argval('--only') or newest_save()
        p = name if os.path.isabs(name) else os.path.join(SAVES_DIR, name)
        d = _sav_json(read_sav(p))
        probs = check_map(d)
        log('  %s: %s' % (os.path.basename(p),
                          '✓ 一致' if not probs else '%d 项问题' % len(probs)))
        for x in probs:
            log('     ' + x)
        return
    if '--find-custom' in args:
        find_custom(only=_argval('--only')); return
    if '--extern' in args:
        list_extern(); return
    if '--edit-extern' in args:
        edit_extern(); return
    if '--report' in args:
        report(); return
    watch()


def pick_sections():
    """交互式勾选要修改的项目"""
    cfg = load_cfg()
    cur = parse_sections(cfg.get('sections')) or set(SECTIONS_ALL)
    while True:
        log("")
        log("  选择要修改的项目（多选，互不影响）")
        log("  ────────────────────────────────────────")
        for i, k in enumerate(SECTIONS_ALL, start=1):
            mark = "[√]" if k in cur else "[ ]"
            log("   %d %s %-12s %s" % (i, mark, SECTIONS_NAME[k], SECTIONS_TIP[k]))
        log("  ────────────────────────────────────────")
        log("  输入编号切换勾选（空格分隔可多个）｜A=全选  N=全不选  Q=完成并退出")
        try:
            c = input("  > ").strip()
        except EOFError:
            c = 'q'
        low = c.lower()
        if low in ('q', ''):
            break
        if low == 'a':
            cur = set(SECTIONS_ALL)
            continue
        if low == 'n':
            cur = set()
            continue
        for tok in c.replace(',', ' ').split():
            if tok.isdigit() and 1 <= int(tok) <= len(SECTIONS_ALL):
                k = SECTIONS_ALL[int(tok) - 1]
                if k in cur:
                    cur.discard(k)
                else:
                    cur.add(k)
    cfg['sections'] = ('all' if cur == set(SECTIONS_ALL)
                       else ','.join(x for x in SECTIONS_ALL if x in cur))
    save_cfg(cfg)
    log("")
    log("已保存勾选: " + sections_label(cur))
    if not cur:
        log("注意：一个都没勾，应用修改时不会改动任何东西")
        return
    try:
        ans = input("现在就对全部存档应用吗？[Y/n]: ").strip().lower()
    except EOFError:
        ans = 'y'
    if ans in ('', 'y', 'yes'):
        done, sk, fa, lines = apply_all(secs=cur)
        log("\n".join(lines))
        log("完成 %d / 已是最新 %d / 失败 %d" % (done, sk, fa))


# ----------------------------------------------------------------- 自建武将模板
def read_extern():
    """读 ExternPersonage.sav（UTF-16 JSON）。返回 (dict, 原始文本)"""
    if not os.path.exists(EXTERN_PATH):
        return None, None
    raw = open(EXTERN_PATH, 'rb').read()
    txt = raw.decode('utf-16')
    return json.loads(txt), txt


def write_extern(data):
    """写回 ExternPersonage.sav：先备份，再按 UTF-16(带BOM) + 制表符缩进写"""
    if os.path.exists(EXTERN_PATH):
        bak = EXTERN_PATH + '.bak'
        if not os.path.exists(bak):
            shutil.copy2(EXTERN_PATH, bak)
    txt = json.dumps(data, ensure_ascii=False, indent='\t').replace('\n', '\r\n')
    with open(EXTERN_PATH, 'wb') as f:
        f.write(txt.encode('utf-16'))
    # 回读校验
    back, _ = read_extern()
    return back is not None


def _extern_rows(d):
    """[(guid, info_dict, kind)]  kind: new=自建  mod=对原版武将的修改"""
    rows = []
    for gid, v in (d.get('newInfos') or {}).items():
        rows.append((gid, v, 'new'))
    for gid, v in (d.get('modifyInfos') or {}).items():
        rows.append((gid, v, 'mod'))
    return rows


def _extern_name(v):
    sn = v.get('surname') or ''
    nm = v.get('name') or ''
    name = (str(sn) + str(nm)).strip()
    return name or '(无名)'


def list_extern():
    """列出编辑器的自建武将模板"""
    d, _ = read_extern()
    if d is None:
        log('没找到 ExternPersonage.sav：%s' % EXTERN_PATH)
        return None
    rows = _extern_rows(d)
    log('')
    log('  自建武将模板: %s' % EXTERN_PATH)
    log('  新武将 %d 个 / 原版武将改造 %d 个'
        % (len(d.get('newInfos') or {}), len(d.get('modifyInfos') or {})))
    log('')
    log('  编号  类型  姓名            统率 武力 敏捷 智力 政治 魅力  战法  GUID')
    log('  ' + '-' * 76)
    for i, (gid, v, kind) in enumerate(rows, start=1):
        vals = []
        for k in STAT_KEYS:
            x = v.get(k)
            vals.append('   -' if x is None else '%4d' % int(x))
        log('   [%2d] %s %s %s  %3s   %s'
            % (i, '自建' if kind == 'new' else '改造',
               _pad(_extern_name(v), 14), ' '.join(vals),
               v.get('tactical', '-'), gid[:8] + '...'))
    return rows


def edit_extern():
    """按编号修改自建武将模板的六维（下次新建战役生效）"""
    while True:
        rows = list_extern()
        if not rows:
            return
        log('')
        log('  输入编号 = 改这个武将      Q = 退出')
        log('  改的是模板文件，只影响"以后新建的战役"；已开局的老存档不会被改')
        try:
            c = input('  选择: ').strip()
        except EOFError:
            return
        if c.lower() == 'q' or c == '':
            return
        if not c.isdigit() or not (1 <= int(c) <= len(rows)):
            log('  无效编号')
            continue
        gid, v, kind = rows[int(c) - 1]
        log('')
        log('  正在改: %s  (%s)' % (_extern_name(v), gid))
        log('  当前: %s' % '  '.join('%s=%s' % (STAT_LABEL[k], v.get(k, '-'))
                                    for k in STAT_KEYS))
        log('  直接回车 = 该项不改')
        changed = 0
        for k in STAT_KEYS:
            try:
                raw = input('    %-6s [%s]: ' % (STAT_LABEL[k], v.get(k, '-')))
            except EOFError:
                break
            raw = raw.strip().replace(',', '').replace('，', '')
            if not raw:
                continue
            try:
                nv = max(1, min(STAT_MAX, int(float(raw))))
            except Exception:
                log('      [忽略] 不是数字')
                continue
            if v.get(k) != nv:
                v[k] = nv
                changed += 1
        if changed:
            d, _ = read_extern()
            if kind == 'new':
                d.setdefault('newInfos', {})[gid] = v
            else:
                d.setdefault('modifyInfos', {})[gid] = v
            ok = write_extern(d)
            log('')
            log('已修改 %d 项，写入%s' % (changed, '成功' if ok else '失败'))
            log('原文件已备份为 ExternPersonage.sav.bak')
        else:
            log('  没有改动')


def _find_newinfo_entry(d, guid):
    """在 newInfos 里按 GUID 找模板（大小写不敏感）。"""
    ni = (d or {}).get('newInfos') or {}
    g = str(guid or '').strip()
    if not g:
        return None, None
    if g in ni:
        return g, ni[g]
    gup = g.upper()
    for k, v in ni.items():
        if str(k).upper() == gup:
            return k, v
    return None, None


def _find_personage_entry(d, pid):
    ps = (d or {}).get('personages') or {}
    p = str(pid or '').strip()
    if not p:
        return None, None
    if p in ps:
        return p, ps[p]
    pup = p.upper()
    for k, v in ps.items():
        if str(k).upper() == pup:
            return k, v
    return None, None


def _faction_id_sample(data, fid):
    """与存档里同势力其它武将一致的 faction 字段写法（如 19 / new_6）。"""
    fk = str(fid or '')
    for per in (data.get('personages') or {}).values():
        inf = per.get('info') or {}
        if str(inf.get('faction', '')).lower() == fk.lower():
            return inf.get('faction')
    return fid


def _set_save_person_display(bi, surname, name):
    sn = str(surname or '').strip()
    nm = str(name or '').strip()
    full = sn + nm
    bi['fullName'] = {'scene': 'None', 'file': 'NO_TABLE', 'key': full or nm or sn}
    bi['name'] = {'scene': 'None', 'file': 'NO_TABLE', 'key': nm or full}
    if sn:
        bi['clan'] = {'scene': 'None', 'file': 'NO_TABLE', 'key': sn}
        bi['surname'] = {'scene': 'None', 'file': 'NO_TABLE', 'key': sn}


# 自建模板里引用其它武将 GUID 的字段（clone 时需按 old->new 映射）
_CUSTOM_REL_LIST_KEYS = ('closees', 'hatedes')
_CUSTOM_REL_SCALAR_KEYS = ('idelPersonage',)


def _norm_guid_map(guid_remap):
    """{ 32位HEX大写 -> 新GUID }"""
    if not guid_remap:
        return {}
    out = {}
    for k, v in guid_remap.items():
        ku = str(k or '').strip().upper()
        vu = str(v or '').strip().upper()
        if re.fullmatch(r'[0-9A-F]{32}', ku) and re.fullmatch(r'[0-9A-F]{32}', vu):
            out[ku] = vu
    return out


def _remap_one_guid(val, gmap):
    if not val or not gmap:
        return val
    s = str(val).strip().upper()
    if re.fullmatch(r'[0-9A-F]{32}', s):
        return gmap.get(s, val)
    return val


def remap_custom_relations(info, guid_remap):
    """亲近(closees)、相性/理想(idelPersonage) 等 GUID 引用按映射表替换。"""
    gmap = _norm_guid_map(guid_remap)
    if not gmap or not isinstance(info, dict):
        return info
    for k in _CUSTOM_REL_LIST_KEYS:
        raw = info.get(k)
        if isinstance(raw, list) and raw:
            info[k] = [_remap_one_guid(x, gmap) for x in raw]
    for k in _CUSTOM_REL_SCALAR_KEYS:
        if info.get(k):
            info[k] = _remap_one_guid(info[k], gmap)
    return info


def clone_custom_extern(source_guid, surname, name, tactical=None, guid_remap=None):
    """复制 newInfos 里一名自建武将模板，生成新 GUID。仅写 ExternPersonage.sav。"""
    d, _ = read_extern()
    if d is None:
        raise ValueError('找不到 ExternPersonage.sav：' + EXTERN_PATH)
    _sg, src = _find_newinfo_entry(d, source_guid)
    if src is None:
        raise ValueError('模板里没有源武将 GUID：' + str(source_guid))
    sn = str(surname or '').strip()
    nm = str(name or '').strip()
    if not sn and not nm:
        raise ValueError('请至少填写姓或名')
    new_gid = uuid.uuid4().hex.upper()
    v = copy.deepcopy(src)
    if sn:
        v['surname'] = sn
    if nm:
        v['name'] = nm
    if tactical is not None and str(tactical).strip() != '':
        v['tactical'] = str(tactical).strip()
    remap_custom_relations(v, guid_remap)
    d.setdefault('newInfos', {})[new_gid] = v
    if not write_extern(d):
        raise ValueError('写入 ExternPersonage.sav 失败')
    return new_gid, _extern_name(v)


def spawn_custom_in_save(data, source_pid, new_pid, surname, name, fid=None):
    """把存档里已有自建武将复制为新人（新 GUID），并设为 Idle。实验功能，请先备份。"""
    if fid is None:
        fid = _player_fid(data)
    if fid is None:
        raise ValueError('存档里没有玩家势力')
    _sp, src = _find_personage_entry(data, source_pid)
    if src is None:
        raise ValueError('存档里没有源武将：' + str(source_pid))
    np = str(new_pid or '').strip().upper()
    if not re.fullmatch(r'[0-9A-F]{32}', np):
        raise ValueError('新武将 GUID 不合法')
    if _find_personage_entry(data, np)[1] is not None:
        raise ValueError('该 GUID 已在存档中存在')
    per = copy.deepcopy(src)
    per['iD'] = np
    inf = per.setdefault('info', {})
    inf['faction'] = _faction_id_sample(data, fid)
    per['state'] = 'Idle'
    per['stateParam'] = 0
    per['stateChangeReason'] = None
    _set_save_person_display(per.setdefault('baseInfo', {}), surname, name)
    data.setdefault('personages', {})[np] = per
    return np, _general_display_name(data, np)


def _load_save_json(path):
    sav = read_sav(path)
    return sav, json.loads(sav['body'].decode('utf-8'))


def _write_save_json(path, sav, data, snapshot=True):
    """写回存档（保留原有备份 + 每次写前打一份历史快照）"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = backup_path(path)
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    if snapshot and _in_real_saves(path):
        snapshot_save(path, 'auto')      # 改动前的内容，随时能退回
    body = json.dumps(data, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')
    blob = build_sav(sav, body)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(blob)
    os.replace(tmp, path)


_ROSTER_CACHE = None


def _known_roster():
    """原版武将名录：从所有 .orig 备份收集。
    用来判断"这个武将是原版就有的，还是后来加的（自建）"。
    """
    global _ROSTER_CACHE
    if _ROSTER_CACHE is not None:
        return _ROSTER_CACHE
    known = set()
    if os.path.isdir(BACKUP_DIR):
        for n in os.listdir(BACKUP_DIR):
            if not n.lower().endswith('.orig'):
                continue
            try:
                d = json.loads(read_sav(os.path.join(BACKUP_DIR, n))['body'].decode('utf-8'))
            except Exception:
                continue
            known |= set((d.get('personages') or {}).keys())
    merged = os.path.join(BACKUP_DIR, '_roster_merged.txt')
    if os.path.exists(merged):
        try:
            with open(merged, encoding='utf-8') as f:
                known |= {x.strip() for x in f if x.strip()}
        except Exception:
            pass
    _ROSTER_CACHE = known
    return known


def _custom_reasons(pid, per, fid, roster):
    """判定"像自建武将"。返回 (是否可疑, 理由列表)

    注意：六维全 100 不能当成判据 —— 本工具打补丁后本国武将本来就都是 100。
    只认结构性特征：不在原版名录 / 没有名称键 / 没有姓氏。
    """
    why = []
    strong = False
    if re.fullmatch(r'[0-9A-Fa-f]{32}', str(pid)):
        why.append('GUID键（自建）')
        strong = True
    elif roster and pid not in roster:
        why.append('不在原版名录')
        strong = True
    inf = per.get('info') or {}
    bi = per.get('baseInfo') or {}
    if str(inf.get('faction', '')).lower() == str(fid).lower():
        nm = (bi.get('name') or {}).get('key') or ''
        if not nm or nm in ('None', ''):
            why.append('无名称键')
            strong = True
        if not bi.get('clan') and not bi.get('surname'):
            why.append('无姓氏')
            strong = True
        vals = []
        for k in STAT_KEYS:
            if k in bi:
                try:
                    vals.append(int(bi[k]))
                except Exception:
                    pass
        if len(vals) == len(STAT_KEYS) and min(vals) >= 95:
            why.append('六维全≥95')
    return strong, why


# ----------------------------------------------------------------- 城市归属
# 城市中文名（仅收录高置信度的；未收录的显示拼音 ID，绝不臆造）
CITY_CN = {
    'luoyang': '\u6d1b\u9633', 'chengdu': '\u6210\u90fd', 'jianye': '\u5efa\u4e1a',
    'xuchang': '\u8bb8\u660c', 'hanzhong': '\u6c49\u4e2d', 'chaisang': '\u67f4\u6851',
    'liaodong': '\u8fbd\u4e1c', 'beiping': '\u5317\u5e73', 'linchuan': '\u4e34\u5ddd',
    'beihai': '\u5317\u6d77', 'ye': '\u90ba', 'zhongshan': '\u4e2d\u5c71',
    'jinyang': '\u664b\u9633', 'yunzhong': '\u4e91\u4e2d', 'shuofang': '\u6714\u65b9',
    'wuwei': '\u6b66\u5a01', 'anding': '\u5b89\u5b9a', 'shangdang': '\u4e0a\u515a',
    'longxi': '\u9647\u897f', 'changan': '\u957f\u5b89', 'jiangxia': '\u6c5f\u590f',
    'chenliu': '\u9648\u7559', 'puyang': '\u6fee\u9633', 'xiapi': '\u4e0b\u90b3',
    'zhuojun': '\u6daa\u90e1', 'wu': '\u5434', 'guangling': '\u5e7f\u9675',
    'shouchun': '\u5bff\u6625', 'runan': '\u6c5d\u5357', 'nanyang': '\u5357\u9633',
    'pengcheng': '\u5f6d\u57ce', 'xiangyang': '\u8944\u9633', 'zitong': '\u6893\u6f7c',
    'baidi': '\u767d\u5e1d', 'bajun': '\u5df4\u90e1', 'jianning': '\u5efa\u5b81',
    'yunnan': '\u4e91\u5357', 'hepu': '\u5408\u6d66', 'jianan': '\u5efa\u5b89',
    'changsha': '\u957f\u6c99', 'wuling': '\u6b66\u9675', 'jiangling': '\u6c5f\u9675',
    'lingling': '\u96f6\u9675', 'guiyang': '\u6842\u9633', 'cangwu': '\u82cd\u68a7',
    'nanhai': '\u5357\u6d77', 'jinan': '\u6d4e\u5357', 'qiao': '\u8c2f',
    'xinye': '\u65b0\u91ce', 'shangyong': '\u4e0a\u5eb8', 'langzhong': '\u9606\u4e2d',
    'zhongli': '\u949f\u79bb', 'lujiang': '\u5e90\u6c5f', 'qichun': '\u8572\u6625',
    'nanpi': '\u5357\u76ae', 'henei': '\u6cb3\u5185', 'hedong': '\u6cb3\u4e1c',
    'liyang': '\u9ece\u9633', 'shanggu': '\u4e0a\u8c37',
    'bailangshan': '\u767d\u72fc\u5c71', 'changli': '\u660c\u9ece',
    'shangjun': '\u4e0a\u90e1', 'jincheng': '\u91d1\u57ce', 'beidi': '\u5317\u5730',
    'chencang': '\u9648\u4ed3', 'hongnong': '\u5f18\u519c', 'yangdi': '\u9633\u7fbf',
    'shangluo': '\u4e0a\u6d1b', 'huarong': '\u534e\u5bb9', 'yuzhang': '\u8c6b\u7ae0',
    'pingyuan': '\u5e73\u539f', 'kuaiji': '\u4f1a\u7a3d', 'yulin': '\u90c1\u6797',
    'xinggu': '\u5174\u53e4', 'wuyuan': '\u4e94\u539f', 'yizhou': '\u76ca\u5dde',
    'wuguan': '\u6b66\u5173', 'yangpingguan': '\u9633\u5e73\u5173',
    'hulaoguan': '\u864e\u7262\u5173', 'hanguuguan': '\u51fd\u8c37\u5173',
    'hanguoguan': '\u51fd\u8c37\u5173', 'tongguan': '\u6f7c\u5173',
    'yanmenguan': '\u96c1\u95e8\u5173', 'huguan': '\u58f6\u5173',
    'jiange': '\u5251\u9601', 'shanhaiguan': '\u5c71\u6d77\u5173',
    'mianzhu': '\u7ef5\u7af9', 'huanyuanguan': '\u8f58\u8f95\u5173',
    'hanjin': '\u6c49\u6d25', 'baimajin': '\u767d\u9a6c\u6d25',
}


def _city_cn(key):
    return CITY_CN.get(str(key).lower(), '')


def _person_index(d):
    """武将表 + 小写索引（prefectId 是大驼峰 YuanShu，personages 键是小驼峰 yuanShu）"""
    ps = d.get('personages') or {}
    return ps, {str(k).lower(): k for k in ps}


def _find_person(ps, plow, pid):
    """按 ID 找武将真实键，大小写无关；找不到返回 None"""
    pid = str(pid or 'None')
    if pid == 'None' or not pid:
        return None
    if pid in ps:
        return pid
    return plow.get(pid.lower())


def _to_camel(key):
    key = str(key or '')
    return key[:1].upper() + key[1:]


def _faction_label(d, fid):
    """势力显示：君主拼音(编号)，如 YuanShu(43)。势力 ID 大小写不敏感"""
    facs = d.get('factions') or {}
    f = facs.get(str(fid)) or {}
    if not f:
        low = str(fid).lower()
        for k, v in facs.items():
            if str(k).lower() == low:
                f = v
                break
    inf = f.get('info') or {}
    king = inf.get('kingId')
    if king and king != 'None':
        return '%s(%s)' % (king, fid)
    return str(fid)


def city_rows(d):
    """城市行数据，按势力编号 + 城市 key 排序（编号稳定）"""
    arch = d.get('architectures') or {}
    facs = d.get('factions') or {}
    out = []
    for key in sorted(arch, key=lambda k: (str((arch[k].get('info') or {}).get('faction')), k)):
        a = arch[key] or {}
        inf = a.get('info') or {}
        fid = str(inf.get('faction'))
        cap = str(((facs.get(fid) or {}).get('info') or {}).get('capitalId') or '')
        out.append(dict(
            key=key, cn=_city_cn(key), fid=fid,
            label=_faction_label(d, fid),
            level=inf.get('level') or 0,
            pop=int(inf.get('population') or 0),
            prefect=str(inf.get('prefectId') or 'None'),
            capital=(cap.lower() == key.lower() and cap != ''),
        ))
    return out


def print_cities(d, title=''):
    """打印编号城市表，返回 key 列表"""
    rows = city_rows(d)
    if not rows:
        log('  该存档没有城市数据')
        return []
    if title:
        log('')
        log('  ' + title)
    log('')
    log('  编号  ' + _pad('城市', 22) + _pad('归属势力', 20) + _pad('首都', 6)
        + _pad('等级', 6) + _pad('人口', 10) + '太守')
    log('  ' + '-' * 88)
    for i, r in enumerate(rows, 1):
        name = ('%s %s' % (r['cn'], r['key'])) if r['cn'] else r['key']
        cap = '\u2605' if r['capital'] else ''
        pre = r['prefect']
        if len(pre) > 20 and all(ch in '0123456789ABCDEFabcdef' for ch in pre):
            pre = pre[:8] + '..'
        log('  [%3d] %s%s%s%s%s%s'
            % (i, _pad(name, 22), _pad(r['label'], 20), _pad(cap, 6),
               _pad(r['level'], 6), _pad(format(r['pop'], ','), 10), pre))
    log('')
    log('  \u2605 = 该势力首都      共 %d 城 / %d 势力'
        % (len(rows), len({r['fid'] for r in rows})))
    return [r['key'] for r in rows]


def _parse_indices(text, total):
    """'1,3,5-8' -> [1,3,5,6,7,8]，越界丢弃"""
    idx = set()
    for tok in str(text).replace('\uff0c', ',').split(','):
        tok = tok.strip()
        if not tok:
            continue
        if '-' in tok:
            a, b = tok.split('-', 1)
            if a.strip().isdigit() and b.strip().isdigit():
                x, y = int(a), int(b)
                if x > y:
                    x, y = y, x
                idx.update(range(x, y + 1))
        elif tok.isdigit():
            idx.add(int(tok))
    return sorted(i for i in idx if 1 <= i <= total)


def _fix_capitals(d, fids, notes):
    """被改动的势力，若首都不在自己手里就重指一个；无城则置 None"""
    arch = d.get('architectures') or {}
    facs = d.get('factions') or {}
    low = {k.lower(): k for k in arch}
    for fid in fids:
        f = facs.get(str(fid))
        if not f:
            continue
        inf = f.setdefault('info', {})
        own = [k for k, a in arch.items()
               if str((a.get('info') or {}).get('faction')).lower() == str(fid).lower()]
        cur = str(inf.get('capitalId') or 'None')
        curkey = low.get(cur.lower()) if cur != 'None' else None
        if curkey and curkey in own:
            continue
        if not own:
            inf['capitalId'] = 'None'
            notes.append('  \u26a0 势力 %s 已无任何城市（首都置空）' % _faction_label(d, fid))
            continue
        best = sorted(own, key=lambda k: (-int((arch[k].get('info') or {}).get('level') or 0),
                                          -int((arch[k].get('info') or {}).get('population') or 0)))[0]
        inf['capitalId'] = _to_camel(best)
        notes.append('  \u00b7 势力 %s 首都改到 %s %s'
                     % (_faction_label(d, fid), _city_cn(best) or '', best))


def _fix_after_transfer(d, warn):
    """城市易手后，清理所有指向城市的悬空引用 + 修正守军兵种。

    游戏自己易手时 guardNum / guardTroopKindId 必改（实测 100% / 98%），
    不改会让新势力带着旧兵种的守军，读档时可能找不到模板而崩退。
    """
    arch = d.get('architectures') or {}
    facs = d.get('factions') or {}
    low = {k.lower(): k for k in arch}
    own = {k.lower(): str((a.get('info') or {}).get('faction')).lower()
           for k, a in arch.items()}

    # 每个势力"自己城市的守军兵种"（用来给新占的城选兵种）
    kinds = {}
    for k, a in arch.items():
        f = own[k.lower()]
        g = str(a.get('guardTroopKindId') or 'None')
        if g != 'None':
            kinds.setdefault(f, []).append(g)

    fixed_guard = 0
    for k, a in arch.items():
        f = own[k.lower()]
        g = str(a.get('guardTroopKindId') or 'None')
        cand = kinds.get(f) or []
        if cand and g not in cand:
            a['guardTroopKindId'] = cand[0]
            fixed_guard += 1

    # AI 的目标城如果变成了自己的城，必须清掉（否则寻路/攻击逻辑会访问无效目标）
    cleared = 0
    for k, a in arch.items():
        ai = a.get('architectureAI')
        if not isinstance(ai, dict):
            continue
        tgt = str(ai.get('readyAttackTargetArchitecture') or 'None')
        if tgt == 'None':
            continue
        tk = low.get(tgt.lower())
        if tk is None:
            ai['readyAttackTargetArchitecture'] = 'None'
            cleared += 1
        elif own[tk.lower()] == own[k.lower()]:
            ai['readyAttackTargetArchitecture'] = 'None'
            ai['defenseState'] = 'None'
            cleared += 1
    for fid, f in facs.items():
        me = str(fid).lower()
        lst = f.get('autoBuildCityOrder') or []
        if lst:
            keep = [x for x in lst
                    if str(x).lower() not in low or own[str(x).lower()] == me]
            if len(keep) != len(lst):
                f['autoBuildCityOrder'] = keep
                cleared += len(lst) - len(keep)
        for fld in ('priorityFoodArch', 'stratagemCity', 'stratagemTargetCity',
                    'requestSupportArchitectureId'):
            v = str(f.get(fld) or 'None')
            if v == 'None':
                continue
            ck = low.get(v.lower())
            if ck is None or own[ck.lower()] != me:
                f[fld] = 'None'
                cleared += 1
        inf = f.get('info') or {}
        cf = inf.get('capitalFeatures') or []
        if cf:
            cap = str(inf.get('capitalId') or 'None')
            ck = low.get(cap.lower()) if cap != 'None' else None
            feats = {str(x).lower() for x in (arch[ck].get('features') or {})} if ck else set()
            keep = [x for x in cf if str(x).lower() in feats]
            if len(keep) != len(cf):
                inf['capitalFeatures'] = keep
                cleared += len(cf) - len(keep)

    if fixed_guard:
        warn.append('  \u00b7 守军兵种修正 %d 座（跟随新势力）' % fixed_guard)
    if cleared:
        warn.append('  \u00b7 清理悬空城市引用 %d 处' % cleared)
    return fixed_guard, cleared


def transfer_cities(d, keys, target, move_officers=False, keep_one=True):
    """把 keys 里的城市全部改属 target 势力。

    keep_one=True（默认）：如果某个势力会被转走到一座城不剩，就自动保留它的
    1 座城（优先首都）。这是硬性保护 —— 游戏无法处理"存在但没有城的势力"，
    实测会让 AI 卡死（全局 31 个 0 城势力时游戏直接卡崩）。
    想强行清空请传 keep_one=False，但大概率会崩。

    move_officers=False 时清空城内的太守/驻守岗位（武将留在原势力，游戏会重新指派）
    move_officers=True  时把太守/驻守武将一并转给 target
    返回 (done, lines, warns)"""
    arch = d.get('architectures') or {}
    facs = d.get('factions') or {}
    persons, plow = _person_index(d)
    target = str(target)
    lines, warns = [], []
    if target not in facs:
        return 0, [], ['目标势力 %s 不在该存档里' % target]

    # ---------- 保护：不允许产生"零城势力" ----------
    if keep_one:
        from collections import defaultdict
        owner = {k: str((arch[k].get('info') or {}).get('faction'))
                 for k in arch if k in keys}
        total = defaultdict(int)
        for a in arch.values():
            total[str((a.get('info') or {}).get('faction')).lower()] += 1
        move_cnt = defaultdict(int)
        for k, f in owner.items():
            move_cnt[f.lower()] += 1
        drop = set()
        for f_low, n_move in move_cnt.items():
            if n_move < total.get(f_low, 0):
                continue                      # 还剩别的城，安全
            # 该势力的城全在转移列表里 -> 保留 1 座
            mine = [k for k, f in owner.items() if f.lower() == f_low]
            cap = str(((facs.get(f_low) or {}).get('info') or {}).get('capitalId') or '')
            low_cap = cap.lower()
            keep = None
            for k in mine:
                if low_cap and k.lower() == low_cap:
                    keep = k
                    break
            if keep is None:
                keep = sorted(mine, key=lambda k: -int(
                    (arch[k].get('info') or {}).get('level') or 0))[0] if mine else None
            if keep:
                drop.add(keep)
                warns.append('  \u26a0 %s 会被转空，已保留 %s（游戏不支持零城势力）'
                             % (_faction_label(d, owner[keep]), _city_cn(keep) or keep))
        keys = [k for k in keys if k not in drop]
        if not keys:
            return 0, [], warns + ['  所有目标城都被保护拦下了，没有可转的城']

    done = 0
    touched = set()
    for k in keys:
        a = arch.get(k)
        if not a:
            warns.append('城市 %s 不存在，跳过' % k)
            continue
        inf = a.setdefault('info', {})
        old = str(inf.get('faction'))
        if old.lower() == target.lower():
            warns.append('%s 已经属于目标势力，跳过' % (_city_cn(k) or k))
            continue
        # 收集城内任职武将
        offs = []
        if str(inf.get('prefectId') or 'None') != 'None':
            offs.append(str(inf['prefectId']))
        pu = a.get('prefecturalUnit') or {}
        if str(pu.get('staffId') or 'None') != 'None':
            offs.append(str(pu['staffId']))
        for u in (a.get('areaUnitList') or []):
            if str(u.get('staffId') or 'None') != 'None':
                offs.append(str(u['staffId']))
        # 换归属
        a['lastFactionName'] = old
        inf['faction'] = target
        if move_officers:
            for pid in set(offs):
                real = _find_person(persons, plow, pid)
                p = persons.get(real) if real else None
                if isinstance(p, dict):
                    p.setdefault('info', {})['faction'] = target
        else:
            inf['prefectId'] = 'None'
            if str(pu.get('staffId') or 'None') != 'None':
                pu['staffId'] = 'None'
            # 必须同时归零：staffId=None 但 staffAccTime!=0 会让游戏
            # 认为"有太守且任职 N 秒"，访问空对象 -> 0x4568 空指针崩退
            pu['staffAccTime'] = 0
            for u in (a.get('areaUnitList') or []):
                if str(u.get('staffId') or 'None') != 'None':
                    u['staffId'] = 'None'
                if u.get('staffId') in (None, 'None', ''):
                    u['staffAccTime'] = 0
        done += 1
        touched.add(old)
        touched.add(target)
        lines.append('  %s  %s -> %s'
                     % (_pad((_city_cn(k) + ' ' if _city_cn(k) else '') + k, 22),
                        _faction_label(d, old), _faction_label(d, target)))
    if done:
        _fix_capitals(d, touched, warns)
        _fix_after_transfer(d, warns)
        flog("transfer: %d cities -> %s | %s"
             % (done, target, ', '.join(k for k in keys[:20])))
        for w in warns:
            if '⚠' in w:
                flog("   " + w.strip())
    return done, lines, warns


def _person_id_camel(pid_key):
    """personages 键 -> 岗位 ID（juShou -> JuShou）"""
    s = str(pid_key or '')
    if not s:
        return s
    return s[0].upper() + s[1:]


def _city_arch_name(city_key):
    """武将 info.architecture 常见写法（luoYang -> LuoYang）"""
    return _person_id_camel(city_key)


def _looks_like_guid(pid):
    s = str(pid or '')
    return len(s) >= 32 and all(c in '0123456789abcdefABCDEF' for c in s)


def _collect_prefect_ids(d):
    busy = set()
    for a in (d.get('architectures') or {}).values():
        inf = a.get('info') or {}
        pre = str(inf.get('prefectId') or 'None')
        if pre != 'None':
            busy.add(pre.lower())
        pu = a.get('prefecturalUnit') or {}
        sid = str(pu.get('staffId') or 'None')
        if sid != 'None':
            busy.add(sid.lower())
    return busy


def _bi_stat(bi, key, default=0):
    try:
        return int(bi.get(key, default))
    except Exception:
        return default


COMBAT_STAT_KEYS = ('command', 'strength', 'agility')
ADMIN_STAT_KEYS = ('politics', 'intelligence', 'charm')
PREFECT_BUSY_STATES = frozenset(
    ('InTroop', 'Working', 'InPrison', 'Search', 'InPrefect'))
DEFAULT_COMBAT_EXCLUDE = 232


def _combat_score(bi):
    return sum(_bi_stat(bi, k) for k in COMBAT_STAT_KEYS)


def _admin_score(bi):
    p = _bi_stat(bi, 'politics')
    i = _bi_stat(bi, 'intelligence')
    c = _bi_stat(bi, 'charm')
    return int(p * 1.35 + i + c * 0.6)


def _prefect_suitability(bi):
    return _admin_score(bi) - _combat_score(bi) * 0.35


def _is_combat_general(bi, combat_threshold=DEFAULT_COMBAT_EXCLUDE):
    """武/统/敏偏高或明显偏战斗的武将不当太守，留给出征。"""
    combat = _combat_score(bi)
    admin = _admin_score(bi)
    if combat >= combat_threshold:
        return True
    if combat >= 200 and combat >= admin * 1.12:
        return True
    if _bi_stat(bi, 'strength') >= 90 and _bi_stat(bi, 'command') >= 85:
        return True
    if _bi_stat(bi, 'agility') >= 92 and combat >= 210:
        return True
    return False


def _collect_faction_troop_generals(d, fid):
    """已在部队编制中的武将 ID（含 GUID），不可调去任太守。"""
    busy = set()
    facs = d.get('factions') or {}
    fk = None
    for k in facs:
        if str(k).lower() == str(fid).lower():
            fk = k
            break
    if fk is None:
        return busy
    troops = (facs[fk].get('troops') or {})
    items = troops.values() if isinstance(troops, dict) else troops
    for t in items:
        if not isinstance(t, dict):
            continue
        for g in ('generalId1', 'generalId2', 'generalId3'):
            gid = str(t.get(g) or 'None')
            if gid != 'None':
                busy.add(gid.lower())
    return busy


def _player_king_person_key(d, fid):
    facs = d.get('factions') or {}
    fk = None
    for k in facs:
        if str(k).lower() == str(fid).lower():
            fk = k
            break
    if fk is None:
        return None
    kid = str((facs[fk].get('info') or {}).get('kingId') or 'None')
    if kid in ('None', '', 'none'):
        return None
    persons, plow = _person_index(d)
    return _find_person(persons, plow, kid)


def _arch_matches_city(arch_name, city_key):
    if not arch_name:
        return False
    a = str(arch_name).lower()
    ck = str(city_key).lower()
    if a == ck:
        return True
    return a == _city_arch_name(city_key).lower()


def _city_importance(a):
    inf = a.get('info') or {}
    try:
        lv = int(inf.get('level') or 0)
    except Exception:
        lv = 0
    try:
        pop = int(inf.get('population') or 0)
    except Exception:
        pop = 0
    return (lv, pop)


def _clear_person_prefect_slots(d, person_camel):
    """避免同一武将占两座城的太守岗位"""
    pc = str(person_camel).lower()
    for a in (d.get('architectures') or {}).values():
        inf = a.setdefault('info', {})
        if str(inf.get('prefectId') or 'None').lower() == pc:
            inf['prefectId'] = 'None'
        pu = a.setdefault('prefecturalUnit', {})
        if str(pu.get('staffId') or 'None').lower() == pc:
            pu['staffId'] = 'None'
            pu['staffAccTime'] = 0


def set_city_prefect(d, city_key, person_key):
    """把 person_key（personages 键）任命为 city_key 的太守"""
    arch = d.get('architectures') or {}
    a = arch.get(city_key)
    if not a:
        raise ValueError('城市不存在: ' + city_key)
    persons, plow = _person_index(d)
    real = _find_person(persons, plow, person_key)
    if not real:
        raise ValueError('武将不存在: ' + person_key)
    per = persons[real]
    inf_p = per.setdefault('info', {})
    city_inf = a.setdefault('info', {})
    fid_city = str(city_inf.get('faction'))
    if str(inf_p.get('faction')).lower() != fid_city.lower():
        raise ValueError('武将不属于该城势力')
    if inf_p.get('tag1') in ('Death', 'Dead'):
        raise ValueError('武将已阵亡')
    pid_show = _person_id_camel(real)
    _clear_person_prefect_slots(d, pid_show)
    city_inf['prefectId'] = pid_show
    pu = a.setdefault('prefecturalUnit', {})
    pu['staffId'] = pid_show
    # staffId 有值时 staffAccTime 须与原版一致为非 0（仅 None 时才必须 0）
    pu['staffAccTime'] = max(1, int(pu.get('staffAccTime') or 0))
    inf_p['architecture'] = _city_arch_name(city_key)
    per['state'] = 'InPrefect'
    return pid_show


def auto_assign_prefects(d, fid=None, city_keys=None, combat_threshold=None):
    """为本国无太守城市自动任命：仅调遣 Idle 内政型武将，武统敏高者保留给出征。"""
    if combat_threshold is None:
        combat_threshold = DEFAULT_COMBAT_EXCLUDE
    try:
        combat_threshold = int(combat_threshold)
    except Exception:
        combat_threshold = DEFAULT_COMBAT_EXCLUDE
    if fid is None:
        fid = _player_fid(d)
    if fid is None:
        return 0, [], ['找不到玩家势力']
    arch = d.get('architectures') or {}
    targets = []
    for k, a in arch.items():
        if city_keys is not None and k not in city_keys:
            continue
        inf = a.get('info') or {}
        if str(inf.get('faction')).lower() != str(fid).lower():
            continue
        if str(inf.get('prefectId') or 'None') != 'None':
            continue
        targets.append((k, a))
    if not targets:
        return 0, [], ['玩家势力没有需要任命太守的城市（他国不在处理范围内）']
    targets.sort(key=lambda x: _city_importance(x[1]), reverse=True)

    busy_prefect = _collect_prefect_ids(d)
    troop_busy = _collect_faction_troop_generals(d, fid)
    king_key = _player_king_person_key(d, fid)
    king_low = set()
    if king_key:
        king_low.add(str(king_key).lower())
        king_low.add(_person_id_camel(king_key).lower())

    stat = {
        'pool': 0,
        'skip_guid': 0,
        'skip_state': 0,
        'skip_prefect_slot': 0,
        'skip_troop': 0,
        'skip_fighter': 0,
        'skip_king': 0,
        'skip_no_stats': 0,
    }
    pool = []
    for pid, per in (d.get('personages') or {}).items():
        inf = per.get('info') or {}
        if str(inf.get('faction', '')).lower() != str(fid).lower():
            continue
        if inf.get('tag1') in ('Death', 'Dead'):
            continue
        if _looks_like_guid(pid):
            stat['skip_guid'] += 1
            continue
        show = _person_id_camel(pid).lower()
        plow = str(pid).lower()
        if show in king_low or plow in king_low:
            stat['skip_king'] += 1
            continue
        state = str(per.get('state') or 'Idle')
        if state != 'Idle':
            stat['skip_state'] += 1
            continue
        if show in busy_prefect or plow in busy_prefect:
            stat['skip_prefect_slot'] += 1
            continue
        if show in troop_busy or plow in troop_busy:
            stat['skip_troop'] += 1
            continue
        bi = per.get('baseInfo') or {}
        if not bi:
            stat['skip_no_stats'] += 1
            continue
        if _is_combat_general(bi, combat_threshold):
            stat['skip_fighter'] += 1
            continue
        home = str(inf.get('architecture') or '').lower()
        pool.append({
            'pid': pid,
            'home': home,
            'suit': _prefect_suitability(bi),
            'combat': _combat_score(bi),
            'admin': _admin_score(bi),
        })
        stat['pool'] += 1

    fac_label = _faction_label(d, fid)
    summary = [
        '任命范围：仅玩家势力「%s」的无太守城，共 %d 座（他国城市不处理）'
        % (fac_label, len(targets)),
        '任命规则：仅 state=Idle；排除出征(InTroop)/编制中/在岗(InPrefect)/工作(Working)等；'
        '武统敏合计≥%d 或明显偏战斗者不任太守；优先政智魅高且就近（所在城）' % combat_threshold,
        '  可调遣候选 %d 人 | 非Idle %d | 已在编部队 %d | 高战力 %d | 已有太守岗 %d | 君主 %d'
        % (stat['pool'], stat['skip_state'], stat['skip_troop'],
           stat['skip_fighter'], stat['skip_prefect_slot'], stat['skip_king']),
    ]
    lines = []
    assigned = 0
    for city_key, _a in targets:
        if not pool:
            left = len(targets) - assigned
            if left:
                lines.append('  内政型空闲武将不足，还有 %d 座城未任命' % left)
            break
        ck = city_key.lower()
        best_i = 0
        best_score = None
        for i, c in enumerate(pool):
            local = 100000 if _arch_matches_city(c['home'], city_key) else 0
            score = local + c['suit']
            if best_score is None or score > best_score:
                best_score = score
                best_i = i
        cand = pool.pop(best_i)
        try:
            show = set_city_prefect(d, city_key, cand['pid'])
            assigned += 1
            busy_prefect.add(show.lower())
            cn = _city_cn(city_key) or city_key
            tag = '就近' if _arch_matches_city(cand['home'], city_key) else '调遣'
            lines.append('  %s ← %s (%s 政%d/战%d)'
                           % (_pad(cn, 10), show, tag, cand['admin'], cand['combat']))
        except ValueError as e:
            lines.append('  跳过 %s: %s' % (city_key, e))
    return assigned, lines, summary


# ----------------------------------------------------------------- 快速编队（一支部队 = 主将 + 2 副将，对应一条 troops）
def _normalize_generals_triple(gens, sq=None):
    if not isinstance(gens, list):
        gens = []
        if sq:
            gens = [sq.get('generalId1'), sq.get('generalId2'), sq.get('generalId3')]
    row = []
    for g in (gens + [None, None, None])[:3]:
        if g is None or str(g).strip() in ('', 'None', 'none'):
            row.append('None')
        else:
            row.append(str(g).strip())
    return row


def _flat_preset_entry(pid, name, kind, generals, staffing=0):
    if not kind:
        return None
    return {
        'id': pid,
        'name': name,
        'troopKindId': kind,
        'generals': _normalize_generals_triple(generals),
        'staffing': int(staffing) if str(staffing or '').isdigit() else 0,
    }


def normalize_team_presets(raw):
    """校验 config 中的 team_presets。
    一条预设 = 游戏意义的一支「编队」（三人部队），不是 teamInfos 编组。"""
    out = []
    if not isinstance(raw, list):
        return out
    seen = set()
    seq = 0
    for i, p in enumerate(raw):
        if not isinstance(p, dict):
            continue
        base_id = str(p.get('id') or ('preset_%d' % (i + 1))).strip()
        base_name = str(p.get('name') or base_id).strip() or base_id
        squads = p.get('squads')
        if isinstance(squads, list) and squads:
            for j, sq in enumerate(squads):
                if not isinstance(sq, dict):
                    continue
                kind = str(sq.get('troopKindId') or sq.get('kind') or '').strip()
                seq += 1
                pid = base_id if len(squads) == 1 else '%s_%d' % (base_id, j + 1)
                if pid in seen:
                    pid = 'preset_%d' % seq
                seen.add(pid)
                nm = base_name if len(squads) == 1 else '%s·%s' % (
                    base_name, sq.get('label') or ('队%d' % (j + 1)))
                st = int(sq['staffing']) if str(sq.get('staffing') or '').isdigit() else 0
                ent = _flat_preset_entry(pid, nm, kind, sq.get('generals'), st)
                if ent:
                    if not isinstance(sq.get('generals'), list):
                        ent['generals'] = _normalize_generals_triple(None, sq)
                    try:
                        ent['gameTeamId'] = int(sq.get('gameTeamId') or p.get('gameTeamId') or 0)
                    except Exception:
                        ent['gameTeamId'] = 0
                    out.append(ent)
            continue
        kind = str(p.get('troopKindId') or p.get('kind') or '').strip()
        if not kind:
            continue
        seq += 1
        pid = base_id or ('preset_%d' % seq)
        if pid in seen:
            pid = 'preset_%d' % seq
        seen.add(pid)
        st = int(p['staffing']) if str(p.get('staffing') or '').isdigit() else 0
        ent = _flat_preset_entry(pid, base_name, kind, p.get('generals'), st)
        if ent:
            try:
                ent['gameTeamId'] = int(p.get('gameTeamId') or 0)
            except Exception:
                ent['gameTeamId'] = 0
            out.append(ent)
    return out


def get_team_presets(cfg=None):
    cfg = cfg if cfg is not None else load_cfg()
    raw = cfg.get('team_presets')
    normed = normalize_team_presets(raw) if raw else []
    if not normed:
        return normalize_team_presets(DEFAULT_TEAM_PRESETS)
    return normed


def ensure_team_presets():
    """保证 config 含全部内置预设：空则写入；缺 id 则按 DEFAULT 顺序补全并落盘。"""
    cfg = load_cfg()
    current = normalize_team_presets(cfg.get('team_presets') or [])
    if not current:
        presets = normalize_team_presets(DEFAULT_TEAM_PRESETS)
        cfg['team_presets'] = presets
        save_cfg(cfg)
        return presets
    by_id = {p['id']: p for p in current}
    merged = []
    seen = set()
    changed = False
    for d in DEFAULT_TEAM_PRESETS:
        did = d['id']
        if did in by_id:
            merged.append(by_id[did])
        else:
            merged.append(dict(d))
            changed = True
        seen.add(did)
    for p in current:
        pid = p.get('id')
        if pid and pid not in seen:
            merged.append(p)
            seen.add(pid)
    if changed or len(merged) != len(current):
        cfg['team_presets'] = normalize_team_presets(merged)
        save_cfg(cfg)
    return get_team_presets(cfg)


def seed_team_presets_if_empty():
    """兼容旧调用名。"""
    return ensure_team_presets()


def save_team_presets(presets):
    cfg = load_cfg()
    cfg['team_presets'] = normalize_team_presets(presets)
    save_cfg(cfg)
    return cfg['team_presets']


def _faction_key(d, fid):
    for k in (d.get('factions') or {}):
        if str(k).lower() == str(fid).lower():
            return k
    return None


def _max_troop_id(d):
    m = 0
    for f in (d.get('factions') or {}).values():
        for t in (f.get('troops') or {}).values():
            try:
                m = max(m, int(t.get('troopId') or 0))
            except Exception:
                pass
    return m


def _collect_troop_general_tokens(d, fid=None):
    busy = set()
    facs = d.get('factions') or {}
    items = []
    if fid is not None:
        fk = _faction_key(d, fid)
        if fk:
            tr = (facs[fk].get('troops') or {})
            items = tr.values() if isinstance(tr, dict) else tr
    else:
        for f in facs.values():
            tr = (f.get('troops') or {})
            items.extend(tr.values() if isinstance(tr, dict) else tr)
    for t in items:
        if not isinstance(t, dict):
            continue
        for g in ('generalId1', 'generalId2', 'generalId3'):
            gid = str(t.get(g) or 'None')
            if gid != 'None':
                busy.add(gid.lower())
    return busy


def _general_troop_token(pid):
    if _looks_like_guid(pid):
        return str(pid).upper()
    return _person_id_camel(pid)


def _resolve_person_for_troop(d, token, fid):
    if token is None or str(token).strip() in ('', 'None', 'none'):
        return None
    persons, plow = _person_index(d)
    real = _find_person(persons, plow, token)
    if not real:
        raise ValueError('武将不存在: ' + str(token))
    per = persons[real]
    inf = per.get('info') or {}
    if str(inf.get('faction', '')).lower() != str(fid).lower():
        raise ValueError('武将 %s 不属于玩家势力' % token)
    if inf.get('tag1') in ('Death', 'Dead'):
        raise ValueError('武将 %s 已阵亡' % token)
    return real, per


def _build_architecture_pos_index(d):
    arch = d.get('architectures') or {}
    key_by_lower = {}
    for k, a in arch.items():
        key_by_lower[k.lower()] = k
        iD = str(a.get('iD') or k)
        key_by_lower[iD.lower()] = k
    pos = {}
    for f in (d.get('factions') or {}).values():
        for t in (f.get('troops') or {}).values():
            ai = t.get('troopAI') or {}
            if not isinstance(ai, dict):
                continue
            p = t.get('pos') or {}
            if p.get('x') is None:
                continue
            for _k, aid in ai.items():
                if 'architecture' not in str(_k).lower():
                    continue
                aid = str(aid or 'None')
                if aid == 'None':
                    continue
                ck = key_by_lower.get(aid.lower())
                if ck and ck not in pos:
                    pos[ck] = {'x': int(p['x']), 'y': int(p['y'])}
    return pos


def _city_pos_override(city_key):
    cfg = load_cfg()
    raw = cfg.get('city_pos') or cfg.get('city_pos_overrides') or {}
    if not isinstance(raw, dict):
        return None
    for k, v in raw.items():
        if str(k).lower() != str(city_key).lower():
            continue
        if isinstance(v, dict) and v.get('x') is not None and v.get('y') is not None:
            return {'x': int(v['x']), 'y': int(v['y'])}
    return None


def _resolve_city_deploy_pos(d, city_key, slot_index, pos_index=None):
    if pos_index is None:
        pos_index = _build_architecture_pos_index(d)
    base = pos_index.get(city_key) or _city_pos_override(city_key)
    if not base:
        raise ValueError(
            '无法确定「%s」的地图坐标：请先在游戏中到此城驻扎一支部队，或在 config.json 的 city_pos 里填写 {"%s": {"x":..,"y":..}}'
            % (_city_cn(city_key) or city_key, city_key))
    dx = (slot_index % 3) - 1
    dy = slot_index // 3
    return {'x': base['x'] + dx, 'y': base['y'] + dy}


def _pick_troop_template(d, fid, troop_kind_id):
    fk = _faction_key(d, fid)
    if fk is None:
        raise ValueError('找不到势力')
    troops = (d['factions'][fk].get('troops') or {})
    items = list(troops.values()) if isinstance(troops, dict) else list(troops)
    for t in items:
        if str(t.get('troopKindId')) == str(troop_kind_id):
            return copy.deepcopy(t)
    if items:
        return copy.deepcopy(items[0])
    raise ValueError('势力中没有部队可参考，无法新建')


def _alloc_team_id(d):
    ti = d.setdefault('teamInfos', {})
    used = set()
    for k in ti:
        try:
            used.add(int(k))
        except Exception:
            pass
    for n in range(1, 128):
        slot = ti.get(str(n)) or ti.get(n)
        if slot is None:
            return n
        if not (slot.get('troopIds') or []):
            return n
    return (max(used) + 1) if used else 1


def _general_display_name(d, token):
    if not token or str(token) == 'None':
        return '—'
    persons, plow = _person_index(d)
    real = _find_person(persons, plow, token)
    if not real:
        s = str(token)
        return s[:10] + '…' if len(s) > 12 else s
    bi = (persons[real].get('baseInfo') or {})
    fn = bi.get('fullName')
    if isinstance(fn, dict) and fn.get('key'):
        return str(fn.get('key'))
    return _person_id_camel(real)


def list_player_teams(d, fid=None):
    """读档内玩家「三人编队」列表：每条 troops = 主将 + 2 副将。"""
    if fid is None:
        fid = _player_fid(d)
    if fid is None:
        return []
    fk = _faction_key(d, fid)
    if fk is None:
        return []
    rows = []
    for t in (d['factions'][fk].get('troops') or {}).values():
        if not isinstance(t, dict):
            continue
        gens = []
        gens_cn = []
        for g in ('generalId1', 'generalId2', 'generalId3'):
            v = str(t.get(g) or 'None')
            if v == 'None':
                gens.append('None')
                gens_cn.append('—')
            else:
                gens.append(v)
                gens_cn.append(_general_display_name(d, v))
        tid = int(t.get('troopId') or 0)
        lead = gens_cn[0] if gens_cn else '—'
        rows.append({
            'troopId': tid,
            'gameTeamId': int(t.get('teamId') or 0),
            'name': lead,
            'troopKindId': str(t.get('troopKindId') or ''),
            'generals': gens,
            'generals_cn': gens_cn,
            'label': '%s / %s / %s' % tuple(gens_cn),
        })
    rows.sort(key=lambda r: (r.get('gameTeamId') or 0, r.get('troopId') or 0))
    return rows


def _append_troop_to_game_team(d, game_team_id, troop_id):
    """可选：挂到游戏 teamInfos 编组（与「三人编队」不同层）。"""
    if not game_team_id:
        return
    try:
        gid = int(game_team_id)
    except Exception:
        return
    if gid <= 0:
        return
    ti = d.setdefault('teamInfos', {})
    tkey = str(gid)
    slot = ti.get(tkey)
    if not isinstance(slot, dict):
        slot = {'troopIds': []}
        ti[tkey] = slot
    ids = list(slot.get('troopIds') or [])
    tid = int(troop_id)
    if tid not in ids:
        ids.append(tid)
    slot['troopIds'] = ids


def _create_one_troop_at_city(d, city_key, preset, fid, slot_index, busy_g, pos_index,
                              arch_id, troops, fac, game_team_id=0):
    kind = str(preset.get('troopKindId') or '')
    if not kind:
        raise ValueError('预设缺少兵种 troopKindId')
    t = _pick_troop_template(d, fid, kind)
    next_tid = _max_troop_id(d) + 1
    # 上面 max 在循环外应递增 — 调用方传 busy 并每次 +1 tid
    t['troopId'] = next_tid
    t['factionId'] = str(fac.get('iD') or fid)
    t['troopKindId'] = kind
    try:
        gt = int(game_team_id or 0)
    except Exception:
        gt = 0
    t['teamId'] = gt
    cap = int(preset.get('staffing') or 0)
    if cap <= 0:
        cap = troop_cap(kind, t.get('staffing'))
    t['staffing'] = cap
    t['healthyNum'] = cap
    t['injuriedNum'] = 0
    t['bDestroyed'] = False
    t['pos'] = _resolve_city_deploy_pos(d, city_key, slot_index, pos_index)
    t['state'] = 'TroopAction'
    ai = t.setdefault('troopAI', {})
    if not isinstance(ai, dict):
        ai = {}
        t['troopAI'] = ai
    ai['belongArchitectureId'] = arch_id
    ai.setdefault('aIState', 'None')

    slots = ('generalId1', 'generalId2', 'generalId3')
    gen_names = []
    for si, slot in enumerate(slots):
        tok = (preset.get('generals') or [None, None, None])[si]
        if tok in (None, 'None', 'none', ''):
            t[slot] = 'None'
            continue
        real, per = _resolve_person_for_troop(d, tok, fid)
        show = _general_troop_token(real)
        if show.lower() in busy_g:
            raise ValueError('武将 %s 已在其他部队中' % tok)
        if str(per.get('state') or 'Idle') not in ('Idle',):
            raise ValueError('武将 %s 状态为 %s，无法编入新队' % (tok, per.get('state')))
        t[slot] = show
        busy_g.add(show.lower())
        per['state'] = 'InTroop'
        gen_names.append(_general_display_name(d, show))

    troops[str(next_tid)] = t
    _append_troop_to_game_team(d, gt, next_tid)
    cn = _city_cn(city_key) or city_key
    gcn = (_general_display_name(d, t.get('generalId2')),
           _general_display_name(d, t.get('generalId3')))
    line = '  %s @ %s · %s  主:%s  副:%s / %s' % (
        kind, cn, preset.get('name') or kind,
        gen_names[0] if gen_names else '—', gcn[0], gcn[1],
    )
    return next_tid, line


def create_team_preset_at_city(d, city_key, preset, fid=None, team_id=None):
    """
    在 city_key 按一条预设创建一支三人部队（一条 troops）。
    preset: normalize 后的 { troopKindId, generals[3], ... }
    team_id: 可选游戏 teamInfos 编组号；0/None 表示不写入编组（散队）。
    """
    if fid is None:
        fid = _player_fid(d)
    if fid is None:
        raise ValueError('找不到玩家势力')
    fk = _faction_key(d, fid)
    if fk is None:
        raise ValueError('找不到玩家势力')
    arch = d.get('architectures') or {}
    a = arch.get(city_key)
    if not a:
        raise ValueError('城市不存在: ' + city_key)
    if str((a.get('info') or {}).get('faction')).lower() != str(fid).lower():
        raise ValueError('该城不属于玩家')

    fac = d['factions'][fk]
    troops = fac.setdefault('troops', {})
    if not isinstance(troops, dict):
        troops = {str(t.get('troopId')): t for t in troops if isinstance(t, dict)}
        fac['troops'] = troops

    busy_g = _collect_troop_general_tokens(d, fid)
    pos_index = _build_architecture_pos_index(d)
    arch_id = _city_arch_id(city_key, d)
    if team_id in (None, '', 'none'):
        team_id = preset.get('gameTeamId', 0)
    gt = 0 if team_id in (None, '', 'none') else team_id
    tid, line = _create_one_troop_at_city(
        d, city_key, preset, fid, 0, busy_g, pos_index, arch_id, troops, fac, gt)
    return gt, 1, [line]


def deploy_team_presets_at_city(d, city_key, presets, fid=None, game_team_id=None):
    """在同一城市连续创建多支「三人编队」。"""
    if not presets:
        raise ValueError('没有选中任何预设')
    if fid is None:
        fid = _player_fid(d)
    fk = _faction_key(d, fid)
    arch = (d.get('architectures') or {}).get(city_key)
    if not arch:
        raise ValueError('城市不存在: ' + city_key)
    if str((arch.get('info') or {}).get('faction')).lower() != str(fid).lower():
        raise ValueError('该城不属于玩家')
    fac = d['factions'][fk]
    troops = fac.setdefault('troops', {})
    if not isinstance(troops, dict):
        troops = {str(t.get('troopId')): t for t in troops if isinstance(t, dict)}
        fac['troops'] = troops
    busy_g = _collect_troop_general_tokens(d, fid)
    pos_index = _build_architecture_pos_index(d)
    arch_id = _city_arch_id(city_key, d)
    gt = game_team_id
    lines = []
    for i, preset in enumerate(presets):
        before = _max_troop_id(d)
        pg = gt if gt not in (None, '', 0) else preset.get('gameTeamId', 0)
        _tid, line = _create_one_troop_at_city(
            d, city_key, preset, fid, i, busy_g, pos_index, arch_id, troops, fac, pg)
        if _max_troop_id(d) <= before:
            raise ValueError('创建部队失败')
        lines.append(line)
    return gt or 0, len(presets), lines


def _city_arch_id(city_key, d):
    a = (d.get('architectures') or {}).get(city_key)
    if not a:
        return _city_arch_name(city_key)
    return str(a.get('iD') or _city_arch_name(city_key))


def check_map(d):
    """城市归属一致性自检，返回问题列表。
    faction='None' 是合法无主城；势力 ID 大小写不敏感（城市可能写 New_0，势力键是 new_0）"""
    arch = d.get('architectures') or {}
    facs = d.get('factions') or {}
    flow = {str(k).lower(): k for k in facs}
    persons, plow = _person_index(d)
    problems = []
    low = {k.lower(): k for k in arch}
    cnt = {}
    for k, a in arch.items():
        inf = a.get('info') or {}
        fid = str(inf.get('faction'))
        if fid in ('None', '', 'none'):
            continue                      # 无主城（中立/空城）是正常状态
        cnt[fid.lower()] = cnt.get(fid.lower(), 0) + 1
        if fid.lower() not in flow:
            problems.append('城市 %s 的归属势力 %s 不在势力表里' % (k, fid))
        pre = str(inf.get('prefectId') or 'None')
        if pre != 'None':
            real = _find_person(persons, plow, pre)
            p = persons.get(real) if real else None
            if p:
                pf = str((p.get('info') or {}).get('faction'))
                if pf.lower() != fid.lower():
                    problems.append('%s 太守 %s 属于势力 %s（城属 %s）'
                                    % (k, pre, pf, fid))
    for fid, f in facs.items():
        inf = f.get('info') or {}
        cap = str(inf.get('capitalId') or 'None')
        if cap == 'None':
            continue
        ck = low.get(cap.lower())
        fkey = str(fid).lower()
        if ck is None:
            problems.append('势力 %s 首都 %s 不是已知城市' % (fid, cap))
            continue
        owner = str((arch[ck].get('info') or {}).get('faction')).lower()
        if owner in ('none', ''):
            problems.append('势力 %s 首都 %s 是无主城' % (fid, cap))
        elif owner != fkey:
            problems.append('势力 %s 首都 %s 归势力 %s' % (fid, cap, owner))
        if cnt.get(fkey, 0) == 0:
            problems.append('势力 %s 没有任何城市' % fid)
    return problems


def map_report(only=None):
    """打印某存档的城市归属总览"""
    name = only or newest_save()
    if not name:
        log('没有存档')
        return
    p = name if os.path.isabs(name) else os.path.join(SAVES_DIR, name)
    d = _sav_json(read_sav(p))
    log('')
    log('  存档: %s' % os.path.basename(p))
    pfid = _player_fid(d)
    log('  玩家: %s' % (_faction_label(d, pfid) if pfid else '?'))
    print_cities(d)
    probs = check_map(d)
    if probs:
        log('')
        log('  \u26a0 一致性问题 %d 项:' % len(probs))
        for x in probs[:12]:
            log('     ' + x)
    else:
        log('')
        log('  \u2713 归属一致性自检通过')


def transfer_ui(only=None):
    """交互式转移城市"""
    name = only or newest_save()
    if not name:
        log('没有存档')
        return
    p = name if os.path.isabs(name) else os.path.join(SAVES_DIR, name)
    sav = read_sav(p)
    d = _sav_json(sav)
    keys = print_cities(d, '城市列表（存档：%s）' % os.path.basename(p))
    if not keys:
        return
    log('')
    log('  要转走哪些城市：1 / 1,3 / 1-5 / @43（势力43的全部城） / Q=取消')
    try:
        c = input('  城市编号: ').strip()
    except EOFError:
        return
    if c.lower() == 'q':
        log('  已取消')
        return
    toks = [t.strip() for t in c.replace('，', ',').split(',') if t.strip()]
    picked = []
    fids_in = []
    for t in toks:
        if t.startswith('@'):
            fids_in.append(t[1:].strip())
    for fid in fids_in:
        fk = [k for k, a in (d.get('architectures') or {}).items()
              if str((a.get('info') or {}).get('faction')) == str(fid)]
        if fk:
            picked += fk
            log('  势力 %s 的全部 %d 城已加入' % (_faction_label(d, fid), len(fk)))
        else:
            log('  势力 %s 没有城市' % fid)
    idx = _parse_indices(','.join(t for t in toks if not t.startswith('@')), len(keys))
    picked += [keys[i - 1] for i in idx]
    seen = set()
    picked = [k for k in picked if not (k in seen or seen.add(k))]
    if not picked:
        log('  没有选中任何城市')
        return
    log('  已选 %d 城: %s' % (len(picked), ', '.join(_city_cn(k) or k for k in picked)))

    facs = d.get('factions') or {}
    flist = sorted(facs, key=lambda f: -sum(
        1 for a in (d.get('architectures') or {}).values()
        if str((a.get('info') or {}).get('faction')) == str(f)))
    log('')
    log('  编号  势力              城数   君主')
    log('  ' + '-' * 50)
    for i, fid in enumerate(flist, 1):
        n = sum(1 for a in (d.get('architectures') or {}).values()
                if str((a.get('info') or {}).get('faction')) == str(fid))
        inf = (facs[fid].get('info') or {})
        log('  [%3d] %s %3d    %s' % (i, _pad(_faction_label(d, fid), 16), n,
                                      inf.get('kingId') or ''))
    log('')
    log('  给哪个势力：输入编号 / Q=取消')
    try:
        t = input('  目标势力: ').strip()
    except EOFError:
        return
    if t.lower() == 'q' or not t.isdigit() or not (1 <= int(t) <= len(flist)):
        log('  已取消')
        return
    target = flist[int(t) - 1]
    srcs = {str((d['architectures'][k].get('info') or {}).get('faction')) for k in picked}
    log('')
    log('  即将把 %d 座城市交给 %s' % (len(picked), _faction_label(d, target)))
    for k in picked:
        log('     %s %s' % (_pad(_city_cn(k) or k, 12),
                           '(%s)' % _faction_label(d, str((d['architectures'][k].get('info') or {}).get('faction')))))
    log('')
    log('  城内太守/驻守武将怎么处理？')
    log('    [1] 留原势力，岗位清空（推荐，游戏会重新指派）')
    log('    [2] 跟着城市一起转给新势力')
    try:
        mv = input('  选择 [1]: ').strip() or '1'
    except EOFError:
        mv = '1'
    try:
        ok = input('  确认执行？(Y/N): ').strip().lower()
    except EOFError:
        ok = 'n'
    if ok not in ('y', 'yes', '\u662f'):
        log('  已取消，未写入')
        return
    backup_before_transfer(p)
    done, lines, warns = transfer_cities(d, picked, target, move_officers=(mv == '2'))
    if not done:
        log('  没有发生改动')
        for w in warns:
            log('     ' + w)
        return
    _write_save_json(p, sav, d)
    log('')
    log('  已转移 %d 城：' % done)
    for l in lines:
        log(l)
    for w in warns:
        log(w)
    probs = check_map(d)
    log('')
    if probs:
        log('  \u26a0 仍有 %d 项一致性问题：' % len(probs))
        for x in probs[:10]:
            log('     ' + x)
    else:
        log('  \u2713 自检通过')
    log('')
    log('  \u26a0 记得：退出到主菜单 → 重新载入该存档才生效（别中途存档）')


def _sha1(path, limit=None):
    import hashlib
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _in_real_saves(path):
    """只对真实游戏存档目录自动快照；测试用的临时目录不参与"""
    try:
        a = os.path.dirname(os.path.abspath(path)).lower()
        b = os.path.abspath(_SAVES_DEFAULT).lower()
        return a == b
    except Exception:
        return False


def _size_text(n):
    if n >= 1 << 20:
        return '%.1fM' % (n / 1048576.0)
    return '%dK' % (n // 1024)


def _short(text, width):
    text = str(text)
    if len(text) <= width:
        return text
    return text[:max(1, width - 3)] + '...'


def list_snapshots(only=None):
    """列出 history 里的快照，按时间倒序。文件名格式: 存档名~YYYYmmdd-HHMMSS~备注.sav"""
    out = []
    if not os.path.isdir(HISTORY_DIR):
        return out
    for n in os.listdir(HISTORY_DIR):
        if not n.lower().endswith('.sav'):
            continue
        parts = n[:-4].split('~')
        if len(parts) < 3:
            continue
        base, stamp, note = parts[0], parts[1], parts[2]
        target = base + '.sav'
        if only and str(target).lower() != str(only).lower():
            continue
        p = os.path.join(HISTORY_DIR, n)
        try:
            st = os.stat(p)
        except Exception:
            continue
        try:
            t = time.mktime(time.strptime(stamp, '%Y%m%d-%H%M%S'))
        except Exception:
            t = st.st_mtime
        try:
            h = _sha1(p)
        except Exception:
            h = ''
        out.append(dict(file=n, path=p, target=target, note=note,
                        time=t, size=st.st_size, sha1=h))
    out.sort(key=lambda x: (x['time'], x['file']), reverse=True)
    return out


def _hist_cleanup():
    """每个存档只保留最近 HIST_KEEP 份"""
    seen, drop = {}, []
    for s in list_snapshots():
        k = s['target']
        seen[k] = seen.get(k, 0) + 1
        if seen[k] > HIST_KEEP:
            drop.append(s)
    for s in drop:
        try:
            os.remove(s['path'])
        except Exception:
            pass
    return len(drop)


def snapshot_save(path, note='snap'):
    """把存档当前内容存进工具自己的 history 目录。内容相同则不重复存。"""
    try:
        if not os.path.exists(path):
            return None
        os.makedirs(HISTORY_DIR, exist_ok=True)
        target = os.path.basename(path)
        base = target[:-4] if target.lower().endswith('.sav') else target

        want = _sha1(path)
        prev = list_snapshots(target)
        if prev and prev[0]['sha1'] == want:
            return prev[0]['path']          # 内容没变，不重复占空间

        stamp = time.strftime('%Y%m%d-%H%M%S')
        note = ''.join(c for c in str(note or 'snap')
                       if c.isalnum() or c in '-_')[:16] or 'snap'
        dst = os.path.join(HISTORY_DIR, '%s~%s~%s.sav' % (base, stamp, note))
        i = 2
        while os.path.exists(dst):
            dst = os.path.join(HISTORY_DIR, '%s~%s~%s_%d.sav' % (base, stamp, note, i))
            i += 1
        shutil.copy2(path, dst)
        os.utime(dst, (time.time(), time.time()))   # 快照时间 = 现在（copy2 会保留旧时间）
        flog('snapshot: %s' % os.path.basename(dst))
        _hist_cleanup()
        return dst
    except Exception as e:
        flog('snapshot failed: %s' % e)
        return None


def backup_before_transfer(path):
    """兼容旧调用：转移前打一份快照"""
    return snapshot_save(path, 'pre_transfer')


def migrate_old_snapshots():
    """把旧版放在存档目录里的 存档.sav.before_xxx_MMDD_HHMMSS 搬进 history，
    免得它们混在游戏的存档列表里。返回搬运份数。"""
    n = 0
    if not os.path.isdir(SAVES_DIR):
        return n
    for name in list(os.listdir(SAVES_DIR)):
        if '.before_' not in name:
            continue
        src = os.path.join(SAVES_DIR, name)
        if not os.path.isfile(src):
            continue
        head, tail = name.split('.before_', 1)
        target = head
        base = target[:-4] if target.lower().endswith('.sav') else target
        # 从 xxx_1025_192324 里取时间戳
        stamp = None
        bits = tail.rsplit('_', 2)
        if (len(bits) == 3 and len(bits[1]) == 4 and len(bits[2]) == 6
                and bits[1].isdigit() and bits[2].isdigit()):
            stamp = '%d%s-%s' % (time.localtime().tm_year, bits[1], bits[2])
        note = 'old_' + (bits[0] if bits else 'snap')
        note = ''.join(c for c in note if c.isalnum() or c in '-_')[:16]
        if not stamp:
            stamp = time.strftime('%Y%m%d-%H%M%S', time.localtime(os.path.getmtime(src)))
        try:
            os.makedirs(HISTORY_DIR, exist_ok=True)
            dst = os.path.join(HISTORY_DIR, '%s~%s~%s.sav' % (base, stamp, note))
            i = 2
            while os.path.exists(dst):
                dst = os.path.join(HISTORY_DIR,
                                   '%s~%s~%s_%d.sav' % (base, stamp, note, i))
                i += 1
            shutil.move(src, dst)
            n += 1
        except Exception as e:
            flog('migrate snapshot failed: %s' % e)
    if n:
        flog('migrated %d old snapshots -> history' % n)
        log('  [i] 已把 %d 份旧快照从存档目录搬进 history（不再干扰游戏存档列表）' % n)
    return n


def _history_groups():
    """{存档名: {'snaps': [...], 'orig': 路径或None}}，只含当前存档目录里还存在的档"""
    exist = set()
    if os.path.isdir(SAVES_DIR):
        exist = {n for n in os.listdir(SAVES_DIR) if n.lower().endswith('.sav')}
    g = {}
    for sn in list_snapshots():
        if sn['target'] not in exist:
            continue
        g.setdefault(sn['target'], {'snaps': [], 'orig': None})['snaps'].append(sn)
    if os.path.isdir(BACKUP_DIR):
        for n in os.listdir(BACKUP_DIR):
            if not n.lower().endswith('.orig'):
                continue
            tgt = n[:-5]
            if tgt not in exist:
                continue
            g.setdefault(tgt, {'snaps': [], 'orig': None})['orig'] = os.path.join(BACKUP_DIR, n)
    return g


def _pick_save_for_undo(g):
    """两段式第一步：选存档。返回存档名或 None"""
    names = sorted(g, key=lambda k: -max([x['time'] for x in g[k]['snaps']] or [0]))
    if len(names) == 1:
        return names[0]
    log('')
    log('  %-4s %s %6s %6s' % ('编号', _pad('存档', 38), '快照', '原始档'))
    log('  ' + '-' * 64)
    for i, n in enumerate(names, 1):
        log('  [%3d] %s %4d   %s' %
            (i, _pad(_short(n, 36), 38), len(g[n]['snaps']),
             '有' if g[n]['orig'] else '-'))
    log('')
    log('  输入编号 = 选这个存档      Q = 取消')
    try:
        raw = input('  选择: ').strip()
    except EOFError:
        raw = 'q'
    if raw.lower() in ('q', ''):
        return None
    try:
        i = int(raw)
    except Exception:
        log('  输入无效')
        return None
    if not (1 <= i <= len(names)):
        log('  编号超出范围')
        return None
    return names[i - 1]


def undo_transfer(only=None):
    """回滚：先选存档，再选版本（history 快照 或 工具首次改动前的原始档）"""
    g = _history_groups()
    if only:
        base = os.path.basename(str(only))
        g = {k: v for k, v in g.items() if k.lower() == base.lower()}
    if not g:
        log('')
        log('  没有可回滚的记录。')
        log('  快照目录: %s' % HISTORY_DIR)
        log('  原始备份: %s' % BACKUP_DIR)
        log('  （从现在起每次改档前都会自动存一份到 history）')
        if _PORTABLE:
            gbak = os.path.join(LOCAL, APP_NAME, 'backup')
            if os.path.isdir(gbak) and os.listdir(gbak):
                log('')
                log('  提示：这是便携版，用的是自己目录里的 history（现在是空的）。')
                log('  你机器上正式安装的备份在: %s' % gbak)
                log('  要用那些备份，请运行安装目录里的程序，不是解压包里的。')
        return False

    target = _pick_save_for_undo(g)
    if not target:
        log('  已取消')
        return False

    rows = [('快照', sn) for sn in g[target]['snaps']]
    if g[target]['orig']:
        o = g[target]['orig']
        st = os.stat(o)
        rows.append(('原始档', dict(file=os.path.basename(o), path=o, target=target,
                                   note='工具首次改动前', time=st.st_mtime,
                                   size=st.st_size)))
    if not rows:
        log('  这个存档没有历史记录')
        return False

    log('')
    log('  存档: %s' % target)
    log('  %-4s %-6s %-16s %8s  %s' % ('编号', '类型', '时间', '大小', '备注'))
    log('  ' + '-' * 72)
    for i, (kind, sn) in enumerate(rows, 1):
        log('  [%3d] %s %s %8s  %s'
            % (i, _pad(kind, 5),
               time.strftime('%m-%d %H:%M:%S', time.localtime(sn['time'])),
               _size_text(sn['size']), _short(sn['note'], 18)))
    log('')
    log('  列表按时间倒序（1 = 最近一份）；"原始档" = 工具第一次改动前')
    log('  输入编号 = 回滚到这一份      Q = 取消')
    try:
        raw = input('  选择: ').strip()
    except EOFError:
        raw = 'q'
    if raw.lower() in ('q', ''):
        log('  已取消')
        return False
    try:
        idx = int(raw)
    except Exception:
        log('  输入无效')
        return False
    if not (1 <= idx <= len(rows)):
        log('  编号超出范围')
        return False

    kind, sn = rows[idx - 1]
    dst = os.path.join(SAVES_DIR, target)
    log('')
    log('  回滚到 : %s' % target)
    log('  来源   : %s（%s）' % (kind, time.strftime('%m-%d %H:%M:%S',
                                              time.localtime(sn['time']))))
    if os.path.exists(dst):
        log('  当前内容会先存一份新快照，随时能再退回来')
    try:
        ok = input('  确认回滚？(Y/N): ').strip().lower()
    except EOFError:
        ok = 'n'
    if ok not in ('y', 'yes', '是'):
        log('  已取消')
        return False

    try:
        if os.path.exists(dst):
            snapshot_save(dst, 'before_restore')
        shutil.copy2(sn['path'], dst)
        os.utime(dst, (time.time(), time.time()))    # 让游戏认它是"最新"
        log('')
        log('  ✓ 已回滚: %s' % target)
        log('  进游戏 → 载入这个存档即可（别再中途存档）')
        flog('undo: %s <= %s (%s)' % (target, sn['file'], kind))
        return True
    except Exception as e:
        log('  ✗ 回滚失败: %s' % e)
        return False


def show_history(only=None):
    """只看不还原：每个存档手上有几个版本"""
    g = _history_groups()
    if only:
        base = os.path.basename(str(only))
        g = {k: v for k, v in g.items() if k.lower() == base.lower()}
    if not g:
        log('')
        log('  还没有任何历史快照。')
        log('  快照目录: %s' % HISTORY_DIR)
        return
    log('')
    log('  %-4s %s %6s %6s %s' % ('编号', _pad('存档', 38), '快照', '原始档', '最新'))
    log('  ' + '-' * 80)
    total = 0
    for i, n in enumerate(sorted(g, key=lambda k: -max([x['time'] for x in g[k]['snaps']] or [0])), 1):
        snaps = g[n]['snaps']
        total += len(snaps)
        newest = time.strftime('%m-%d %H:%M', time.localtime(snaps[0]['time'])) if snaps else '-'
        log('  [%3d] %s %4d   %s   %s'
            % (i, _pad(_short(n, 36), 38), len(snaps),
               '有' if g[n]['orig'] else ' - ', newest))
    log('')
    log('  history 共 %d 份快照，每个存档最多留 %d 份' % (total, HIST_KEEP))
    log('  回滚: M → 6    或    launcher.cmd --undo-transfer')


def _existing_saves():
    """当前存档目录里的存档名集合；目录不可用时返回 None（此时不做任何判断）"""
    if not os.path.isdir(SAVES_DIR):
        return None
    return {n for n in os.listdir(SAVES_DIR) if n.lower().endswith('.sav')}


def _orphan_targets():
    """本地有副本、但游戏里已经没有这个存档了"""
    exist = _existing_saves()
    if exist is None:
        return []
    known = set(sn['target'] for sn in list_snapshots())
    if os.path.isdir(BACKUP_DIR):
        for n in os.listdir(BACKUP_DIR):
            if n.lower().endswith(('.orig', '.applied')):
                known.add(n.rsplit('.', 1)[0])
    return sorted(t for t in known if t not in exist)


def _merge_roster(target):
    """把某个存档 .orig 里的武将键并入 backup 目录下 _roster_merged.txt
    （.orig 被清走后，仍然认得哪些武将原本就有）"""
    src = os.path.join(BACKUP_DIR, target + '.orig')
    if not os.path.exists(src):
        return
    try:
        d = json.loads(read_sav(src)['body'].decode('utf-8'))
        keys = set((d.get('personages') or {}).keys())
    except Exception:
        return
    if not keys:
        return
    dst = os.path.join(BACKUP_DIR, '_roster_merged.txt')
    old = set()
    if os.path.exists(dst):
        try:
            with open(dst, encoding='utf-8') as f:
                old = {x.strip() for x in f if x.strip()}
        except Exception:
            pass
    add = keys - old
    if not add:
        return
    try:
        with open(dst, 'a', encoding='utf-8') as f:
            for k in sorted(add):
                f.write(str(k) + '\n')
        flog('roster merged: +%d keys from %s' % (len(add), target))
    except Exception as e:
        flog('roster merge failed: %s' % e)


def reap_target(target, with_backup=True):
    """把某个已删除存档的本地副本移进回收站（不直接删，留 7 天反悔期）

    with_backup=False 时只清历史快照，不动 backup 里的 .orig／.applied ——
    自动清理用这个模式，万一误判也不会丢掉原始备份。
    """
    day = os.path.join(TRASH_DIR, time.strftime('%Y%m%d'))
    moved = 0
    for sn in list_snapshots(target):
        try:
            os.makedirs(day, exist_ok=True)
            shutil.move(sn['path'], os.path.join(day, sn['file']))
            moved += 1
        except Exception as e:
            flog('reap snapshot failed: %s' % e)
    if with_backup and os.path.isdir(BACKUP_DIR):
        _merge_roster(target)          # 先把原版武将名录存下来，别随备份一起丢
        for suf in ('.orig', '.applied'):
            p = os.path.join(BACKUP_DIR, target + suf)
            if os.path.exists(p):
                try:
                    os.makedirs(day, exist_ok=True)
                    shutil.move(p, os.path.join(day, os.path.basename(p)))
                    moved += 1
                except Exception as e:
                    flog('reap backup failed: %s' % e)
    if moved:
        flog('reaped %d local copies of deleted save: %s' % (moved, target))
    return moved


def purge_trash(days=None):
    """回收站里超过 N 天的日期文件夹整个删掉"""
    days = TRASH_KEEP_DAYS if days is None else days
    if not os.path.isdir(TRASH_DIR):
        return 0
    cut = time.time() - days * 86400
    n = 0
    for d in os.listdir(TRASH_DIR):
        p = os.path.join(TRASH_DIR, d)
        if not os.path.isdir(p):
            continue
        try:
            t = time.mktime(time.strptime(d, '%Y%m%d'))
        except Exception:
            try:
                t = os.path.getmtime(p)
            except Exception:
                continue
        if t < cut:
            try:
                shutil.rmtree(p)
                n += 1
            except Exception as e:
                flog('purge trash failed: %s' % e)
    if n:
        flog('purged %d trash day(s)' % n)
    return n


def reap_orphans(verbose=False, with_backup=False):
    """扫一遍：存档已删除的本地副本 -> 回收站；顺手清过期回收站

    with_backup 默认 False：自动清理只动历史快照，原始备份留给手动 --cleanup
    """
    targets = _orphan_targets()
    total = 0
    for t in targets:
        m = reap_target(t, with_backup=with_backup)
        total += m
        if verbose and m:
            log('  %s  -> 回收站（%d 份）' % (_short(t, 40), m))
    purge_trash()
    if total:
        flog('reap orphans: %d copies from %d deleted save(s)'
             % (total, len(targets)))
    return total, len(targets)


def cleanup_ui():
    """菜单/命令行用：清掉已删除存档的本地副本"""
    targets = _orphan_targets()
    if not targets:
        n = purge_trash()
        log('')
        log('  没有需要清理的：本地副本和游戏里的存档一一对应')
        if n:
            log('  回收站清掉了 %d 个过期日期文件夹' % n)
        return
    log('')
    log('  这些存档在游戏里已经不在了，但本地还留着副本：')
    for t in targets[:20]:
        log('     %s' % _short(t, 56))
    if len(targets) > 20:
        log('     ...（共 %d 个）' % len(targets))
    log('')
    log('  会把它们的快照和原始备份移进:')
    log('     %s' % TRASH_DIR)
    log('  %d 天后自动彻底删除（期间想找回，直接去这个目录拿）' % TRASH_KEEP_DAYS)
    log('')
    try:
        ans = input('  确认清理？(Y/N): ').strip().lower()
    except EOFError:
        ans = 'n'
    if ans not in ('y', 'yes', '是'):
        log('  已取消')
        return
    total, cnt = reap_orphans(verbose=True, with_backup=True)
    purge_trash()
    log('')
    log('  ✓ 已清理 %d 份副本（涉及 %d 个已删除存档）' % (total, cnt))


def audit_save(only=None, verbose=True):
    """存档结构审计：把"原版从不出现的状态"全找出来。

    返回 (errors, warnings)
      errors   一定会导致崩溃/卡死的硬性问题
      warnings 与原版基线偏离的统计类问题（数量暴增等）
    """
    name = only or newest_save()
    if not name:
        if verbose:
            log('  没有存档')
        return 1, []
    p = name if os.path.isabs(name) else os.path.join(SAVES_DIR, name)
    try:
        sav = read_sav(p)
        d = json.loads(sav['body'].decode('utf-8'))
    except Exception as e:
        if verbose:
            log('  读档失败: %s' % e)
        return 1, []

    arch = d.get('architectures') or {}
    facs = d.get('factions') or {}
    ppl = d.get('personages') or {}
    low = {k.lower(): k for k in arch}
    flow = {str(k).lower() for k in facs}
    plo = {str(k).lower(): k for k in ppl}
    err = []
    stat = {'prefect_mismatch': 0, 'stray': 0, 'food_arch_foreign': 0,
            'stratagem_foreign': 0}

    def own(a):
        return str((a.get('info') or {}).get('faction'))

    # ---------- A1 势力：存活者必须有城、有有效首都 ----------
    for fid, f in facs.items():
        if f.get('bDestroyed'):
            continue
        cities = [k for k, a in arch.items() if own(a).lower() == str(fid).lower()]
        if not cities:
            err.append('势力 %s 没有任何城市（存活却 0 城）' % fid)
            continue
        cap = str((f.get('info') or {}).get('capitalId') or 'None')
        ck = low.get(cap.lower())
        if ck is None:
            err.append('势力 %s 的首都 %s 不存在' % (fid, cap))
        elif own(arch[ck]).lower() != str(fid).lower():
            err.append('势力 %s 的首都 %s 属于 %s' % (fid, cap, own(arch[ck])))

    # ---------- A2 皇帝必须健在 ----------
    emp = d.get('empire') or {}
    eid = str(((emp.get('info') or {}).get('emperorId')) or 'None')
    if eid != 'None':
        f = facs.get(eid)
        if f is None:
            err.append('皇帝 %s 不在势力表里' % eid)
        elif f.get('bDestroyed'):
            err.append('皇帝 %s 已被标记灭亡' % eid)
        elif not [k for k, a in arch.items() if own(a).lower() == eid.lower()]:
            err.append('皇帝 %s 没有任何城市' % eid)

    # ---------- A3 成对字段：staffId=None -> staffAccTime 必须 0 ----------
    for k, a in arch.items():
        pu = a.get('prefecturalUnit') or {}
        if str(pu.get('staffId') or 'None') == 'None' and int(pu.get('staffAccTime') or 0) != 0:
            err.append('%s 无太守但 staffAccTime=%s（必崩）' % (k, pu.get('staffAccTime')))
        for u in (a.get('areaUnitList') or []):
            if str(u.get('staffId') or 'None') == 'None' and int(u.get('staffAccTime') or 0) != 0:
                err.append('%s 建筑 %s 无驻守但 staffAccTime=%s' % (k, u.get('unitId'), u.get('staffAccTime')))

    # ---------- A4 城市岗位武将必须存在且属于本城势力 ----------
    for k, a in arch.items():
        o = own(a).lower()
        inf = a.get('info') or {}
        ids = []
        pre = str(inf.get('prefectId') or 'None')
        if pre != 'None':
            ids.append(pre)
        pu = a.get('prefecturalUnit') or {}
        s1 = str(pu.get('staffId') or 'None')
        if s1 != 'None':
            ids.append(s1)
        for u in (a.get('areaUnitList') or []):
            s2 = str(u.get('staffId') or 'None')
            if s2 != 'None':
                ids.append(s2)
        for pid in ids:
            real = plo.get(pid.lower())
            if real is None:
                err.append('%s 的岗位武将 %s 不存在' % (k, pid))
            else:
                pf = str((ppl[real].get('info') or {}).get('faction')).lower()
                if pf != o:
                    stat['prefect_mismatch'] += 1

    # ---------- A5 武将居住地 ----------
    stray = 0
    for pid, per in ppl.items():
        inf = per.get('info') or {}
        fac = str(inf.get('faction'))
        arc = str(inf.get('architecture') or 'None')
        if fac in ('None', 'none', '') or arc in ('None', 'none', ''):
            continue
        ck = low.get(arc.lower())
        if ck is None:
            err.append('武将 %s 的居住城 %s 不存在' % (pid, arc))
            continue
        if own(arch[ck]).lower() != fac.lower():
            stat['stray'] += 1

    # ---------- A6 城市 AI 目标不能指向自己 ----------
    for k, a in arch.items():
        ai = a.get('architectureAI') or {}
        t = str(ai.get('readyAttackTargetArchitecture') or 'None')
        if t == 'None':
            continue
        tk = low.get(t.lower())
        if tk is None:
            err.append('%s 的 AI 目标城 %s 不存在' % (k, t))
        elif own(arch[tk]).lower() == own(a).lower():
            err.append('%s 的 AI 在攻击自己的城 %s' % (k, t))

    # ---------- A7 势力级"指向城市"的引用 ----------
    for fid, f in facs.items():
        if f.get('bDestroyed'):
            continue
        me = str(fid).lower()
        for fld in ('priorityFoodArch', 'stratagemCity', 'stratagemTargetCity',
                    'requestSupportArchitectureId'):
            v = str(f.get(fld) or 'None')
            if v == 'None':
                continue
            ck = low.get(v.lower())
            if ck is None:
                err.append('势力 %s 的 %s=%s 指向不存在的城' % (fid, fld, v))
            elif own(arch[ck]).lower() != me:
                # 计略/求援指向别国是正常的；"优先粮食城"指向别国才是问题
                if fld == 'priorityFoodArch':
                    stat['food_arch_foreign'] += 1
                else:
                    stat['stratagem_foreign'] += 1

    # ---------- A7b 灭亡势力：帝国/外交里不能还挂着它 ----------
    dead = {fid for fid, f in facs.items() if f.get('bDestroyed')}
    if dead:
        einfo = (emp.get('info') or {}) if isinstance(emp, dict) else {}
        for key in ('seigneurIds', 'independentIds', 'rebellionFactionIds'):
            for x in (einfo.get(key) or []):
                if str(x) in dead:
                    err.append('帝国 %s 里仍挂着已灭亡势力 %s' % (key, x))
        if str(einfo.get('regentId')) in dead:
            err.append('帝国 regentId 指向已灭亡势力 %s' % einfo.get('regentId'))
        if str(einfo.get('rebukeFactionId')) in dead:
            err.append('帝国 rebukeFactionId 指向已灭亡势力 %s' % einfo.get('rebukeFactionId'))
        for fid in sorted(dead):
            cities = [k for k, a in arch.items() if own(a).lower() == str(fid).lower()]
            if not cities:
                err.append('势力 %s 已被标记灭亡却仍占着 %d 座城（原版没有这种状态）'
                           % (fid, len(cities)) if cities else
                           '势力 %s 被标记灭亡（需确认游戏能处理）' % fid)
        # 存活势力的关系里不该再出现灭亡势力
        for fid, f in facs.items():
            if f.get('bDestroyed'):
                continue
            for key in ('revengeLst', 'improveFactionIds', 'donateFactions'):
                for x in (f.get(key) or []):
                    if str(x) in dead:
                        err.append('势力 %s 的 %s 引用了已灭亡势力 %s' % (fid, key, x))

    # ---------- A8 部队将领必须存在 ----------
    for fid, f in facs.items():
        for tid, t in (f.get('troops') or {}).items():
            for g in ('generalId1', 'generalId2', 'generalId3'):
                v = str(t.get(g) or 'None')
                if v != 'None' and v.lower() not in plo:
                    err.append('部队 %s 的 %s=%s 武将不存在' % (tid, g, v))

    stray = stat['stray']

    # ---------- B 与原版基线对比 ----------
    warn = []
    base = {'stray': 0, 'prefect_mismatch': 0, 'food_arch_foreign': 0,
            'stratagem_foreign': 0, 'zero': 0}
    n_orig = 0
    for d0 in (BACKUP_DIR,):
        if not os.path.isdir(d0):
            continue
        for n in os.listdir(d0):
            if not n.lower().endswith('.orig'):
                continue
            try:
                b = json.loads(read_sav(os.path.join(d0, n))['body'].decode('utf-8'))
            except Exception:
                continue
            n_orig += 1
            ar = b.get('architectures') or {}
            fa = b.get('factions') or {}
            pp2 = b.get('personages') or {}
            lo2 = {k.lower(): k for k in ar}
            c = {}
            for v in ar.values():
                fid2 = str((v.get('info') or {}).get('faction')).lower()
                c[fid2] = c.get(fid2, 0) + 1
            base['zero'] += sum(1 for fid2 in fa
                                if c.get(str(fid2).lower(), 0) == 0
                                and not fa[fid2].get('bDestroyed'))
            for per in pp2.values():
                inf = per.get('info') or {}
                fac2 = str(inf.get('faction'))
                arc2 = str(inf.get('architecture') or 'None')
                if fac2 in ('None', 'none', '') or arc2 in ('None', 'none', ''):
                    continue
                ck = lo2.get(arc2.lower())
                if ck and str((ar[ck].get('info') or {}).get('faction')).lower() != fac2.lower():
                    base['stray'] += 1
            for fid2, f2 in fa.items():
                me2 = str(fid2).lower()
                for fld in ('priorityFoodArch', 'stratagemCity',
                            'stratagemTargetCity', 'requestSupportArchitectureId'):
                    v2 = str(f2.get(fld) or 'None')
                    if v2 == 'None':
                        continue
                    ck = lo2.get(v2.lower())
                    if ck is None:
                        continue
                    if str((ar[ck].get('info') or {}).get('faction')).lower() != me2:
                        if fld == 'priorityFoodArch':
                            base['food_arch_foreign'] += 1
                        else:
                            base['stratagem_foreign'] += 1
            # 岗位武将归属错配
            for k2, a2 in ar.items():
                o2 = str((a2.get('info') or {}).get('faction')).lower()
                pids2 = []
                pr2 = str((a2.get('info') or {}).get('prefectId') or 'None')
                if pr2 != 'None':
                    pids2.append(pr2)
                s2 = str((a2.get('prefecturalUnit') or {}).get('staffId') or 'None')
                if s2 != 'None':
                    pids2.append(s2)
                for u2 in (a2.get('areaUnitList') or []):
                    s3 = str(u2.get('staffId') or 'None')
                    if s3 != 'None':
                        pids2.append(s3)
                for pid2 in pids2:
                    real2 = {k.lower(): k for k in pp2}.get(pid2.lower())
                    if real2:
                        pf2 = str((pp2[real2].get('info') or {}).get('faction')).lower()
                        if pf2 != o2:
                            base['prefect_mismatch'] += 1
    if n_orig:
        avg = {k: v / float(n_orig) for k, v in base.items()}
        for key, label, mult in (
                ('stray', '武将住在非本势力城', 3),
                ('prefect_mismatch', '岗位武将归属错配', 3),
                ('food_arch_foreign', '优先粮食城指向别国', 1),
                ('stratagem_foreign', '计略/求援指向别国（正常，仅记录）', 100)):
            mine = stat.get(key, 0)
            lim = avg[key] * mult + 3
            if key == 'stratagem_foreign':
                continue
            if mine > lim:
                warn.append('%s：%d 处，原版平均 %.1f 处（%d 个原始档）'
                            % (label, mine, avg[key], n_orig))
        if base['zero'] == 0:
            zero_now = [f for f in facs
                        if not [k for k, a in arch.items()
                                if own(a).lower() == str(f).lower()]
                        and not facs[f].get('bDestroyed')]
            if zero_now:
                err.append('%d 个存活势力 0 城（原版存档里从不出现）' % len(zero_now))
    if stat['stray'] or stat['prefect_mismatch']:
        warn.append('明细: 武将住敌城 %d 处 / 岗位武将错配 %d 处 / 优先粮城越界 %d 处'
                    % (stat['stray'], stat['prefect_mismatch'],
                       stat['food_arch_foreign']))

    if verbose:
        log('')
        log('  存档: %s' % name)
        log('  城市 %d / 势力 %d / 武将 %d' % (len(arch), len(facs), len(ppl)))
        if err:
            log('  ✗ 硬性问题 %d 项:' % len(err))
            for e in err[:20]:
                log('     ' + e)
        else:
            log('  ✓ 硬性不变量全部通过')
        for w in warn:
            log('  ! ' + w)
        log('')
        log('  （检查项：势力有城/有首都、皇帝健在、staffId 与 staffAccTime 成对、')
        log('    岗位武将存在且属于本城、武将居住地、AI 不打自己城、势力级城市引用、部队将领存在）')
    return len(err), warn


def check_save_health(only=None):
    """存档健康检查：把可能导致游戏卡死的状态全查一遍"""
    name = only or newest_save()
    if not name:
        log('  没有存档')
        return
    p = name if os.path.isabs(name) else os.path.join(SAVES_DIR, name)
    d = _sav_json(read_sav(p))
    arch = d.get('architectures') or {}
    facs = d.get('factions') or {}
    low = {k.lower(): k for k in arch}
    owner = {k.lower(): str((a.get('info') or {}).get('faction')).lower() for k, a in arch.items()}
    cnt = {}
    for v in owner.values():
        cnt[v] = cnt.get(v, 0) + 1
    bad = []

    # bDestroyed=True 的势力本来就该 0 城，不算异常
    zero = [f for f in facs if cnt.get(str(f).lower(), 0) == 0
            and not facs[f].get('bDestroyed')]
    if zero:
        bad.append('零城势力 %d 个: %s（会卡死 AI）' % (len(zero), ', '.join(zero[:8])))
    dead_n = sum(1 for f in facs if facs[f].get('bDestroyed'))
    if dead_n:
        log('  （%d 个势力已灭亡，不计入风险）' % dead_n)
    for fid, f in facs.items():
        if f.get('bDestroyed'):
            continue
        cap = str((f.get('info') or {}).get('capitalId') or 'None')
        if cap == 'None':
            if cnt.get(str(fid).lower(), 0) > 0:
                bad.append('势力 %s 有城但首都为 None' % fid)
            continue
        ck = low.get(cap.lower())
        if ck is None:
            bad.append('势力 %s 首都 %s 不存在' % (fid, cap))
        elif owner[ck.lower()] != str(fid).lower():
            bad.append('势力 %s 首都 %s 不归自己' % (fid, cap))
    for fid, f in facs.items():
        me = str(fid).lower()
        for fld in ('priorityFoodArch', 'stratagemCity', 'stratagemTargetCity',
                    'requestSupportArchitectureId'):
            v = str(f.get(fld) or 'None')
            if v == 'None':
                continue
            ck = low.get(v.lower())
            if ck is None or owner[ck.lower()] != me:
                bad.append('势力 %s 的 %s 指向不属于自己的 %s' % (fid, fld, v))
        lst = f.get('autoBuildCityOrder') or []
        stale = [x for x in lst if str(x).lower() in low and owner[str(x).lower()] != me]
        if stale:
            bad.append('势力 %s 的建造队列含他人城市 %s' % (fid, stale[:3]))
    for k, a in arch.items():
        pu = a.get('prefecturalUnit') or {}
        if str(pu.get('staffId') or 'None') == 'None' and int(pu.get('staffAccTime') or 0) != 0:
            bad.append('%s 无太守但 staffAccTime=%s（读档会空指针崩退）'
                       % (k, pu.get('staffAccTime')))
        for u in (a.get('areaUnitList') or []):
            if str(u.get('staffId') or 'None') == 'None' and int(u.get('staffAccTime') or 0) != 0:
                bad.append('%s 建筑 %s 无驻守但 staffAccTime=%s'
                           % (k, u.get('unitId'), u.get('staffAccTime')))
    for k, a in arch.items():
        ai = a.get('architectureAI') or {}
        tgt = str(ai.get('readyAttackTargetArchitecture') or 'None')
        if tgt != 'None':
            tk = low.get(tgt.lower())
            if tk and owner[tk.lower()] == owner[k.lower()]:
                bad.append('%s 的 AI 在攻击自己的城 %s' % (k, tgt))
        sf = str(ai.get('supportFactionId') or 'None')
        if sf != 'None' and sf.lower() != owner[k.lower()]:
            bad.append('%s 向敌对势力 %s 请求支援' % (k, sf))
        fid = owner[k.lower()]
        if fid and fid != 'none' and fid not in {str(x).lower() for x in facs}:
            bad.append('%s 的归属势力 %s 不存在' % (k, fid))

    log('')
    log('  存档: %s' % os.path.basename(p))
    log('  城市 %d / 势力 %d' % (len(arch), len(facs)))
    if bad:
        log('  ⚠ 发现 %d 项风险:' % len(bad))
        for x in bad[:15]:
            log('     ' + x)
        log('')
        # 能就地修的直接修，不用再跑别的命令
        fixed = fix_save_health(d)
        if fixed:
            bak = p + '.before_healthfix_' + time.strftime('%m%d_%H%M%S')
            try:
                shutil.copy2(p, bak)
                _write_save_json(p, read_sav(p), d)
                log('  ✓ 已自动修复 %d 处，备份: %s' % (fixed, os.path.basename(bak)))
                log('    重新读档即可（当前存档已更新）')
            except Exception as e:
                log('  ✗ 自动修复写盘失败: %s' % e)
        else:
            log('  修复: --repair-annex   回滚: --undo-transfer')
    else:
        log('  ✓ 未发现会导致卡死的状态')
    return bad


def fix_save_health(d):
    """就地修复 check_save_health 能识别的问题，返回修复处数。

    目前覆盖：
      1) staffId=None 但 staffAccTime!=0（空指针崩退的头号原因）
      2) 建筑驻守同样成对清零
      3) 势力指向他人城市/不存在城市的引用
      4) 建造队列里的他人城市
    """
    arch = d.get('architectures') or {}
    facs = d.get('factions') or {}
    low = {k.lower(): k for k in arch}
    own = {k.lower(): str((a.get('info') or {}).get('faction')).lower()
           for k, a in arch.items()}
    n = 0
    for k, a in arch.items():
        ai = a.get('architectureAI')
        if isinstance(ai, dict):
            tgt = str(ai.get('readyAttackTargetArchitecture') or 'None')
            if tgt != 'None':
                tk = low.get(tgt.lower())
                if tk is None or own[tk.lower()] == own[k.lower()]:
                    ai['readyAttackTargetArchitecture'] = 'None'
                    ai['defenseState'] = 'None'
                    n += 1
    for k, a in arch.items():
        pu = a.get('prefecturalUnit') or {}
        if str(pu.get('staffId') or 'None') == 'None' and int(pu.get('staffAccTime') or 0) != 0:
            pu['staffAccTime'] = 0
            n += 1
        for u in (a.get('areaUnitList') or []):
            if str(u.get('staffId') or 'None') == 'None' and int(u.get('staffAccTime') or 0) != 0:
                u['staffAccTime'] = 0
                n += 1
    for fid, f in facs.items():
        me = str(fid).lower()
        for fld in ('priorityFoodArch', 'stratagemCity', 'stratagemTargetCity',
                    'requestSupportArchitectureId'):
            v = str(f.get(fld) or 'None')
            if v == 'None':
                continue
            ck = low.get(v.lower())
            if ck is None or own[ck.lower()] != me:
                f[fld] = 'None'
                n += 1
        lst = f.get('autoBuildCityOrder') or []
        if lst:
            keep = [x for x in lst
                    if str(x).lower() not in low or own[str(x).lower()] == me]
            if len(keep) != len(lst):
                f['autoBuildCityOrder'] = keep
                n += len(lst) - len(keep)
    if n:
        flog('health auto-fix: %d 处' % n)
    return n


def repair_annex(only=None, src=None):
    """把"被全吞并"的存档救回来：用另一个（吞并前的）存档恢复城市归属与太守。

    起因：把某势力的最后一座城转走会让游戏卡死（实测 31 个零城势力直接卡崩）。
    该游戏版本里没有任何 bDestroyed=True 的势力，说明不支持"势力灭亡"，
    所以只能把城还回去。
    """
    # 没指定目标：自动找"零城势力最多"的那个存档
    if not only:
        best = None
        for n in os.listdir(SAVES_DIR):
            if not n.lower().endswith('.sav'):
                continue
            try:
                d0 = _sav_json(read_sav(os.path.join(SAVES_DIR, n)))
            except Exception:
                continue
            cnt0 = {}
            for a in (d0.get('architectures') or {}).values():
                f = str((a.get('info') or {}).get('faction')).lower()
                cnt0[f] = cnt0.get(f, 0) + 1
            z = sum(1 for f in (d0.get('factions') or {})
                    if cnt0.get(str(f).lower(), 0) == 0)
            if z > 1 and (best is None or z > best[1]):
                best = (n, z)
        if not best:
            log('  没有发现"零城势力"异常的存档，不需要修复')
            log('  （只有 0~1 个零城势力属于游戏正常状态）')
            return False
        only = best[0]
        log('  自动选中: %s（零城势力 %d 个）' % (only, best[1]))
    tp = only if os.path.isabs(only) else os.path.join(SAVES_DIR, only)
    if not src:
        # 自动挑一个最接近的：同目录下 tick 最接近且非零城势力最少的
        cands = []
        d_t = _sav_json(read_sav(tp))
        t_tick = _header_tick(read_sav(tp))
        for n in os.listdir(SAVES_DIR):
            if not n.lower().endswith('.sav') or n == os.path.basename(tp):
                continue
            p2 = os.path.join(SAVES_DIR, n)
            try:
                d2 = _sav_json(read_sav(p2))
                tick2 = _header_tick(read_sav(p2))
            except Exception:
                continue
            cnt = {}
            for a in (d2.get('architectures') or {}).values():
                f = str((a.get('info') or {}).get('faction')).lower()
                cnt[f] = cnt.get(f, 0) + 1
            zero = sum(1 for f in (d2.get('factions') or {})
                       if cnt.get(str(f).lower(), 0) == 0)
            cands.append((zero, abs(tick2 - t_tick), n))
        if not cands:
            log('  找不到可用的对照存档，请用 --from 指定')
            return False
        cands.sort()
        src = cands[0][2]
        log('  自动选用对照档: %s（零城势力 %d 个）' % (src, cands[0][0]))
    sp = src if os.path.isabs(src) else os.path.join(SAVES_DIR, src)
    if not os.path.exists(sp):
        log('  对照存档不存在: %s' % sp)
        return False

    sav_t = read_sav(tp)
    d_t = _sav_json(sav_t)
    d_s = _sav_json(read_sav(sp))
    arch_t = d_t.get('architectures') or {}
    arch_s = d_s.get('architectures') or {}
    fac_t = d_t.get('factions') or {}
    fac_s = d_s.get('factions') or {}

    # 先备份当前状态（.orig 是历史原档，不能覆盖，另存一份）
    stamp = time.strftime('%m%d_%H%M%S')
    safe = tp + '.before_repair_' + stamp
    shutil.copy2(tp, safe)

    fixed = 0
    offs = 0
    for key, a_s in arch_s.items():
        a_t = arch_t.get(key)
        if not a_t:
            continue
        si = a_s.get('info') or {}
        ti = a_t.setdefault('info', {})
        src_fid = str(si.get('faction'))
        if str(ti.get('faction')) != src_fid:
            ti['faction'] = src_fid
            fixed += 1
        if 'lastFactionName' in a_s:
            a_t['lastFactionName'] = a_s.get('lastFactionName')
        # 太守
        pre_s = si.get('prefectId') or 'None'
        if str(ti.get('prefectId')) != str(pre_s):
            ti['prefectId'] = pre_s
        # 郡治单位
        pu_t = a_t.get('prefecturalUnit')
        pu_s = a_s.get('prefecturalUnit')
        if isinstance(pu_t, dict) and isinstance(pu_s, dict):
            if pu_s.get('staffId') and pu_t.get('staffId') != pu_s.get('staffId'):
                pu_t['staffId'] = pu_s['staffId']
                offs += 1
        # 城内建筑驻守
        au_t = a_t.get('areaUnitList')
        au_s = a_s.get('areaUnitList')
        if isinstance(au_t, list) and isinstance(au_s, list):
            smap = {}
            for u in au_s:
                if isinstance(u, dict) and u.get('unitId'):
                    smap[u['unitId']] = u.get('staffId')
            for u in au_t:
                if not isinstance(u, dict):
                    continue
                want = smap.get(u.get('unitId'))
                if want and u.get('staffId') != want:
                    u['staffId'] = want
                    offs += 1

    # 武将归属对齐：城里的太守/驻守武将，必须属于该城所属势力
    persons, plow = _person_index(d_t)
    aligned = 0
    for key, a_t in arch_t.items():
        ti = a_t.get('info') or {}
        fid = str(ti.get('faction'))
        if fid in ('None', ''):
            continue
        pids = []
        pre = str(ti.get('prefectId') or 'None')
        if pre != 'None':
            pids.append(pre)
        for u in (a_t.get('areaUnitList') or []):
            sid = str((u or {}).get('staffId') or 'None')
            if sid != 'None':
                pids.append(sid)
        for pid in pids:
            real = _find_person(persons, plow, pid)
            per = persons.get(real) if real else None
            if not isinstance(per, dict):
                continue
            pi = per.setdefault('info', {})
            if str(pi.get('faction')) != fid:
                pi['faction'] = fid
                aligned += 1

    # 首都
    cap_fixed = 0
    for fid, f_s in fac_s.items():
        f_t = fac_t.get(fid)
        if not isinstance(f_t, dict):
            continue
        cap_s = (f_s.get('info') or {}).get('capitalId')
        if not cap_s or str(cap_s) == 'None':
            continue
        ti = f_t.setdefault('info', {})
        if str(ti.get('capitalId')) != str(cap_s):
            ti['capitalId'] = cap_s
            cap_fixed += 1

    _write_save_json(tp, sav_t, d_t)

    log('')
    log('  修复: %s' % os.path.basename(tp))
    log('  对照: %s' % os.path.basename(sp))
    log('  改回归属   : %d 城' % fixed)
    log('  恢复岗位   : %d 处' % offs)
    log('  武将改回原势力: %d 人' % aligned)
    log('  修正首都   : %d 个势力' % cap_fixed)
    log('  修复前备份 : %s' % os.path.basename(safe))
    probs = check_map(d_t)
    real = [x for x in probs if '没有任何城市' not in x]
    log('')
    if real:
        log('  \u26a0 仍有 %d 项一致性问题:' % len(real))
        for x in real[:8]:
            log('     ' + x)
    else:
        log('  \u2713 归属一致性检查通过')
    if probs:
        log('  \u26a0 还有 %d 个零城势力（游戏可能会卡）' % len(probs))
    return True


def transfer_cli(only=None, city_arg=None, to=None, move_officers=False):
    """命令行批量转移：城市 key 逗号分隔"""
    name = only or newest_save()
    if not name:
        log('没有存档')
        return
    p = name if os.path.isabs(name) else os.path.join(SAVES_DIR, name)
    sav = read_sav(p)
    d = _sav_json(sav)
    arch = d.get('architectures') or {}
    low = {k.lower(): k for k in arch}
    if not city_arg or not to:
        log('用法: --transfer-city "luoYang,xuChang" --to 43 [--only 存档]')
        return
    keys, bad = [], []
    for tok in city_arg.replace('\uff0c', ',').split(','):
        tok = tok.strip()
        if not tok:
            continue
        ck = low.get(tok.lower())
        if ck:
            keys.append(ck)
        else:
            bad.append(tok)
    if bad:
        log('  找不到城市: %s' % ', '.join(bad))
    if not keys:
        return
    backup_before_transfer(p)
    done, lines, warns = transfer_cities(d, keys, to, move_officers=move_officers,
                                          keep_one=('--allow-empty' not in sys.argv))
    if done:
        _write_save_json(p, sav, d)
    log('  存档: %s' % os.path.basename(p))
    log('  已转移 %d 城 -> %s' % (done, _faction_label(d, to)))
    for l in lines:
        log(l)
    for w in warns:
        log(w)


def find_custom(only=None):
    """列出当前存档里"像自建武将"的人（按结构性特征判定）"""
    name = only or newest_save()
    if not name:
        log('存档目录里没有 .sav 文件')
        return
    path = os.path.join(SAVES_DIR, name)
    if not os.path.exists(path):
        log('找不到存档: ' + name)
        return
    d = json.loads(read_sav(path)['body'].decode('utf-8'))
    fid = _player_fid(d)
    roster = _known_roster()
    log('')
    log('  存档: %s' % name)
    log('  原版名录: %d 人（来自 backup 里的 .orig 备份）' % len(roster))
    log('  本档武将: %d 人' % len(d.get('personages') or {}))
    if not roster:
        log('  ⚠ 还没有原始备份，无法比对名录')
    hits = []
    for pid, per in (d.get('personages') or {}).items():
        strong, why = _custom_reasons(pid, per, fid, roster)
        if strong:
            bi = per.get('baseInfo') or {}
            inf = per.get('info') or {}
            hits.append((pid, inf.get('faction'), why,
                         [bi.get(k) for k in STAT_KEYS]))
    log('')
    if not hits:
        log('  没发现自建武将（也可能是新建的那个还没存档）')
        return
    hits.sort(key=lambda x: -sum(v for v in x[3] if isinstance(v, int)))
    log('  疑似自建武将 %d 个：' % len(hits))
    log('  武将                势力   统/武/敏/智/政/魅          理由')
    log('  ' + '-' * 74)
    for pid, fac, why, vals in hits[:40]:
        log('  ★ %-18s %-6s %-24s %s'
            % (_pad(pid, 18), _pad(str(fac), 6),
               '/'.join('-' if v is None else str(v) for v in vals),
               '、'.join(why)))
    if len(hits) > 40:
        log('  ... 还有 %d 个' % (len(hits) - 40))


def _own_generals(d, fid):
    """本国在世武将 [(合计, pid, baseInfo)]，按合计降序。
    自建武将可能只带部分六维字段，这里"有多少算多少"，不整条跳过。"""
    rows = []
    for pid, per in (d.get('personages') or {}).items():
        inf = per.get('info') or {}
        if str(inf.get('faction', '')).lower() != str(fid).lower():
            continue
        if inf.get('tag1') in ('Death', 'Dead'):
            continue
        bi = per.get('baseInfo') or {}
        if not bi:
            continue
        have = [k for k in STAT_KEYS if k in bi]
        if not have:
            continue
        tot = 0
        for k in have:
            try:
                tot += int(bi[k])
            except Exception:
                pass
        rows.append((tot, pid, bi))
    rows.sort(key=lambda x: -x[0])
    return rows


def _stat_cell(bi, k):
    """列表里的单格；缺字段显示 '-'"""
    if k not in bi:
        return '   -'
    try:
        return '%4d' % int(bi[k])
    except Exception:
        return '%4s' % str(bi[k])[:4]


def custom_stats():
    """批量：设定 attr 模块的目标六维"""
    cfg = load_cfg()
    apply_caps(cfg)
    log('')
    log('  设置六维目标值（直接回车 = 保持不变，范围 1~%d）' % STAT_MAX)
    log('  这些值是给「武将六维」模块用的：应用到哪个存档由下一步决定')
    log('')
    for k in STAT_KEYS:
        try:
            raw = input('  %-6s [%d]: ' % (STAT_LABEL[k], STATS[k]))
        except EOFError:
            return
        raw = raw.strip().replace(',', '').replace('，', '')
        if not raw:
            continue
        try:
            STATS[k] = max(1, min(STAT_MAX, int(float(raw))))
        except Exception:
            log('    [忽略] 不是数字: ' + raw)
    cfg['stats'] = {k: STATS[k] for k in STAT_KEYS}
    save_cfg(cfg)
    log('')
    log('已保存目标值: ' + '  '.join('%s=%d' % (STAT_LABEL[k], STATS[k])
                                     for k in STAT_KEYS))


def edit_general(only=None):
    """单个武将：列出本国武将，按编号逐个改六维"""
    name = only or newest_save()
    if not name:
        log('存档目录里没有 .sav 文件')
        return
    path = os.path.join(SAVES_DIR, name)
    if not os.path.exists(path):
        log('找不到存档: ' + name)
        return

    while True:
        sav, d = _load_save_json(path)
        fid = _player_fid(d)
        if fid is None:
            log('这个存档里找不到玩家势力')
            return
        rows = _own_generals(d, fid)
        if not rows:
            log('本国没有可改的武将（可能都已阵亡或还没出场）')
            return

        log('')
        log('  存档: %s    势力: %s    武将 %d 人' % (name, fid, len(rows)))
        log('  编号  武将                统率 武力 敏捷 智力 政治 魅力  合计')
        log('  ' + '-' * 66)
        roster = _known_roster()
        for i, (tot, pid, bi) in enumerate(rows, start=1):
            mark = '★' if (roster and pid not in roster) else ' '
            log('   [%2d]%s%s %s %s %s %s %s %s  %4d'
                % (i, mark, _pad(pid, 18),
                   _stat_cell(bi, 'command'), _stat_cell(bi, 'strength'),
                   _stat_cell(bi, 'agility'), _stat_cell(bi, 'intelligence'),
                   _stat_cell(bi, 'politics'), _stat_cell(bi, 'charm'), tot))
        log('')
        log('  输入编号 = 改这个武将      A = 全部改成目标值(%s)      Q = 退出'
            % '/'.join(str(STATS[k]) for k in STAT_KEYS))
        try:
            c = input('  选择: ').strip()
        except EOFError:
            return
        low = c.lower()
        if low == 'q' or low == '':
            return

        if low == 'a':
            n = 0
            for tot, pid, bi in rows:
                for k in STAT_KEYS:
                    if k in bi:
                        _set(bi, k, STATS[k])
                n += 1
            _write_save_json(path, sav, d)
            log('')
            log('已把 %d 个武将的六维设为目标值并写入存档' % n)
            log('⚠ 需要重新读档才生效')
            continue

        if not c.isdigit() or not (1 <= int(c) <= len(rows)):
            log('  无效编号')
            continue

        tot, pid, bi = rows[int(c) - 1]
        log('')
        log('  正在改: %s  (当前 统率%d 武力%d 敏捷%d 智力%d 政治%d 魅力%d)'
            % (pid, bi['command'], bi['strength'], bi['agility'],
               bi['intelligence'], bi['politics'], bi['charm']))
        log('  直接回车 = 该项不改')
        changed = 0
        for k in STAT_KEYS:
            if k not in bi:
                log('    %-6s （该武将无此字段，跳过）' % STAT_LABEL[k])
                continue
            try:
                raw = input('    %-6s [%s]: ' % (STAT_LABEL[k], bi[k]))
            except EOFError:
                break
            raw = raw.strip().replace(',', '').replace('，', '')
            if not raw:
                continue
            try:
                v = max(1, min(STAT_MAX, int(float(raw))))
            except Exception:
                log('      [忽略] 不是数字')
                continue
            if _set(bi, k, v):
                changed += 1
        if changed:
            _write_save_json(path, sav, d)
            log('')
            log('已修改 %d 项并写入存档' % changed)
            log('⚠ 需要重新读档才生效')
        else:
            log('  没有改动')


def custom_caps():
    """交互式自定义目标数值"""
    cfg = load_cfg()
    apply_caps(cfg)
    log("当前目标数值（直接回车 = 保持不变）：")
    for k in ('money', 'conscription', 'food', 'tech', 'tactical', 'supply', 'troop'):
        try:
            raw = input("  %s [%s]: " % (CAP_LABEL[k], format(CAPS[k], ',')))
        except EOFError:
            return
        raw = raw.strip().replace(',', '').replace('，', '')
        if not raw:
            continue
        try:
            nv, cut = clamp_cap(k, float(raw))
            CAPS[k] = nv
            if cut:
                log("    [钳制] 游戏上限是 %s, 已按此设置" % format(nv, ','))
        except Exception:
            log("    [忽略] 不是数字: " + raw)
    cfg['caps'] = {k: CAPS[k] for k in CAPS}
    save_cfg(cfg)
    log("已保存: " + ", ".join("%s=%s" % (CAP_LABEL[k], format(CAPS[k], ','))
                              for k in ('money', 'conscription', 'food', 'tech',
                                        'tactical', 'supply', 'troop')))
    try:
        ans = input("要立刻应用到所有存档吗？[Y/n]: ").strip().lower()
    except EOFError:
        ans = 'y'
    if ans in ('', 'y', 'yes'):
        done, sk, fa, lines = apply_all()
        log("\n".join(lines))
        log("完成 %d / 跳过 %d / 失败 %d" % (done, sk, fa))


def report():
    cfg = load_cfg()
    lines = ["存档目录: " + SAVES_DIR,
             "程序目录: " + APP_DIR,
             "备份目录: " + BACKUP_DIR,
             "作用范围: %s   热键: %s"
             % (SCOPE_NAME.get(cfg.get('scope'), cfg.get('scope')),
                'Ctrl+Alt+F9 等 5 组' if cfg.get('hotkey', True) else '关'),
             "自动修改: " + ('开（游戏启动自动改档）' if cfg.get('auto_apply')
                            else '关（只保留热键，改档手动）'),
             "已勾选  : " + sections_label(parse_sections(cfg.get('sections'))),
             "六维目标: " + '/'.join(str(STATS[k]) for k in STAT_KEYS)
             + "  (统率/武力/敏捷/智力/政治/魅力)",
             ""]
    if os.path.isdir(SAVES_DIR):
        for n in sorted(os.listdir(SAVES_DIR)):
            if not n.lower().endswith('.sav'):
                continue
            p = os.path.join(SAVES_DIR, n)
            try:
                data = json.loads(read_sav(p)['body'].decode('utf-8'))
                pl = [f for f in (data.get('factions') or {}).values() if f.get('bIsPlayerCtrl')]
                money = (pl[0].get('info') or {}).get('money') if pl else '?'
                tag = "修改中(金钱%s)" % money if money == CAPS['money'] else "原档"
            except Exception:
                tag = "读取失败"
            lines.append("  %-34s %10d B  [%s]" % (n, os.path.getsize(p), tag))
    txt = "\n".join(lines)
    log(txt)
    if sys.stdout is None and not RESULT_FILE:
        popup(txt)


if __name__ == '__main__':
    main()
