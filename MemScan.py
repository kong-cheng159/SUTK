#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MemScan —— CE 式内存扫描/写入（纯 ctypes，无依赖）
=================================================
比 CE 少一步盲搜：存档文件里就有当前数值，直接拿它当种子。

用法
----
  python MemScan.py --self-test
        自检：派生子进程写入特征值 → 扫描 → 过滤 → 改值 → 校验

  python MemScan.py --seed-from-save "AutoSave.sav" --field money --type int32
        用存档里的金钱当种子，扫描游戏进程（自动找内存占用最大的那个进程）

  python MemScan.py --filter 12000000
        进入游戏花掉一些钱，用新值做二次过滤

  python MemScan.py --write 999999999
        把剩下的地址全部改成目标值

  python MemScan.py --list        查看当前候选数
"""
import ctypes, ctypes.wintypes as wt, struct, json, os, sys, subprocess, time

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype = wt.BOOL
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.GetLastError.restype = wt.DWORD

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_RW = (0x04, 0x08, 0x40, 0x80)   # RW / WRITECOPY / EXECUTE_RW / EXECUTE_WRITECOPY

GAME = 'SUTK-Win64-Shipping.exe'
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'memscan.json')
FMT = {'int32': ('<i', 4), 'int64': ('<q', 8), 'float': ('<f', 4), 'double': ('<d', 8)}


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p),
                ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wt.DWORD),
                ('PartitionId', wt.WORD),
                ('_pad', wt.WORD),
                ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD),
                ('Protect', wt.DWORD),
                ('Type', wt.DWORD)]


def regions(h):
    """枚举可写私有已提交内存区"""
    out = []
    addr = 0
    mbi = MBI()
    while True:
        n = k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not n:
            break
        if mbi.State == MEM_COMMIT and mbi.Type == MEM_PRIVATE and mbi.Protect in PAGE_RW:
            out.append((addr, mbi.RegionSize))
        addr += mbi.RegionSize
        if addr >= 0x7FFFFFFF0000:
            break
    return out


def rpm(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
        return None
    return buf.raw[:got.value]


def wpm(h, addr, data):
    got = ctypes.c_size_t(0)
    buf = ctypes.create_string_buffer(data, len(data))
    return bool(k32.WriteProcessMemory(h, ctypes.c_void_p(addr), buf, len(data),
                                       ctypes.byref(got)))


def scan(h, value, typ='int32', limit=None):
    """全内存扫描等于 value 的地址"""
    pack, sz = FMT[typ]
    pat = struct.pack(pack, value)
    hits = []
    chunk = 1 << 20
    for base, size in regions(h):
        off = 0
        carry = b''
        while off < size:
            n = min(chunk, size - off)
            data = rpm(h, base + off, n)
            if data:
                buf = carry + data
                start = 0
                while True:
                    i = buf.find(pat, start)
                    if i < 0:
                        break
                    hits.append(base + off - len(carry) + i)
                    start = i + 1
                carry = buf[-(sz - 1):] if sz > 1 else b''
            off += n
            if limit and len(hits) > limit:
                return hits
    return hits


def filter_hits(h, hits, value, typ='int32'):
    pack, sz = FMT[typ]
    pat = struct.pack(pack, value)
    keep = []
    for a in hits:
        d = rpm(h, a, sz)
        if d == pat:
            keep.append(a)
    return keep


def write_hits(h, hits, value, typ='int32'):
    pack, sz = FMT[typ]
    pat = struct.pack(pack, value)
    ok = 0
    for a in hits:
        if wpm(h, a, pat):
            ok += 1
    return ok


# ------------------------------------------------------------------ 进程
def find_game():
    """找内存占用最大的游戏进程（排除退出后残留的空壳）"""
    si = subprocess.STARTUPINFO(); si.dwFlags |= 1
    out = subprocess.check_output(
        'tasklist /FI "IMAGENAME eq %s" /FO CSV /NH' % GAME,
        shell=True, startupinfo=si, creationflags=0x08000000).decode('gbk', 'ignore')
    best = None
    for line in out.splitlines():
        p = [x.strip('"') for x in line.split('","')]
        if len(p) < 5 or p[0].lower() != GAME.lower():
            continue
        try:
            mem = int(p[4].replace(',', '').replace(' K', '').strip())
        except Exception:
            mem = 0
        if best is None or mem > best[1]:
            best = (int(p[1]), mem)
    return best          # (pid, KB)


def open_target(pid):
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ |
                        PROCESS_VM_WRITE | PROCESS_VM_OPERATION, False, pid)
    if not h:
        err = ctypes.get_last_error()
        raise OSError(err, 'OpenProcess 失败 (错误码 %d)%s' %
                      (err, ' = 拒绝访问，需要用管理员身份运行' if err == 5 else ''))
    return h


def seed_from_save(path, field='money'):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import importlib.util, importlib.machinery
    spec = importlib.util.spec_from_loader('sutk', importlib.machinery.SourceFileLoader(
        'sutk', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'SUTKMod.pyw')))
    M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
    d = json.loads(M.read_sav(path)['body'].decode('utf-8'))
    for f in d['factions'].values():
        if f.get('bIsPlayerCtrl'):
            if field == 'food':
                return f.get('food'), f['info'].get('money')
            return f['info'].get(field), f.get('food')
    return None, None



# ------------------------------------------------------------------ 提权
def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin():
    """不是管理员就用 UAC 重新拉起自己。返回 True 表示已是管理员"""
    if is_admin():
        return True
    exe = sys.executable
    if exe.lower().endswith('pythonw.exe'):
        exe = exe[:-len('pythonw.exe')] + 'python.exe'
    script = os.path.abspath(__file__)
    args = [x for x in sys.argv[1:]]
    params = '"%s"' % script
    if args:
        params += ' ' + ' '.join('"%s"' % a if ' ' in a else a for a in args)
    print('当前不是管理员，无法读取游戏内存（游戏是管理员级别运行）。')
    print('正在请求管理员权限，请在弹出的「用户账户控制」窗口点「是」...')
    try:
        r = ctypes.windll.shell32.ShellExecuteW(
            None, 'runas', exe, params, os.path.dirname(script), 1)
        if r > 32:
            print('已发起提权请求，本窗口可以关闭（新窗口会继续运行）。')
        else:
            print('提权被取消或失败 (ShellExecute 返回 %s)' % r)
    except Exception as e:
        print('提权失败:', e)
    return False


# ------------------------------------------------------------------ 自检
def self_test():
    print('=== 自检：对派生子进程做 扫描 → 过滤 → 写入 → 校验 ===')
    code = ("import ctypes,time\n"
            "v=ctypes.c_int(1234567)\n"
            "print('ready',flush=True)\n"
            "time.sleep(60)\n")
    p = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE)
    p.stdout.readline()
    try:
        h = open_target(p.pid)
        print('  OpenProcess OK')
        regs = regions(h)
        print('  可枚举内存区: %d 个, 共 %.1f MB' % (len(regs), sum(r[1] for r in regs) / 1e6))

        hits = scan(h, 1234567, 'int32')
        print('  扫描 1234567 → 命中 %d 处' % len(hits))

        hits2 = filter_hits(h, hits, 1234567, 'int32')
        print('  复核 → 保留 %d 处' % len(hits2))
        assert hits2, '未找到特征值'

        n = write_hits(h, hits2, 7654321, 'int32')
        print('  写入 7654321 → 成功 %d 处' % n)

        left = filter_hits(h, hits2, 7654321, 'int32')
        print('  回读校验 → %d 处已是新值' % len(left))
        old_left = filter_hits(h, hits2, 1234567, 'int32')
        print('  旧值残留 → %d 处' % len(old_left))
        ok = (len(left) == len(hits2))
        print('\n结论:', 'PASS —— 扫描/写入引擎正常' if ok else 'FAIL')
        return ok
    finally:
        p.kill()



def wizard():
    """引导式流程：扫描 → 二次过滤 → 写入"""
    g = find_game()
    if not g:
        print('游戏没在运行，先启动游戏'); return
    print('找到游戏: PID %d (%.0f MB)' % (g[0], g[1] / 1024))

    import glob
    saves = sorted(glob.glob(os.path.join(
        os.environ.get('LOCALAPPDATA', ''), r'ProjectA\Saved\Saves\*.sav')),
        key=os.path.getmtime, reverse=True)
    seed = None
    if saves:
        print('最近存档: %s' % os.path.basename(saves[0]))
        try:
            seed, _ = seed_from_save(saves[0], 'money')
            print('  存档里的金钱 = %s' % seed)
        except Exception as e:
            print('  读取存档失败:', e)
    print()
    print('  !! 种子必须是【游戏画面里现在显示的数值】')
    print('     存档文件里的值只作参考(如果你中途花过钱, 内存值已变)')
    if seed is not None:
        print('     存档参考值: %s' % seed)
    raw = input('  输入游戏里显示的金钱数值: ').strip().replace(',', '').replace('，', '')
    if raw:
        seed = int(float(raw))
    if seed is None:
        print('需要一个数值'); return

    t0 = time.time()
    try:
        h = open_target(g[0])
    except OSError as e:
        print()
        print('  ✗ %s' % e)
        print('  ─────────────────────────────────────────')
        print('  解决办法: 右键「控制台」或 bat → 以管理员身份运行')
        print('  然后重新进入本功能')
        return
    try:
        regs = regions(h)
        print('可写私有内存: %d 区 / %.0f MB, 开始扫描...' % (len(regs), sum(r[1] for r in regs) / 1e6))
        hits = scan(h, seed, 'int32')
        print('int32 命中 %d 处 (%.1fs)' % (len(hits), time.time() - t0))
        if not hits:
            print('int32 没命中, 自动改用 float 再扫一次...')
            t1 = time.time()
            hits = scan(h, float(seed), 'float')
            print('float 命中 %d 处 (%.1fs)' % (len(hits), time.time() - t1))
        if not hits:
            print()
            print('  ✗ 两种类型都没找到, 常见原因:')
            print('    1. 输入的数值和游戏画面不一致(再看一眼, 别用存档值)')
            print('    2. 你在主菜单/没进入剧本, 金钱还没加载进内存')
            print('    3. 游戏内部用的不是整型/单精度浮点')
            return

        while True:
            print('\n当前候选: %d 处 [%s]' % (len(hits), ', '.join('%#x' % x for x in hits[:5])))
            print('  F = 在游戏里改一下这个数值, 然后输入新值做过滤')
            print('  W = 直接写入目标值')
            print('  Q = 退出')
            c = input('选择: ').strip().lower()
            if c == 'q':
                return
            if c == 'f' or (c and c[0].isdigit()):
                v = c if c[0].isdigit() else input('  输入游戏里现在显示的新数值: ').strip()
                try:
                    nv = int(v)
                except Exception:
                    print('  不是整数'); continue
                hits = filter_hits(h, hits, nv, 'int32')
                print('  过滤后剩 %d 处' % len(hits))
                if not hits:
                    print('  候选清零，重新扫描吧'); return
                if len(hits) == 1:
                    print('  ✅ 已锁定唯一地址 %#x' % hits[0])
            elif c == 'w':
                tgt = input('  要写入的数值: ').strip()
                try:
                    tv = int(tgt)
                except Exception:
                    print('  不是整数'); continue
                n = write_hits(h, hits, tv, 'int32')
                back = filter_hits(h, hits, tv, 'int32')
                print('  写入 %s: 成功 %d 处, 回读确认 %d 处' % (tv, n, len(back)))
                print('  回游戏看一眼数值变了没有')
    finally:
        k32.CloseHandle(h)


# ------------------------------------------------------------------ main
def main():
    a = sys.argv[1:]
    if '--no-elevate' not in a and not ensure_admin():
        return
    if '--self-test' in a:
        self_test(); return
    if '--wizard' in a:
        wizard(); return

    typ = 'int32'
    if '--type' in a:
        typ = a[a.index('--type') + 1]

    if '--list' in a:
        if not os.path.exists(STATE_FILE):
            print('还没有候选，先扫描一次'); return
        st = json.load(open(STATE_FILE))
        print('候选地址: %d 个 | 值=%s 类型=%s' % (len(st['hits']), st['value'], st['type']))
        for x in st['hits'][:10]:
            print('   %#x' % x)
        return

    if '--seed-from-save' in a:
        sav = a[a.index('--seed-from-save') + 1]
        field = a[a.index('--field') + 1] if '--field' in a else 'money'
        seed, alt = seed_from_save(sav, field)
        print('从存档取种子: %s = %s' % (field, seed))
    elif '--seed' in a:
        seed = int(a[a.index('--seed') + 1])
    elif '--filter' in a:
        seed = int(a[a.index('--filter') + 1])
        st = json.load(open(STATE_FILE))
        g = find_game()
        if not g:
            print('游戏没在运行'); return
        h = open_target(g[0])
        try:
            keep = filter_hits(h, st['hits'], seed, st['type'])
            print('过滤 %s → 保留 %d / %d 处' % (seed, len(keep), len(st['hits'])))
            st['hits'] = keep; st['value'] = seed
            json.dump(st, open(STATE_FILE, 'w'))
        finally:
            k32.CloseHandle(h)
        return
    elif '--write' in a:
        val = int(a[a.index('--write') + 1])
        st = json.load(open(STATE_FILE))
        g = find_game()
        if not g:
            print('游戏没在运行'); return
        h = open_target(g[0])
        try:
            n = write_hits(h, st['hits'], val, st['type'])
            back = filter_hits(h, st['hits'], val, st['type'])
            print('写入 %s → 成功 %d 处, 回读确认 %d 处' % (val, n, len(back)))
        finally:
            k32.CloseHandle(h)
        return
    else:
        print(__doc__); return

    g = find_game()
    if not g:
        print('游戏没在运行'); return
    print('游戏 PID %d (%.0f MB)' % (g[0], g[1] / 1024))
    t0 = time.time()
    h = open_target(g[0])
    try:
        regs = regions(h)
        print('可写私有内存: %d 区, %.0f MB' % (len(regs), sum(r[1] for r in regs) / 1e6))
        hits = scan(h, seed, typ)
        print('扫描 %s 完成: 命中 %d 处, 耗时 %.1fs' % (seed, len(hits), time.time() - t0))
        json.dump({'hits': hits, 'value': seed, 'type': typ, 'pid': g[0]},
                  open(STATE_FILE, 'w'))
        print('已保存候选 →', STATE_FILE)
        print('\n下一步: 在游戏里花掉一些钱, 然后用新数值执行:')
        print('   python MemScan.py --filter <新的金钱数>')
    finally:
        k32.CloseHandle(h)


if __name__ == '__main__':
    main()
