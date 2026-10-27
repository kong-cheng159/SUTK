# -*- coding: utf-8 -*-
"""SUTK 修改器桌面界面。

只调用上一级目录里的 SUTKMod.pyw / MemScan.py，不改那些文件。
监听 127.0.0.1，不对外网开放。
"""
import importlib.machinery
import importlib.util
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
STATIC = os.path.join(HERE, 'static')
NAMES_PATH = os.path.join(HERE, 'names_zh.json')
CITIES_PATH = os.path.join(HERE, 'cities_zh.json')
TROOP_KINDS_PATH = os.path.join(HERE, 'troop_kinds_zh.json')
PORT = 8731
APP_ID = 'sutk-desktop'

sys.path.insert(0, PROJ)


def _load(name, filename):
    path = os.path.join(PROJ, filename)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


M = _load('sutkmod_desktop', 'SUTKMod.pyw')
MS = _load('memscan_desktop', 'MemScan.py')
M.NOGUI = True


def _apply_app_dir():
    """Tauri 启动时把配置、备份、历史放到 exe 旁边，不改 SUTKMod.pyw。"""
    base = os.environ.get('SUTK_APP_DIR', '').strip()
    if not base:
        return
    base = os.path.abspath(base)
    os.makedirs(base, exist_ok=True)
    M.APP_DIR = base
    M.BACKUP_DIR = os.path.join(base, 'backup')
    M.HISTORY_DIR = os.path.join(base, 'history')
    M.TRASH_DIR = os.path.join(M.HISTORY_DIR, '_trash')
    M.CONFIG_PATH = os.path.join(base, 'config.json')
    try:
        MS.STATE_FILE = os.path.join(base, 'memscan.json')
    except Exception:
        pass


_apply_app_dir()

LOCK = threading.Lock()
HTTPD = None


class Capture:
    def __init__(self):
        self.lines = []
        self._old = None

    def __enter__(self):
        self._old = M.log

        def hook(msg):
            text = str(msg)
            if text:
                self.lines.extend(text.splitlines())

        M.log = hook
        return self

    def __exit__(self, *exc):
        M.log = self._old


def _cfg():
    cfg = M.load_cfg()
    M.apply_caps(cfg)
    return cfg


def _save_path(name):
    base = os.path.basename(str(name or ''))
    if not base or base != str(name) or not base.lower().endswith('.sav'):
        raise ValueError('存档名不合法')
    path = os.path.join(M.SAVES_DIR, base)
    if not os.path.isfile(path):
        raise ValueError('找不到存档: ' + base)
    return path


def _public_cfg(cfg):
    secs = M.parse_sections(cfg.get('sections')) or set()
    return {
        'scope': cfg.get('scope') or 'player',
        'sections': [k for k in M.SECTIONS_ALL if k in secs] if cfg.get('sections') != 'all'
        else list(M.SECTIONS_ALL),
        'sections_all': cfg.get('sections') == 'all' or secs == set(M.SECTIONS_ALL),
        'auto_apply': bool(cfg.get('auto_apply')),
        'snapshot_game': bool(cfg.get('snapshot_game')),
        'hotkey': bool(cfg.get('hotkey', True)),
        'caps': {k: M.CAPS.get(k) for k in M.CAPS},
        'stats': {k: M.STATS.get(k) for k in M.STAT_KEYS},
        'saves_dir': M._norm_user_path(cfg.get('saves_dir')),
        'extern_path': M._norm_user_path(cfg.get('extern_path')),
        'team_presets': M.get_team_presets(cfg),
    }


def _apply_path_fields(cfg, body):
    lines = []
    if 'saves_dir' in body:
        raw = body.get('saves_dir')
        if raw is None or str(raw).strip() == '':
            cfg['saves_dir'] = ''
            lines.append('存档目录已恢复为系统默认')
        else:
            p = M._norm_user_path(raw)
            if not os.path.isdir(p):
                raise ValueError('存档目录不存在或不是文件夹: ' + p)
            cfg['saves_dir'] = p
            lines.append('存档目录: ' + p)
    if 'extern_path' in body:
        raw = body.get('extern_path')
        if raw is None or str(raw).strip() == '':
            cfg['extern_path'] = ''
            lines.append('自建模板路径已随存档目录自动推导')
        else:
            p = M._norm_user_path(raw)
            if not os.path.isfile(p):
                raise ValueError('找不到 ExternPersonage.sav: ' + p)
            cfg['extern_path'] = p
            lines.append('自建模板: ' + p)
    if 'saves_dir' in body or 'extern_path' in body:
        M.apply_path_cfg(cfg)
    return lines


def api_status():
    M.seed_team_presets_if_empty()
    cfg = _cfg()
    n = 0
    if os.path.isdir(M.SAVES_DIR):
        n = len([x for x in os.listdir(M.SAVES_DIR) if x.lower().endswith('.sav')])
    try:
        admin = bool(MS.is_admin())
    except Exception:
        admin = False
    try:
        watchers = M._list_watcher_pids()
    except Exception:
        watchers = []
    return {
        'app': APP_ID,
        'saves_dir': M.SAVES_DIR,
        'saves_dir_default': M.default_saves_dir(),
        'saves_dir_ok': os.path.isdir(M.SAVES_DIR),
        'extern_path': M.EXTERN_PATH,
        'extern_path_default': M.default_extern_path(),
        'extern_ok': os.path.isfile(M.EXTERN_PATH),
        'backup_dir': M.BACKUP_DIR,
        'history_dir': M.HISTORY_DIR,
        'save_count': n,
        'game_running': bool(M.game_running()),
        'admin': admin,
        'watchers': watchers,
        'modules': [{'key': k, 'name': M.SECTIONS_NAME[k], 'tip': M.SECTIONS_TIP[k]}
                    for k in M.SECTIONS_ALL],
        'cap_label': M.CAP_LABEL,
        'stat_label': M.STAT_LABEL,
        'scope_name': M.SCOPE_NAME,
        'cfg': _public_cfg(cfg),
    }


def api_saves():
    _cfg()
    rows = []
    for mt, name, sz in M._saves_sorted():
        path = os.path.join(M.SAVES_DIR, name)
        state, player, money = '读取失败', '', None
        try:
            data = M._sav_json(M.read_sav(path))
            fid = M._player_fid(data)
            if not fid:
                state = '无玩家势力'
            else:
                player = _label_cn(M._faction_label(data, fid))
                money = ((data['factions'][fid].get('info') or {}).get('money'))
                state = '已修改' if money == M.CAPS['money'] else '原档'
        except Exception:
            pass
        rows.append({
            'name': name,
            'mtime': mt,
            'time': time.strftime('%m-%d %H:%M', time.localtime(mt)),
            'size': sz,
            'state': state,
            'player': player,
            'money': money,
            'has_orig': os.path.isfile(M.backup_path(path)),
            'recent': len(rows) == 0,
        })
    return {'saves': rows, 'game_running': bool(M.game_running())}


def _sections(body):
    raw = body.get('sections')
    if raw == 'all' or raw is None:
        return set(M.SECTIONS_ALL)
    if isinstance(raw, str):
        return M.parse_sections(raw) or set()
    return {k for k in raw if k in M.SECTIONS_ALL}


def api_apply(body):
    names = body.get('names') or []
    if isinstance(names, str):
        names = [names]
    names = [os.path.basename(n) for n in names if n]
    if not names:
        raise ValueError('先选择存档')
    secs = _sections(body)
    if not secs:
        raise ValueError('没有勾选任何模块')
    scope = body.get('scope') or _cfg().get('scope') or 'player'
    force = bool(body.get('force'))
    _cfg()
    total = [0, 0, 0]
    lines = []
    if M.game_running():
        lines.append('游戏正在运行：改动要退出到主菜单后重新读档才生效，中途存档会覆盖。')
    with Capture() as cap:
        for name in names:
            _save_path(name)
            done, skipped, failed, part = M.apply_all(
                scope=scope, secs=secs, only=name, force=force)
            total[0] += done
            total[1] += skipped
            total[2] += failed
            lines.extend(part)
    lines.extend(cap.lines)
    lines.append('模块：%s' % M.sections_label(secs))
    lines.append('完成 %d / 已是最新 %d / 失败 %d' % tuple(total))
    return {'lines': lines, 'done': total[0], 'skipped': total[1], 'failed': total[2]}


def api_restore(body):
    names = body.get('names') or []
    if isinstance(names, str):
        names = [names]
    names = [os.path.basename(n) for n in names if n]
    if not names:
        raise ValueError('先选择要还原的存档')
    lines = []
    n = 0
    with Capture() as cap:
        for name in names:
            _save_path(name)
            n1, part = M.restore_all(only=name)
            n += n1
            lines.extend(part)
    lines.extend(cap.lines)
    lines.append('已还原 %d 个存档' % n)
    return {'lines': lines, 'restored': n}


def api_save_config(body):
    cfg = _cfg()
    if 'scope' in body and body['scope'] in M.SCOPE_NAME:
        cfg['scope'] = body['scope']
    if 'sections' in body:
        secs = _sections(body)
        cfg['sections'] = ('all' if secs == set(M.SECTIONS_ALL)
                           else ','.join(k for k in M.SECTIONS_ALL if k in secs))
    if 'auto_apply' in body:
        cfg['auto_apply'] = bool(body['auto_apply'])
    if 'snapshot_game' in body:
        cfg['snapshot_game'] = bool(body['snapshot_game'])
    if 'hotkey' in body:
        cfg['hotkey'] = bool(body['hotkey'])
    caps = body.get('caps') or {}
    cfg.setdefault('caps', {})
    for k, v in caps.items():
        if k in M.CAPS and v is not None and str(v) != '':
            nv, _cut = M.clamp_cap(k, v)
            cfg['caps'][k] = nv
    stats = body.get('stats') or {}
    cfg.setdefault('stats', {})
    for k, v in stats.items():
        if k in M.STAT_KEYS and v is not None and str(v) != '':
            cfg['stats'][k] = max(1, min(M.STAT_MAX, int(float(v))))
    path_lines = _apply_path_fields(cfg, body)
    M.save_cfg(cfg)
    M.apply_caps(cfg)
    lines = path_lines if path_lines else ['配置已保存']
    if path_lines and '配置已保存' not in lines:
        lines.append('配置已保存')
    return {
        'cfg': _public_cfg(cfg),
        'lines': lines,
        'saves_dir': M.SAVES_DIR,
        'extern_path': M.EXTERN_PATH,
    }


def api_open_folder(body):
    kind = (body or {}).get('kind') or 'saves'
    if kind == 'extern':
        path = M.EXTERN_PATH
        if not os.path.isfile(path):
            raise ValueError('文件不存在: ' + path)
        os.startfile(os.path.dirname(path))
    else:
        path = M.SAVES_DIR
        if not os.path.isdir(path):
            raise ValueError('目录不存在: ' + path)
        os.startfile(path)
    return {'lines': ['已打开: ' + path]}


def _load_json_map(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if v}
    except Exception:
        pass
    return {}


_NAMES = _load_json_map(NAMES_PATH)
_CITIES = _load_json_map(CITIES_PATH)
_TROOP_KINDS = _load_json_map(TROOP_KINDS_PATH)


def _troop_kind_cn(kind_id):
    k = str(kind_id or '').strip()
    if not k:
        return ''
    return _TROOP_KINDS.get(k) or _TROOP_KINDS.get(k.split('_')[0]) or ''


def _lookup_cn(token):
    token = str(token or '')
    if not token or token == 'None':
        return ''
    if token in _NAMES:
        return _NAMES[token]
    camel = token[:1].upper() + token[1:]
    return _NAMES.get(camel) or ''


def _label_cn(label):
    label = str(label or '')
    head, sep, tail = label.partition('(')
    cn = _lookup_cn(head)
    if cn and sep:
        return cn + '(' + tail
    return cn or label


def _prefect_cn(data, pid):
    pid = str(pid or '')
    if not pid or pid == 'None':
        return '无'
    hit = _lookup_cn(pid)
    if hit:
        return hit
    ps = data.get('personages') or {}
    per = ps.get(pid)
    if per is None:
        low = pid.lower()
        for k, v in ps.items():
            if str(k).lower() == low:
                per = v
                break
    if per:
        cn = _person_cn(pid, per.get('baseInfo') or {})
        if cn:
            return cn
    return pid


def _person_cn(pid, bi):
    """原版武将用游戏中文名表；自建武将的汉字直接写在存档里。"""
    node = (bi or {}).get('fullName') or {}
    full = str(node.get('key') or '') if isinstance(node, dict) else ''
    if full and not full.startswith('FullName_'):
        return full
    key = full[9:] if full.startswith('FullName_') else ''
    if not key and pid:
        key = pid[:1].upper() + pid[1:]
    return _NAMES.get(key) or ''


def _open_save(name):
    path = _save_path(name)
    sav, data = M._load_save_json(path)
    return path, sav, data


def api_generals(name):
    _path, _sav, data = _open_save(name)
    fid = M._player_fid(data)
    if not fid:
        raise ValueError('这个存档里找不到玩家势力')
    roster = M._known_roster() or set()
    rows = []
    for tot, pid, bi in M._own_generals(data, fid):
        rows.append({
            'pid': pid,
            'cn': _person_cn(pid, bi),
            'total': tot,
            'custom': bool(roster) and pid not in roster,
            'stats': {k: bi.get(k) for k in M.STAT_KEYS},
        })
    return {
        'name': os.path.basename(_path),
        'faction': fid,
        'label': M._faction_label(data, fid),
        'targets': {k: M.STATS[k] for k in M.STAT_KEYS},
        'generals': rows,
    }


def api_edit_general(body):
    path, sav, data = _open_save(body.get('name'))
    fid = M._player_fid(data)
    rows = M._own_generals(data, fid)
    targets = {k: M.STATS[k] for k in M.STAT_KEYS}
    changed = 0
    people = 0
    if body.get('apply_targets'):
        for _tot, _pid, bi in rows:
            for k in M.STAT_KEYS:
                if k in bi and M._set(bi, k, targets[k]):
                    changed += 1
            people += 1
    else:
        want = body.get('pid')
        values = body.get('values') or {}
        found = None
        for _tot, pid, bi in rows:
            if pid == want:
                found = bi
                break
        if found is None:
            raise ValueError('找不到武将: ' + str(want))
        for k, v in values.items():
            if k not in M.STAT_KEYS or v is None or str(v) == '':
                continue
            nv = max(1, min(M.STAT_MAX, int(float(v))))
            if M._set(found, k, nv):
                changed += 1
        people = 1 if changed else 0
    if changed:
        M._write_save_json(path, sav, data)
    msg = '已修改 %d 项' % changed if changed else '没有改动'
    if M.game_running() and changed:
        msg += '。游戏正在运行，需要重新读档才生效'
    return {'lines': [msg], 'changed': changed, 'people': people}


def api_extern():
    data, _raw = M.read_extern()
    if data is None:
        return {'path': M.EXTERN_PATH, 'missing': True, 'rows': []}
    rows = []
    for gid, info, kind in M._extern_rows(data):
        rows.append({
            'guid': gid,
            'kind': kind,
            'name': M._extern_name(info),
            'tactical': info.get('tactical'),
            'stats': {k: info.get(k) for k in M.STAT_KEYS},
        })
    return {
        'path': M.EXTERN_PATH,
        'missing': False,
        'rows': rows,
        'lines': ['改的是模板，只影响以后新建的战役，已有存档不变'],
    }


def api_edit_extern(body):
    data, _raw = M.read_extern()
    if data is None:
        raise ValueError('没找到 ExternPersonage.sav')
    gid = str(body.get('guid') or '')
    kind = body.get('kind')
    bucket = 'newInfos' if kind == 'new' else 'modifyInfos'
    holder = (data.get(bucket) or {}).get(gid)
    if not isinstance(holder, dict):
        raise ValueError('找不到这个模板武将')
    changed = 0
    for k, v in (body.get('values') or {}).items():
        if k not in M.STAT_KEYS or v is None or str(v) == '':
            continue
        nv = max(1, min(M.STAT_MAX, int(float(v))))
        if holder.get(k) != nv:
            holder[k] = nv
            changed += 1
    if changed:
        ok = M.write_extern(data)
        if not ok:
            raise ValueError('写回模板失败')
    return {'lines': ['已修改 %d 项。只影响以后的新开局' % changed if changed else '没有改动'],
            'changed': changed}


def api_cities(name):
    _path, _sav, data = _open_save(name)
    rows = []
    for row in M.city_rows(data):
        item = dict(row)
        item['cn'] = _CITIES.get(str(item['key']).lower()) or item.get('cn') or ''
        item['label'] = _label_cn(item.get('label'))
        item['prefect'] = _prefect_cn(data, item.get('prefect'))
        rows.append(item)
    facs = []
    arch = data.get('architectures') or {}
    for fid, fac in (data.get('factions') or {}).items():
        n = sum(1 for a in arch.values()
                if str((a.get('info') or {}).get('faction')).lower() == str(fid).lower())
        inf = fac.get('info') or {}
        facs.append({
            'id': fid,
            'label': _label_cn(M._faction_label(data, fid)),
            'king': inf.get('kingId') or '',
            'cities': n,
            'player': bool(fac.get('bIsPlayerCtrl')),
            'destroyed': bool(fac.get('bDestroyed')),
        })
    facs.sort(key=lambda x: (-x['cities'], str(x['id'])))
    with Capture() as cap:
        problems = M.check_map(data)
    return {
        'name': os.path.basename(_path),
        'player': M._player_fid(data),
        'cities': rows,
        'factions': facs,
        'problems': problems,
        'lines': cap.lines,
    }


def api_assign_prefects(body):
    path, sav, data = _open_save(body.get('name'))
    fid = M._player_fid(data)
    if fid is None:
        raise ValueError('这个存档里找不到玩家势力')
    all_player = bool(body.get('all_player'))
    keys = body.get('keys')
    if keys is not None and not isinstance(keys, list):
        keys = [keys]
    city_keys = None
    if all_player:
        city_keys = None
    else:
        keys = [str(k) for k in (keys or []) if k]
        if not keys:
            raise ValueError('请先勾选城市，或使用「本国全部无太守城市」')
        arch = data.get('architectures') or {}
        city_keys = []
        for k in keys:
            a = arch.get(k)
            if not a:
                continue
            inf = a.get('info') or {}
            if str(inf.get('faction')).lower() != str(fid).lower():
                continue
            city_keys.append(k)
        if not city_keys:
            raise ValueError('所选城市里没有属于你的、且无太守可任命的城')
    combat_threshold = body.get('combat_threshold')
    lines = []
    with Capture() as cap:
        n, part, summary = M.auto_assign_prefects(
            data, fid=fid, city_keys=city_keys, combat_threshold=combat_threshold)
        if n:
            M._write_save_json(path, sav, data)
        problems = M.check_map(data)
    lines.extend(cap.lines)
    lines.extend(summary or [])
    lines.append('已任命 %d 座城的太守' % n)
    lines.extend(part)
    if problems:
        lines.append('一致性问题 %d 项（见记录）' % len(problems))
        lines.extend(problems[:10])
    else:
        lines.append('一致性自检通过')
    if M.game_running() and n:
        lines.append('游戏正在运行：请回主菜单重新读档后生效。')
    return {'lines': lines, 'assigned': n, 'problems': problems}


def api_troop_kinds_get():
    return {'kinds': _TROOP_KINDS}


def api_team_presets_get():
    return {'presets': M.seed_team_presets_if_empty()}


def api_team_presets_save(body):
    presets = body.get('presets')
    if presets is None:
        raise ValueError('缺少 presets')
    saved = M.save_team_presets(presets)
    return {'presets': saved, 'lines': ['已保存 %d 个三人编队预设' % len(saved)]}


def api_teams_list(body):
    path, sav, data = _open_save(body.get('name'))
    fid = M._player_fid(data)
    teams = M.list_player_teams(data, fid=fid)
    for t in teams:
        cn = _troop_kind_cn(t.get('troopKindId'))
        if cn:
            t['troopKindCn'] = cn
    return {'teams': teams, 'name': os.path.basename(path)}


def api_teams_deploy(body):
    path, sav, data = _open_save(body.get('name'))
    city_key = str(body.get('city_key') or body.get('city') or '').strip()
    if not city_key:
        raise ValueError('请指定 city_key（目标城市）')
    all_presets = M.get_team_presets(_cfg())
    by_id = {str(p.get('id')): p for p in all_presets}
    ids = body.get('preset_ids')
    if ids is not None and not isinstance(ids, list):
        ids = [ids]
    if not ids:
        pid = str(body.get('preset_id') or body.get('preset') or '').strip()
        ids = [pid] if pid else []
    if not ids:
        raise ValueError('请勾选或指定 preset_id / preset_ids')
    chosen = []
    for pid in ids:
        p = by_id.get(str(pid))
        if p is None:
            raise ValueError('找不到预设: ' + str(pid))
        chosen.append(p)
    game_team_id = body.get('team_id') or body.get('game_team_id')
    lines = []
    with Capture() as cap:
        if len(chosen) == 1:
            gt, n, part = M.create_team_preset_at_city(
                data, city_key, chosen[0], team_id=game_team_id)
        else:
            gt, n, part = M.deploy_team_presets_at_city(
                data, city_key, chosen, game_team_id=game_team_id)
        if n:
            M._write_save_json(path, sav, data)
        problems = M.check_map(data)
    lines.extend(cap.lines)
    lines.append('已在 %s 创建 %d 支三人编队（%d 个预设）'
                 % (city_key, n, len(chosen)))
    lines.extend(part)
    if problems:
        lines.append('一致性问题 %d 项' % len(problems))
        lines.extend(problems[:8])
    else:
        lines.append('一致性自检通过')
    if M.game_running() and n:
        lines.append('游戏正在运行：请回主菜单重新读档后生效。')
    return {'lines': lines, 'team_id': tid, 'troops': n, 'problems': problems}


def api_transfer(body):
    path, sav, data = _open_save(body.get('name'))
    keys = [str(k) for k in (body.get('keys') or [])]
    target = str(body.get('target') or '')
    if not keys or not target:
        raise ValueError('先选择城市和目标势力')
    keep_one = body.get('keep_one', True)
    if keep_one is None:
        keep_one = True
    move = bool(body.get('move_officers'))
    lines = []
    with Capture() as cap:
        M.backup_before_transfer(path)
        done, part, warns = M.transfer_cities(
            data, keys, target, move_officers=move, keep_one=bool(keep_one))
        if done:
            M._write_save_json(path, sav, data)
        problems = M.check_map(data)
    lines.extend(cap.lines)
    lines.append('已转移 %d 城' % done)
    lines.extend(part)
    lines.extend(warns)
    if problems:
        lines.append('一致性问题 %d 项' % len(problems))
        lines.extend(problems[:12])
    else:
        lines.append('一致性自检通过')
    if M.game_running() and done:
        lines.append('游戏正在运行：退出到主菜单后重新载入，不要中途存档。')
    return {'lines': lines, 'done': done, 'problems': problems}


def api_health(name):
    with Capture() as cap:
        M.check_save_health(only=name)
    return {'lines': cap.lines or ['检查完成']}


def api_repair(body):
    name = os.path.basename(str(body.get('name') or ''))
    src = body.get('src') or None
    if src:
        src = os.path.basename(str(src))
    with Capture() as cap:
        M.repair_annex(only=name or None, src=src)
    return {'lines': cap.lines or ['修复流程已结束']}


def _diplo_rows(tbl):
    rows = []
    side = tbl.get('side') or {}
    for fid, rel in tbl['rels'].items():
        info = rel.get('info') or {}
        mine, other = M._favour_vals(rel, side.get(fid, 2))
        rows.append({
            'fid': fid,
            'king': tbl['king'].get(fid, ''),
            'destroyed': bool(tbl['facs'].get(fid, {}).get('bDestroyed')),
            'relation': rel.get('relationValue'),
            'friend': bool(info.get('isFriend')),
            'armistice': bool(info.get('isArmistice')),
            'favour': mine,
            'favour_other': other,
        })
    rows.sort(key=lambda r: -float(r['relation'] or 0))
    return rows


def api_diplo(name):
    path = _save_path(name)
    tbl = M.diplo_table(path)
    if tbl is None:
        raise ValueError('这个档里找不到玩家势力')
    return {
        'name': os.path.basename(path),
        'player': tbl['pfid'],
        'king': tbl['king'].get(tbl['pfid'], ''),
        'rows': _diplo_rows(tbl),
        'game_running': bool(M.game_running()),
    }


def api_diplo_write(body):
    path = _save_path(body.get('name'))
    tbl = M.diplo_table(path)
    if tbl is None:
        raise ValueError('这个档里找不到玩家势力')
    changes = body.get('changes') or []
    if not changes:
        raise ValueError('没有要写入的外交改动')
    clean = []
    for ch in changes:
        if not isinstance(ch, dict) or not ch.get('fid'):
            continue
        item = {'fid': ch['fid']}
        if ch.get('relation') is not None and str(ch.get('relation')) != '':
            item['relation'] = max(-100, min(100, int(float(ch['relation']))))
        if 'friend' in ch and ch['friend'] is not None:
            item['friend'] = bool(ch['friend'])
        if 'armistice' in ch and ch['armistice'] is not None:
            item['armistice'] = bool(ch['armistice'])
        if ch.get('favour') is not None and str(ch.get('favour')) != '':
            item['favour'] = max(0, min(100, float(ch['favour'])))
        if ch.get('favour_other') is not None and str(ch.get('favour_other')) != '':
            item['favour_other'] = max(0, min(100, float(ch['favour_other'])))
        if len(item) > 1:
            clean.append(item)
    if not clean:
        raise ValueError('没有有效的外交改动')
    M.snapshot_save(path, 'diplo')
    n = M.diplo_write(tbl, path, clean)
    lines = ['已写入 %d 条外交改动' % n]
    if M.game_running():
        lines.append('游戏正在运行：读档后生效；若再存档会被覆盖。')
    return {'lines': lines, 'written': n}


def api_audit(name):
    with Capture() as cap:
        nerr, warn = M.audit_save(only=name, verbose=True)
    return {'lines': cap.lines, 'errors': nerr, 'warnings': warn or []}


def _group_for(name):
    base = os.path.basename(str(name))
    groups = M._history_groups()
    for key, val in groups.items():
        if key.lower() == base.lower():
            return key, val
    return None, None


def api_history(name=None):
    groups = M._history_groups()
    if name:
        key, val = _group_for(name)
        groups = {key: val} if key else {}
    out = []
    for save, info in groups.items():
        if not info:
            continue
        versions = []
        for sn in info['snaps']:
            versions.append({
                'kind': '快照',
                'file': sn['file'],
                'time': sn['time'],
                'when': time.strftime('%m-%d %H:%M:%S', time.localtime(sn['time'])),
                'size': sn['size'],
                'note': sn['note'],
            })
        orig = info.get('orig')
        if orig and os.path.isfile(orig):
            st = os.stat(orig)
            versions.append({
                'kind': '原始档',
                'file': os.path.basename(orig),
                'time': st.st_mtime,
                'when': time.strftime('%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
                'size': st.st_size,
                'note': '工具首次改动前',
            })
        out.append({
            'name': save,
            'snaps': len(info['snaps']),
            'orig': bool(orig),
            'versions': versions,
        })
    out.sort(key=lambda x: -(x['versions'][0]['time'] if x['versions'] else 0))
    return {'saves': out, 'keep': M.HIST_KEEP}


def api_undo(body):
    key, info = _group_for(body.get('name'))
    if not key or not info:
        raise ValueError('这个存档没有可回滚的记录')
    want = os.path.basename(str(body.get('file') or ''))
    src = None
    kind = ''
    for sn in info['snaps']:
        if sn['file'] == want:
            src = sn['path']
            kind = '快照'
            break
    orig = info.get('orig')
    if src is None and orig and os.path.basename(orig) == want:
        src = orig
        kind = '原始档'
    if not src or not os.path.isfile(src):
        raise ValueError('找不到这个版本')
    real = os.path.abspath(src)
    allowed = [os.path.abspath(M.HISTORY_DIR), os.path.abspath(M.BACKUP_DIR)]
    if not any(real.lower().startswith(a.lower() + os.sep) or real.lower() == a.lower()
               for a in allowed):
        raise ValueError('版本路径不在历史目录里')
    dst = os.path.join(M.SAVES_DIR, key)
    if os.path.exists(dst):
        M.snapshot_save(dst, 'before_restore')
    import shutil
    shutil.copy2(src, dst)
    os.utime(dst, None)
    return {'lines': ['已回滚 %s ← %s（%s）。进游戏重新载入，不要中途存档。' % (key, want, kind)]}


def api_orphans():
    targets = M._orphan_targets()
    return {'targets': targets, 'trash': M.TRASH_DIR, 'days': M.TRASH_KEEP_DAYS}


def api_cleanup():
    with Capture() as cap:
        total, cnt = M.reap_orphans(verbose=True, with_backup=True)
        M.purge_trash()
    lines = list(cap.lines)
    lines.append('已清理 %d 份副本（涉及 %d 个已删除存档）' % (total, cnt))
    return {'lines': lines, 'copies': total, 'saves': cnt}


def api_watcher():
    pid = M.start_watcher()
    return {'lines': ['已尝试启动后台热键 pid=%s' % pid], 'pid': pid}


def api_uninstall():
    with Capture() as cap:
        M.uninstall(quiet=True)
    return {'lines': cap.lines or ['卸载完成']}


def api_guide():
    path = os.path.join(PROJ, '经验总结.md')
    if not os.path.isfile(path):
        raise ValueError('没找到经验总结.md')
    with open(path, encoding='utf-8') as f:
        return {'text': f.read()}


def _i32(value):
    n = int(float(value))
    if n > 2147483647 or n < -2147483648:
        raise ValueError('超出游戏 int32 范围（最大 2147483647）')
    return n


def _mem_state():
    if not os.path.isfile(MS.STATE_FILE):
        return None
    try:
        return json.load(open(MS.STATE_FILE, encoding='utf-8'))
    except Exception:
        return None


def api_mem_status():
    st = _mem_state()
    game = None
    try:
        game = MS.find_game()
    except Exception:
        game = None
    return {
        'admin': bool(MS.is_admin()),
        'game': {'pid': game[0], 'kb': game[1]} if game else None,
        'hits': len(st['hits']) if st and st.get('hits') is not None else 0,
        'value': None if not st else st.get('value'),
        'type': None if not st else st.get('type'),
        'sample': (st.get('hits') or [])[:8] if st else [],
    }


def _need_admin():
    if MS.is_admin():
        return None
    return {'ok': False, 'need_admin': True,
            'error': '读取游戏内存需要管理员权限。请点「用管理员身份重新打开」。'}


def _game_handle():
    game = MS.find_game()
    if not game:
        raise ValueError('游戏没在运行')
    return game, MS.open_target(game[0])


def api_mem_scan(body):
    denied = _need_admin()
    if denied:
        return denied
    field = body.get('field') or 'money'
    if body.get('seed') not in (None, ''):
        seed = _i32(body['seed'])
    else:
        path = _save_path(body.get('name'))
        data = M._sav_json(M.read_sav(path))
        seed = None
        for fac in (data.get('factions') or {}).values():
            if not fac.get('bIsPlayerCtrl'):
                continue
            if field == 'food':
                seed = fac.get('food')
            else:
                seed = (fac.get('info') or {}).get(field)
            break
        if seed is None:
            raise ValueError('存档里没有这个数值')
        seed = _i32(seed)
    game, handle = _game_handle()
    try:
        t0 = time.time()
        hits = MS.scan(handle, seed, 'int32')
        spent = time.time() - t0
    finally:
        MS.k32.CloseHandle(handle)
    json.dump({'hits': hits, 'value': seed, 'type': 'int32', 'pid': game[0]},
              open(MS.STATE_FILE, 'w', encoding='utf-8'))
    return {
        'ok': True,
        'lines': ['扫描 %s 完成：命中 %d 处，用时 %.1f 秒' % (seed, len(hits), spent),
                  '回游戏把这个数花掉或打掉一些，再用新数值过滤。'],
        'hits': len(hits),
        'value': seed,
    }


def api_mem_filter(body):
    denied = _need_admin()
    if denied:
        return denied
    st = _mem_state()
    if not st or not st.get('hits'):
        raise ValueError('还没有候选，先扫描')
    value = _i32(body.get('value'))
    _game, handle = _game_handle()
    try:
        keep = MS.filter_hits(handle, st['hits'], value, st.get('type') or 'int32')
    finally:
        MS.k32.CloseHandle(handle)
    st['hits'] = keep
    st['value'] = value
    json.dump(st, open(MS.STATE_FILE, 'w', encoding='utf-8'))
    return {'ok': True, 'lines': ['过滤 %s 后保留 %d 处' % (value, len(keep))],
            'hits': len(keep), 'value': value}


def api_mem_write(body):
    denied = _need_admin()
    if denied:
        return denied
    st = _mem_state()
    if not st or not st.get('hits'):
        raise ValueError('没有可写的地址')
    if len(st['hits']) > int(body.get('max_hits') or 20):
        raise ValueError('候选还有 %d 处，先继续过滤到不超过 %d 处再写入'
                         % (len(st['hits']), int(body.get('max_hits') or 20)))
    value = _i32(body.get('value'))
    _game, handle = _game_handle()
    try:
        n = MS.write_hits(handle, st['hits'], value, st.get('type') or 'int32')
        back = MS.filter_hits(handle, st['hits'], value, st.get('type') or 'int32')
    finally:
        MS.k32.CloseHandle(handle)
    return {'ok': True,
            'lines': ['写入 %s：成功 %d 处，回读确认 %d 处。回游戏看数值变了没有。' % (value, n, len(back))],
            'written': n, 'confirmed': len(back)}


def api_elevate():
    if MS.is_admin():
        return {'lines': ['当前已经是管理员'], 'admin': True}
    exe = os.path.join(PROJ, 'python', 'pythonw.exe')
    if not os.path.isfile(exe):
        exe = os.path.join(PROJ, 'python', 'python.exe')
    script = os.path.abspath(__file__)
    params = '"%s" --elevated --no-browser' % script
    r = __import__('ctypes').windll.shell32.ShellExecuteW(
        None, 'runas', exe, params, HERE, 0)
    if r <= 32:
        raise ValueError('提权被取消或失败（%s）' % r)

    def _stop():
        time.sleep(0.4)
        if HTTPD is not None:
            threading.Thread(target=HTTPD.shutdown, daemon=True).start()

    threading.Thread(target=_stop, daemon=True).start()
    return {'lines': ['已请求管理员权限。在用户账户控制窗口点「是」后，界面会重新连上。'],
            'restarting': True}


ROUTES = {
    '/api/status': ('GET', lambda b: api_status()),
    '/api/saves': ('GET', lambda b: api_saves()),
    '/api/apply': ('POST', api_apply),
    '/api/restore': ('POST', api_restore),
    '/api/config': ('POST', api_save_config),
    '/api/open-folder': ('POST', api_open_folder),
    '/api/generals': ('GET', lambda b: api_generals(b.get('name'))),
    '/api/generals/edit': ('POST', api_edit_general),
    '/api/extern': ('GET', lambda b: api_extern()),
    '/api/extern/edit': ('POST', api_edit_extern),
    '/api/cities': ('GET', lambda b: api_cities(b.get('name'))),
    '/api/transfer': ('POST', api_transfer),
    '/api/cities/assign-prefects': ('POST', api_assign_prefects),
    '/api/troop-kinds': ('GET', lambda b: api_troop_kinds_get()),
    '/api/team-presets': ('GET', lambda b: api_team_presets_get()),
    '/api/team-presets/save': ('POST', api_team_presets_save),
    '/api/teams': ('GET', lambda b: api_teams_list(b)),
    '/api/teams/deploy': ('POST', api_teams_deploy),
    '/api/health': ('GET', lambda b: api_health(b.get('name'))),
    '/api/repair': ('POST', api_repair),
    '/api/diplo': ('GET', lambda b: api_diplo(b.get('name'))),
    '/api/diplo/write': ('POST', api_diplo_write),
    '/api/audit': ('GET', lambda b: api_audit(b.get('name'))),
    '/api/history': ('GET', lambda b: api_history(b.get('name'))),
    '/api/undo': ('POST', api_undo),
    '/api/orphans': ('GET', lambda b: api_orphans()),
    '/api/cleanup': ('POST', lambda b: api_cleanup()),
    '/api/watcher': ('POST', lambda b: api_watcher()),
    '/api/uninstall': ('POST', lambda b: api_uninstall()),
    '/api/guide': ('GET', lambda b: api_guide()),
    '/api/mem/status': ('GET', lambda b: api_mem_status()),
    '/api/mem/scan': ('POST', api_mem_scan),
    '/api/mem/filter': ('POST', api_mem_filter),
    '/api/mem/write': ('POST', api_mem_write),
    '/api/elevate': ('POST', lambda b: api_elevate()),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        return

    def _query(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        return parsed.path, {k: v[0] for k, v in qs.items()}

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > 2_000_000:
            raise ValueError('请求过大')
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        if not raw:
            return {}
        return json.loads(raw.decode('utf-8'))

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path, ctype):
        data = open(path, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        path, query = self._query()
        if method == 'GET' and path in ('/', '/index.html'):
            self._file(os.path.join(STATIC, 'index.html'), 'text/html; charset=utf-8')
            return
        if method == 'GET' and path == '/app.css':
            self._file(os.path.join(STATIC, 'app.css'), 'text/css; charset=utf-8')
            return
        if method == 'GET' and path == '/app.js':
            self._file(os.path.join(STATIC, 'app.js'), 'text/javascript; charset=utf-8')
            return
        if method == 'GET' and path.startswith('/assets/'):
            rel = path.lstrip('/').replace('/', os.sep)
            fp = os.path.join(STATIC, rel)
            if os.path.isfile(fp):
                ctype = mimetypes.guess_type(fp)[0] or 'application/octet-stream'
                self._file(fp, ctype)
                return
        route = ROUTES.get(path)
        if route is None or route[0] != method:
            self._json({'ok': False, 'error': '没有这个接口'}, 404)
            return
        body = query if method == 'GET' else self._body()
        try:
            with LOCK:
                result = route[1](body)
        except Exception as e:
            self._json({'ok': False, 'error': str(e), 'lines': [str(e)]})
            return
        if not isinstance(result, dict):
            result = {'result': result}
        result.setdefault('ok', True)
        self._json(result)

    def do_GET(self):
        try:
            self._handle('GET')
        except Exception:
            traceback.print_exc()
            self._json({'ok': False, 'error': '服务器内部错误'}, 500)

    def do_POST(self):
        try:
            self._handle('POST')
        except Exception:
            traceback.print_exc()
            self._json({'ok': False, 'error': '服务器内部错误'}, 500)


def _ours(port):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/api/status' % port, timeout=1) as resp:
            return APP_ID.encode() in resp.read()
    except Exception:
        return False


def _open_window(url):
    candidates = [
        os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
        os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), r'Microsoft\Edge\Application\msedge.exe'),
    ]
    for exe in candidates:
        if exe and os.path.isfile(exe):
            __import__('subprocess').Popen(
                [exe, '--app=' + url, '--window-size=1280,860'],
                stdout=__import__('subprocess').DEVNULL,
                stderr=__import__('subprocess').DEVNULL)
            return
    __import__('ctypes').windll.shell32.ShellExecuteW(None, 'open', url, None, None, 1)


def main():
    global HTTPD, PORT
    args = sys.argv[1:]
    if '--port' in args:
        PORT = int(args[args.index('--port') + 1])
    no_browser = '--no-browser' in args
    if '--elevated' in args:
        for _ in range(40):
            if not _ours(PORT):
                break
            time.sleep(0.25)
    elif _ours(PORT):
        if not no_browser:
            _open_window('http://127.0.0.1:%d/' % PORT)
        return
    try:
        HTTPD = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError:
        HTTPD = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        PORT = HTTPD.server_address[1]
    url = 'http://127.0.0.1:%d/' % PORT
    try:
        with open(os.path.join(HERE, 'server.log'), 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), url))
    except Exception:
        pass
    port_dir = os.environ.get('SUTK_APP_DIR', '').strip() or HERE
    try:
        with open(os.path.join(port_dir, 'port.txt'), 'w', encoding='ascii') as f:
            f.write(str(PORT))
    except Exception:
        pass
    if not no_browser:
        threading.Timer(0.3, lambda: _open_window(url)).start()
    HTTPD.serve_forever()


if __name__ == '__main__':
    main()
