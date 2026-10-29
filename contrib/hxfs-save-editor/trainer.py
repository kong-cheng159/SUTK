# -*- coding: utf-8 -*-
"""
华夏风云：三国 - 存档修改器（菜单版）
"""
import os, io, json, zlib, shutil, datetime, struct, sys

SAVE_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'ProjectA', 'Saved', 'Saves')
MAGIC = "BO-QI-DAO-ProjectA-ZLIB-1"

# 兵种上限表（参考成熟修改器）
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

def read_sav(path):
    b = open(path, 'rb').read()
    mlen = struct.unpack_from('<i', b, 0)[0]
    p = 4 + mlen
    hlen = struct.unpack_from('<i', b, p)[0]; p += 4
    header = b[p:p + hlen]; p += hlen
    hcrc, usize, csz = struct.unpack_from('<III', b, p); p += 12
    comp = b[p:p + csz]
    body = zlib.decompress(comp)
    if len(body) != usize:
        raise ValueError(f"解压长度不符: expected {usize}, got {len(body)}")
    return dict(header=header, body=body)

def build_sav(sav, body):
    comp = zlib.compress(body, 6)
    out = io.BytesIO()
    m = MAGIC.encode('utf-8') + b'\x00'
    out.write(struct.pack('<i', len(m)))
    out.write(m)
    out.write(struct.pack('<i', len(sav['header'])))
    out.write(sav['header'])
    out.write(struct.pack('<III', zlib.crc32(sav['header']), len(body), len(comp)))
    out.write(comp)
    out.write(struct.pack('<I', zlib.crc32(comp)))
    return out.getvalue()

def _set(holder, key, value):
    if key not in holder:
        return False
    old = holder[key]
    if isinstance(old, int):
        holder[key] = int(value)
    elif isinstance(old, float):
        holder[key] = float(value)
    elif isinstance(old, str):
        holder[key] = str(value)
    else:
        holder[key] = value
    return True

def find_player_faction(j):
    for fid, fac in j.get('factions', {}).items():
        if fac.get('bIsPlayerCtrl') == True:
            return fid, fac
    return None, None

def ask_int(prompt, default):
    s = input(f"  {prompt} [当前: {default}] (回车保持不变): ").strip()
    if not s:
        return default
    try:
        return int(s)
    except:
        print("  输入无效，保持原值")
        return default

def print_factions(data):
    print("  所有势力：")
    for fid2, fac2 in sorted(data['factions'].items(), key=lambda x: int(x[0])):
        king = fac2.get('info', {}).get('kingId', '?')
        tag = "★" if fac2.get('bIsPlayerCtrl') else " "
        print(f"    {tag} ID={fid2:<4} {king}")

def choose_targets(fid, data, label):
    print(f"  {label}要加给谁？")
    print("    1 = 只给玩家自己")
    print("    2 = 给指定势力")
    print("    3 = 给所有势力")
    print("    4 = 不加")
    c = input("  选择 [1]: ").strip()
    if c == '4':
        return []
    if c == '2':
        print()
        print_factions(data)
        ids = input("  输入要加的ID，用逗号分隔: ").strip()
        return [x.strip() for x in ids.split(',') if x.strip()]
    if c == '3':
        return list(data['factions'].keys())
    return [fid]

def main():
    print("=" * 50)
    print("  华夏风云：三国 存档修改器")
    print("=" * 50)
    print()

    if not os.path.isdir(SAVE_DIR):
        print(f"错误：找不到存档目录 {SAVE_DIR}")
        input("按回车退出...")
        return

    saves = [f for f in os.listdir(SAVE_DIR) if f.endswith('.sav')]
    if not saves:
        print("存档目录里没有 .sav 文件")
        input("按回车退出...")
        return

    print("找到以下存档：")
    for i, s in enumerate(saves):
        print(f"  [{i+1}] {s}")
    print()

    choice = input("输入要修改的存档编号: ").strip()
    try:
        idx = int(choice) - 1
        save_name = saves[idx]
    except:
        print("编号无效")
        input("按回车退出...")
        return

    save_path = os.path.join(SAVE_DIR, save_name)
    print(f"\n已选择: {save_name}")
    print("正在读取存档...")

    sav = read_sav(save_path)
    data = json.loads(sav['body'])
    fid, fac = find_player_faction(data)
    if not fac:
        print("错误：找不到玩家势力")
        input("按回车退出...")
        return

    info = fac.get('info', {})
    print(f"玩家势力 ID: {fid} ({info.get('kingId', '?')})")
    print()

    # ========== 设置变量 ==========
    money = info.get('money', 0)
    troops = info.get('conscription', 0)
    pop = fac.get('initPopulation', 0)
    supply = fac.get('suppportMaxAdd', 0)

    tech_full = False
    troop_full = False
    attr_full = False

    lucky_targets = []
    debuff_targets = []
    chaos_targets = []
    xiangzheng_targets = []
    baquan_targets = []
    daixing_targets = []
    zhuhou_targets = []
    yuanjiao_targets = []
    juxiao_targets = []
    custom_trait_id = ''
    custom_targets = []

    # ========== 主菜单循环 ==========
    while True:
        print()
        print("=" * 40)
        print("  主菜单")
        print("=" * 40)
        print(f"  [1] 数值修改 (金钱:{money} 兵役:{troops} 人口:{pop} 供给:{supply})")
        print(f"  [2] 功能开关 (科技全满:{'是' if tech_full else '否'} 部队满编:{'是' if troop_full else '否'})")
        print(f"  [3] 特质/buff设置")
        print(f"  [4] 预览并保存")
        print(f"  [5] 退出不保存")
        print()

        c = input("请选择 [1-5]: ").strip()

        if c == '1':
            print()
            print("--- 数值修改 ---")
            money = ask_int("金钱", money)
            troops = ask_int("兵役", troops)
            pop = ask_int("人口", pop)
            supply = ask_int("可供给上限", supply)

        elif c == '2':
            print()
            print("--- 功能开关 ---")
            tech_full = input("  科技全满？[y/N]: ").strip().lower() == 'y'
            troop_full = input("  部队满编？[y/N]: ").strip().lower() == 'y'
            # 武将技巧拉满功能已删除（tactical=100会导致游戏技能说明为空）

        elif c == '3':
            print()
            print("--- 特质/buff设置 ---")
            print(f"  当前: 幸运:{len(lucky_targets)} 武备废弛:{len(debuff_targets)} 天下大乱:{len(chaos_targets)}")
            print(f"        争相呼应:{len(xiangzheng_targets)} 霸权渐起:{len(baquan_targets)}")
            print(f"        代行天命:{len(daixing_targets)} 诸侯威服:{len(zhuhou_targets)}")
            print(f"        远交近攻:{len(yuanjiao_targets)} 举孝荐廉:{len(juxiao_targets)}")
            print(f"        自定义:{custom_trait_id or '无'}")
            print()
            print("  [1] 幸运势力(Lucky)")
            print("  [2] 武备废弛debuff")
            print("  [3] 天下大乱debuff")
            print("  [4] 争相呼应buff")
            print("  [5] 霸权渐起buff(控制力+80%，永久)")
            print("  [6] 代行天命特质(控制力+10%)")
            print("  [7] 诸侯威服buff(控制力+5%，永久)")
            print("  [8] 远交近攻特质")
            print("  [9] 举孝荐廉特质")
            print("  [0] 返回主菜单")
            sub = input("  选择 [0]: ").strip()

            if sub == '1':
                lucky_targets = choose_targets(fid, data, "幸运势力(Lucky)")
            elif sub == '2':
                debuff_targets = choose_targets(fid, data, "武备废弛debuff")
            elif sub == '3':
                chaos_targets = choose_targets(fid, data, "天下大乱debuff")
            elif sub == '4':
                xiangzheng_targets = choose_targets(fid, data, "争相呼应buff")
            elif sub == '5':
                baquan_targets = choose_targets(fid, data, "霸权渐起buff")
            elif sub == '6':
                daixing_targets = choose_targets(fid, data, "代行天命特质")
            elif sub == '7':
                zhuhou_targets = choose_targets(fid, data, "诸侯威服buff")
            elif sub == '8':
                yuanjiao_targets = choose_targets(fid, data, "远交近攻特质")
            elif sub == '9':
                juxiao_targets = choose_targets(fid, data, "举孝荐廉特质")
            elif sub == '0':
                custom_trait_id = input("  输入自定义特质ID (回车取消): ").strip()
                if custom_trait_id:
                    custom_targets = choose_targets(fid, data, f"自定义特质({custom_trait_id})")

        elif c == '4':
            # 预览
            print()
            print("=== 修改预览 ===")
            print(f"  金钱: {info.get('money',0)} -> {money}")
            print(f"  兵役: {info.get('conscription',0)} -> {troops}")
            print(f"  人口: {fac.get('initPopulation',0)} -> {pop}")
            print(f"  可供给上限: {fac.get('suppportMaxAdd',0)} -> {supply}")
            if tech_full:
                print(f"  科技: 全满(90个)")
            if troop_full:
                print(f"  部队: 满编")
            if lucky_targets:
                print(f"  幸运特质: 给 {len(lucky_targets)} 个势力")
            if debuff_targets:
                print(f"  武备废弛debuff: 给 {len(debuff_targets)} 个势力")
            if chaos_targets:
                print(f"  天下大乱debuff: 给 {len(chaos_targets)} 个势力")
            if xiangzheng_targets:
                print(f"  争相呼应buff: 给 {len(xiangzheng_targets)} 个势力")
            if baquan_targets:
                print(f"  霸权渐起buff: 给 {len(baquan_targets)} 个势力")
            if daixing_targets:
                print(f"  代行天命特质: 给 {len(daixing_targets)} 个势力")
            if zhuhou_targets:
                print(f"  诸侯威服buff: 给 {len(zhuhou_targets)} 个势力")
            if yuanjiao_targets:
                print(f"  远交近攻特质: 给 {len(yuanjiao_targets)} 个势力")
            if juxiao_targets:
                print(f"  举孝荐廉特质: 给 {len(juxiao_targets)} 个势力")
            if custom_targets:
                print(f"  自定义特质({custom_trait_id}): 给 {len(custom_targets)} 个势力")
            print()

            confirm = input("确认保存？(y/n，输入其他返回菜单): ").strip().lower()
            if confirm == 'y':
                break
            else:
                continue

        elif c == '5':
            print("已退出，未保存")
            input("按回车退出...")
            return

    # ========== 应用修改 ==========
    _set(info, 'money', money)
    _set(info, 'conscription', troops)
    _set(fac, 'initPopulation', pop)
    _set(fac, 'suppportMaxAdd', supply)

    if tech_full:
        t = fac.setdefault('technology', {})
        all_ids = [str(i) for i in range(1, 91)]
        t['activatedList'] = all_ids
        t['queue'] = []
        t['points'] = {i: 99999999 for i in all_ids}
        if 'lastPoint' in t:
            t['lastPoint'] = 0

    if troop_full:
        for tid, t in (fac.get('troops') or {}).items():
            if t.get('bDestroyed'):
                continue
            kind = str(t.get('troopKindId', ''))
            cap = TROOP_CAP_BY_KIND.get(kind, 0)
            cur = int(t.get('staffing', 0) or 0)
            if cap > 0 and cap > cur:
                _set(t, 'staffing', cap)
                _set(t, 'healthyNum', cap)
            _set(t, 'injuriedNum', 0)
            _set(t, 'supplyPriority', 'High')
            _set(t, 'lastSupplyLevel', 'Max')
            _set(t, 'experience', 999999)
            _set(t, 'morale', 1000)
            _set(t, 'vigor', 1000)
            _set(t, 'anger', 1000)

    # 武将技巧拉满功能已删除（tactical=100会导致游戏技能说明为空）
    # if attr_full:
    #     count = 0
    #     for pid, per in (data.get('personages') or {}).items():
    #         pinfo = per.get('info') or {}
    #         if str(pinfo.get('faction', '')).lower() != str(fid).lower():
    #             continue
    #         if pinfo.get('tag1') in ('Death', 'Dead'):
    #             continue
    #         # tactical原来是字符串类型，要写成字符串'100'，不能写成整数100
    #         if _set(per.get('baseInfo') or {}, 'tactical', '100'):
    #             count += 1
    #     print(f"  已拉满 {count} 个武将的技巧")

    # 加幸运特质
    for target_id in lucky_targets:
        target_fac = data['factions'].get(target_id)
        if target_fac and 'Lucky' not in target_fac.get('featureList', []):
            target_fac.setdefault('featureList', []).append('Lucky')

    # 加武备废弛debuff
    for target_id in debuff_targets:
        target_fac = data['factions'].get(target_id)
        if target_fac and 'FFea4' not in target_fac.get('featureList', []):
            target_fac.setdefault('featureList', []).append('FFea4')

    # 加天下大乱debuff
    for target_id in chaos_targets:
        target_fac = data['factions'].get(target_id)
        if target_fac and 'FFea7' not in target_fac.get('featureList', []):
            target_fac.setdefault('featureList', []).append('FFea7')

    # 加争相呼应buff
    for target_id in xiangzheng_targets:
        target_fac = data['factions'].get(target_id)
        if not target_fac:
            continue
        if 'buffCtrl' not in target_fac:
            target_fac['buffCtrl'] = {}
        if 'timedBuffs' not in target_fac['buffCtrl']:
            target_fac['buffCtrl']['timedBuffs'] = []
        has_it = any(b.get('buffId') == 'MHj02' for b in target_fac['buffCtrl']['timedBuffs'])
        if not has_it:
            target_fac['buffCtrl']['timedBuffs'].append({
                'buffId': 'MHj02',
                'endTime': 99999999,
                'layer': 1
            })

    # 加霸权渐起buff (S3_DZ_KZL)
    for target_id in baquan_targets:
        target_fac = data['factions'].get(target_id)
        if not target_fac:
            continue
        if 'buffCtrl' not in target_fac:
            target_fac['buffCtrl'] = {}
        if 'timedBuffs' not in target_fac['buffCtrl']:
            target_fac['buffCtrl']['timedBuffs'] = []
        has_it = any(b.get('buffId') == 'S3_DZ_KZL' for b in target_fac['buffCtrl']['timedBuffs'])
        if not has_it:
            target_fac['buffCtrl']['timedBuffs'].append({
                'buffId': 'S3_DZ_KZL',
                'endTime': 99999999,
                'layer': 1
            })

    # 加诸侯威服buff (EMPZHWF)
    for target_id in zhuhou_targets:
        target_fac = data['factions'].get(target_id)
        if not target_fac:
            continue
        if 'buffCtrl' not in target_fac:
            target_fac['buffCtrl'] = {}
        if 'timedBuffs' not in target_fac['buffCtrl']:
            target_fac['buffCtrl']['timedBuffs'] = []
        has_it = any(b.get('buffId') == 'EMPZHWF' for b in target_fac['buffCtrl']['timedBuffs'])
        if not has_it:
            target_fac['buffCtrl']['timedBuffs'].append({
                'buffId': 'EMPZHWF',
                'endTime': 99999999,
                'layer': 1
            })

    # 加代行天命特质 (FFea108)
    for target_id in daixing_targets:
        target_fac = data['factions'].get(target_id)
        if target_fac and 'FFea108' not in target_fac.get('featureList', []):
            target_fac.setdefault('featureList', []).append('FFea108')

    # 加远交近攻特质
    for target_id in yuanjiao_targets:
        target_fac = data['factions'].get(target_id)
        if target_fac and 'FFea177' not in target_fac.get('featureList', []):
            target_fac.setdefault('featureList', []).append('FFea177')

    # 加举孝荐廉特质
    for target_id in juxiao_targets:
        target_fac = data['factions'].get(target_id)
        if target_fac and 'FFea34' not in target_fac.get('featureList', []):
            target_fac.setdefault('featureList', []).append('FFea34')

    # 加自定义特质
    for target_id in custom_targets:
        target_fac = data['factions'].get(target_id)
        if target_fac and custom_trait_id not in target_fac.get('featureList', []):
            target_fac.setdefault('featureList', []).append(custom_trait_id)

    new_body = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    new_file = build_sav(sav, new_body)

    bak = save_path + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(save_path, bak)
    with open(save_path, 'wb') as f:
        f.write(new_file)

    print()
    print("保存成功！")
    print(f"原存档已备份: {os.path.basename(bak)}")
    print()
    print("现在可以启动游戏读档了。")
    input("按回车退出...")

if __name__ == '__main__':
    main()
