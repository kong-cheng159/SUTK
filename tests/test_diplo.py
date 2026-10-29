# -*- coding: utf-8 -*-
"""外交大小写修复测试（临时目录里跑写档，不碰真实存档）"""
import importlib.util, importlib.machinery, json, os, shutil, struct, tempfile, zlib

spec = importlib.util.spec_from_loader(
    's', importlib.machinery.SourceFileLoader('s', 'SUTKMod.pyw'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)

REAL = M.SAVES_DIR
SRC = os.path.join(REAL, M.newest_save())
print('目标存档:', os.path.basename(SRC))

ok = True
def check(label, cond, extra=''):
    global ok
    ok = ok and bool(cond)
    print('  %s %-40s %s' % ('[PASS]' if cond else '[FAIL]', label, extra))

print('=' * 70)
print('测试 1：diplo_table 能按大小写归一找到自建势力的全部关系（只读）')
print('=' * 70)
tbl = M.diplo_table(SRC)
check('玩家势力找到', tbl is not None and tbl['pfid'] == 'new_6', 'pfid=%r' % (tbl and tbl['pfid']))
check('关系条数 = 其他势力数', tbl and len(tbl['rels']) == len(tbl['facs']) - 1,
      'rels=%d facs=%d' % (len(tbl['rels']), len(tbl['facs'])))
order = M._diplo_print(tbl)
check('表格能列出全部国家', len(order) == len(tbl['facs']) - 1, '%d 个' % len(order))

print()
print('=' * 70)
print('测试 2：好感度写入真正落到 New_6 的关系条目（临时副本）')
print('=' * 70)
tmp = tempfile.mkdtemp(prefix='diplo_')
M.BACKUP_DIR = os.path.join(tmp, 'backup'); os.makedirs(M.BACKUP_DIR)
cp = os.path.join(tmp, os.path.basename(SRC))
shutil.copy2(SRC, cp)

# 找一个目标势力 (排除玩家自己), 故意用"错"大小写输入
targets = [f for f in tbl['rels'] if f != tbl['pfid']]
t1, t2 = targets[0], targets[1]
n = M.diplo_write(tbl, cp, [
    {'fid': t1.swapcase() if t1.isalpha() else t1, 'relation': 100},
    {'fid': t2, 'friend': True},
])
check('写入 2 条外交改动', n == 2, 'n=%d' % n)

d2 = json.loads(M.read_sav(cp)['body'].decode('utf-8'))
pfid = tbl['pfid']
def find_rel(d, a, b):
    for r in d['factionRelations']:
        i = r['info']
        if {str(i['factionId1']).lower(), str(i['factionId2']).lower()} == {str(a).lower(), str(b).lower()}:
            return r
    return None
r1 = find_rel(d2, pfid, t1)
r2 = find_rel(d2, pfid, t2)
check('目标1 好感 = 100', r1 is not None and abs(float(r1['relationValue']) - 100) < 1e-6,
      'relationValue=%r' % (r1 and r1['relationValue']))
check('目标1 事件修正已清空', r1 is not None and r1.get('relationEventValue') == {},
      repr(r1 and r1.get('relationEventValue')))
check('目标2 结盟生效', r2 is not None and r2['info']['isFriend'] is True)
check('目标2 好感被拉满', r2 is not None and abs(float(r2['relationValue']) - 100) < 1e-6)
check('存档仍可正常解析(魔数/解压校验)', M.read_sav(cp)['magic'] == M.MAGIC)
check('写档前自动备份 .orig',
      os.path.exists(os.path.join(M.BACKUP_DIR, os.path.basename(cp) + '.orig')))

print()
print('=' * 70)
print('测试 3：wizard 输入大小写归一（New_6 大写输入也能命中）')
print('=' * 70)
canon = tbl['canon']
check('canon 含 new_6', canon.get('new_6') == 'new_6', repr(canon.get('new_6')))
check('NEW_6 归一成 new_6', canon.get('NEW_6'.lower(), 'NEW_6') == 'new_6')
check('关系条目键均来自势力表', all(k in tbl['facs'] for k in tbl['rels']),
      '全部可显示国家名/君主')

print()
print('=' * 70)
print('测试 4：人情写入方向（我方侧）+ 衰减计时重置')
print('=' * 70)
tbl2 = M.diplo_table(cp)                       # 用测试2写过的副本
t = targets[0]
sd = tbl2['side'][t]
n = M.diplo_write(tbl2, cp, [{'fid': t, 'favour': 20}])
check('写入 1 条人情', n == 1, 'n=%d side=%d' % (n, sd))
d3 = json.loads(M.read_sav(cp)['body'].decode('utf-8'))
r3 = find_rel(d3, pfid, t)
mine_key = 'favourValue%d' % sd
tick_key = 'favourChangeTick%d' % sd
other_key = 'favourValue%d' % (3 - sd)
check('我方侧人情 = 20 (写进 favourValue%d)' % sd,
      r3 is not None and abs(float(r3.get(mine_key) or 0) - 20) < 1e-6,
      'value=%r' % (r3 and r3.get(mine_key)))
htick = 0
try:
    h = json.loads(M.read_sav(cp)['header'].decode('utf-8'))
    htick = int((h.get('gameTime') or {}).get('tickCount') or 0)
except Exception:
    pass
check('衰减计时已重置为当前tick', r3 is not None and r3.get(tick_key) == htick,
      '%s=%r tick=%r' % (tick_key, r3 and r3.get(tick_key), htick))
check('对方侧人情未被误写', r3 is not None and not r3.get(other_key),
      'value=%r' % (r3 and r3.get(other_key)))

print()
print('=' * 70)
print('测试 5：对方侧人情写入（favour_other）')
print('=' * 70)
n = M.diplo_write(tbl2, cp, [{'fid': t, 'favour_other': 13}])
check('写入 1 条对方人情', n == 1)
d4 = json.loads(M.read_sav(cp)['body'].decode('utf-8'))
r4 = find_rel(d4, pfid, t)
check('对方侧人情 = 13 (写进 favourValue%d)' % (3 - sd),
      r4 is not None and abs(float(r4.get(other_key) or 0) - 13) < 1e-6,
      'value=%r' % (r4 and r4.get(other_key)))
check('我方侧人情保持 20', r4 is not None and abs(float(r4.get(mine_key) or 0) - 20) < 1e-6)

mine_v, other_v = M._favour_vals(r4, sd)
check('_favour_vals 方向读取正确', abs(mine_v - 20) < 1e-6 and abs(other_v - 13) < 1e-6,
      'mine=%g other=%g' % (mine_v, other_v))

shutil.rmtree(tmp, ignore_errors=True)
print()
print('结果:', '全部 PASS' if ok else '有 FAIL！')
raise SystemExit(0 if ok else 1)
