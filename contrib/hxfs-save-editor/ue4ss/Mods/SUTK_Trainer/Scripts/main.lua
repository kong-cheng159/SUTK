--[[
    华夏风云：三国 (Seres Universalis: Three Kingdoms) 内置修改器
    基于 UE4SS v3.x
    功能：
      F1  - 切换修改器菜单显示
      F9  - 重新扫描游戏内资源数值
      F10 - 把所有发现的对象属性 dump 到日志 (方便后续精调)
]]

local M = {}

-- ============ 配置区 ============
local CFG = {
    scan_interval = 2.0,       -- 每 2 秒重新扫描一次资源
    add_amount_small = 1000,    -- 单次 +1000
    add_amount_large = 10000,   -- 单次 +10000
    freeze_enabled = false,      -- 是否冻结资源
    menu_visible = true,
}

-- 资源关键词（小写匹配属性名）
local RESOURCE_KEYWORDS = {
    money   = { "money", "gold", "coin", "silver", "copper", "treasury", "qian", "jin", "cash" },
    food    = { "food", "grain", "provision", "ration", "supplie", "liang", "grub", "rice" },
    troop   = { "soldier", "troop", "army", "bing", "soldiercount", "troopcount", "armysize", "men" },
    pop     = { "population", "pop", "people", "renkou", "citizen", "resident" },
    wood    = { "wood", "timber", "mucai", "lumber" },
    iron    = { "iron", "metal", "tie", "steel" },
    stone   = { "stone", "shikuai", "rock" },
    tech    = { "techpoint", "skillpoint", "jishu", "researchpoint", "culture", "prestige" },
}

-- 候选对象类名（按优先级）
local CANDIDATE_CLASSES = {
    "GameState", "GameStateBase",
    "PlayerState",
    "PlayerController",
    "GameInstance",
    "Pawn",
}

-- ============ 状态 ============
local state = {
    scanned = false,
    scan_ready = false,
    found_resources = {},   -- { {category, obj, prop_name, current} }
    candidates = {},        -- 找到的候选对象
    last_scan_time = 0,
    freeze_values = {},     -- prop_name -> locked value
}

-- ============ 工具函数 ============
local function safe_get(obj, prop)
    local ok, val = pcall(function() return obj[prop] end)
    if ok then return val end
    return nil
end

local function safe_set(obj, prop, val)
    local ok, err = pcall(function() obj[prop] = val end)
    return ok
end

local function classify_prop(prop_name)
    local lower = string.lower(prop_name)
    for cat, words in pairs(RESOURCE_KEYWORDS) do
        for _, w in ipairs(words) do
            if string.find(lower, w, 1, true) then
                return cat
            end
        end
    end
    return nil
end

-- ============ 扫描逻辑 ============
local function collect_candidates()
    state.candidates = {}
    for _, cls in ipairs(CANDIDATE_CLASSES) do
        local ok, objs = pcall(FindAllOf, cls)
        if ok and objs then
            for _, o in ipairs(objs) do
                table.insert(state.candidates, o)
            end
        end
    end
    -- 去重
    local seen = {}
    local unique = {}
    for _, o in ipairs(state.candidates) do
        local ok, name = pcall(function() return o:GetFullName() end)
        if ok and name and not seen[name] then
            seen[name] = true
            table.insert(unique, o)
        end
    end
    state.candidates = unique
    Print(string.format("[SUTK Trainer] Found %d candidate objects\n", #unique))
end

local function scan_resources()
    collect_candidates()
    state.found_resources = {}
    local seen_props = {}

    for _, obj in ipairs(state.candidates) do
        -- 尝试枚举对象的属性名（UE4SS 反射）
        local props = {}
        local ok, cls = pcall(function() return obj:GetClass() end)
        if ok and cls then
            -- 尝试多种反射 API
            local ok2, props_list = pcall(function() return cls:GetProperties() end)
            if ok2 and props_list then
                for _, p in ipairs(props_list) do
                    local pname = nil
                    pcall(function() pname = p:GetFName():ToString() end)
                    if not pname then
                        pcall(function() pname = p:GetName() end)
                    end
                    if pname then table.insert(props, pname) end
                end
            end
        end

        -- 如果反射枚举失败，用关键词硬扫常见属性名
        if #props == 0 then
            local guess = {
                "Money","Gold","Food","Grain","Soldier","Troop","Army",
                "Population","Pop","Wood","Iron","Stone","TechPoint","SkillPoint",
                "PlayerMoney","PlayerFood","PlayerTroop","PlayerGold",
                "Treasury","Supplies","SoldierCount","TroopCount",
            }
            props = guess
        end

        for _, prop_name in ipairs(props) do
            local val = safe_get(obj, prop_name)
            if val ~= nil and type(val) ~= "table" and type(val) ~= "userdata" then
                local num = tonumber(val)
                if num ~= nil then
                    local cat = classify_prop(prop_name) or "other"
                    local key = tostring(obj:GetFullName()) .. "::" .. prop_name
                    if not seen_props[key] then
                        seen_props[key] = true
                        table.insert(state.found_resources, {
                            category = cat,
                            obj = obj,
                            prop_name = prop_name,
                            value = num,
                            key = key,
                        })
                    end
                end
            end
        end
    end

    state.scanned = true
    state.scan_ready = true
    Print(string.format("[SUTK Trainer] Scanned %d numeric properties\n", #state.found_resources))
end

local function dump_all_to_log()
    Print("========== SUTK Trainer DUMP START ==========\n")
    for _, obj in ipairs(state.candidates) do
        local ok, fullname = pcall(function() return obj:GetFullName() end)
        if ok then
            Print(string.format("OBJ: %s\n", fullname))
        end
    end
    Print("---------- Found Resources ----------\n")
    for _, r in ipairs(state.found_resources) do
        Print(string.format("[%s] %s = %s\n", r.category, r.prop_name, tostring(r.value)))
    end
    Print("========== SUTK Trainer DUMP END ==========\n")
end

-- ============ 冻结逻辑 ============
local function apply_freeze()
    if not CFG.freeze_enabled then return end
    for _, r in ipairs(state.found_resources) do
        if state.freeze_values[r.key] ~= nil then
            local cur = safe_get(r.obj, r.prop_name)
            if cur ~= nil and tonumber(cur) ~= state.freeze_values[r.key] then
                safe_set(r.obj, r.prop_name, state.freeze_values[r.key])
            end
        end
    end
end

-- ============ ImGui 菜单 ============
local function draw_menu()
    if not imgui then return end

    local visible = { CFG.menu_visible }
    -- 用 Begin 包裹整个窗口
    local ok = pcall(function()
        if not imgui.Begin then return end
        local open = imgui.Begin("华夏风云三国 修改器##SUTK", visible)
        CFG.menu_visible = visible[1]
        if not open then imgui.End() return end

        imgui.TextColored(0.4, 0.9, 0.4, 1.0, "=== 华夏风云：三国 内置修改器 ===")
        imgui.Text(string.format("已扫描 %d 个数值属性", #state.found_resources))
        imgui.Separator()

        -- 冻结开关
        local fr = { CFG.freeze_enabled }
        if imgui.Checkbox("冻结资源数值 (保持不变)", fr) then
            CFG.freeze_enabled = fr[1]
            if CFG.freeze_enabled then
                state.freeze_values = {}
                for _, r in ipairs(state.found_resources) do
                    state.freeze_values[r.key] = r.value
                end
            end
        end
        imgui.SameLine()
        if imgui.Button("重新扫描##rescan") then
            scan_resources()
        end

        imgui.Separator()

        -- 按类别分组显示
        local cats = {"money","food","troop","pop","wood","iron","stone","tech","other"}
        local cat_labels = {
            money = "金钱 / 金币", food = "粮食 / 补给", troop = "兵力 / 军队",
            pop = "人口", wood = "木材", iron = "铁", stone = "石头",
            tech = "科技 / 声望", other = "其他数值"
        }

        for _, cat in ipairs(cats) do
            local items = {}
            for _, r in ipairs(state.found_resources) do
                if r.category == cat then table.insert(items, r) end
            end
            if #items > 0 then
                if imgui.TreeNode(string.format("%s (%d)", cat_labels[cat] or cat, #items)) then
                    for _, r in ipairs(items) do
                        local cur = safe_get(r.obj, r.prop_name)
                        if cur ~= nil then
                            r.value = tonumber(cur) or 0
                            imgui.Text(string.format("%s = %d", r.prop_name, r.value))
                            imgui.SameLine()
                            if imgui.Button(string.format("+%d##%s", CFG.add_amount_small, r.key)) then
                                safe_set(r.obj, r.prop_name, r.value + CFG.add_amount_small)
                            end
                            imgui.SameLine()
                            if imgui.Button(string.format("+%d##%s", CFG.add_amount_large, r.key)) then
                                safe_set(r.obj, r.prop_name, r.value + CFG.add_amount_large)
                            end
                            imgui.SameLine()
                            if imgui.Button(string.format("设为 999999##%s", r.key)) then
                                safe_set(r.obj, r.prop_name, 999999)
                            end
                        end
                    end
                    imgui.TreePop()
                end
            end
        end

        imgui.Separator()
        imgui.TextColored(0.7, 0.7, 0.7, 1.0, "热键: F1 开关菜单 | F9 重新扫描 | F10 导出日志")
        imgui.End()
    end)
    if not ok then
        -- ImGui 出错不崩溃
    end
end

-- ============ 热键功能 ============
local function add_to_category(cat, amount)
    local count = 0
    for _, r in ipairs(state.found_resources) do
        if r.category == cat then
            local cur = safe_get(r.obj, r.prop_name)
            if cur ~= nil then
                safe_set(r.obj, r.prop_name, (tonumber(cur) or 0) + amount)
                count = count + 1
            end
        end
    end
    Print(string.format("[SUTK Trainer] +%d to %d %s properties\n", amount, count, cat))
end

local function set_all_category(cat, value)
    local count = 0
    for _, r in ipairs(state.found_resources) do
        if r.category == cat then
            safe_set(r.obj, r.prop_name, value)
            count = count + 1
        end
    end
    Print(string.format("[SUTK Trainer] Set %d %s properties to %d\n", count, cat, value))
end

-- ============ 热键 ============
local function register_hotkeys()
    pcall(RegisterKeyBind, Key.F1, {}, function()
        CFG.menu_visible = not CFG.menu_visible
        Print(string.format("[SUTK Trainer] Menu %s\n", CFG.menu_visible and "ON" or "OFF"))
    end)
    pcall(RegisterKeyBind, Key.F2, {}, function() add_to_category("money", CFG.add_amount_large) end)
    pcall(RegisterKeyBind, Key.F3, {}, function() add_to_category("food", CFG.add_amount_large) end)
    pcall(RegisterKeyBind, Key.F4, {}, function() add_to_category("troop", CFG.add_amount_large) end)
    pcall(RegisterKeyBind, Key.F5, {}, function() set_all_category("money", 999999) end)
    pcall(RegisterKeyBind, Key.F6, {}, function() set_all_category("food", 999999) end)
    pcall(RegisterKeyBind, Key.F9, {}, function()
        scan_resources()
        Print("[SUTK Trainer] Rescan done\n")
    end)
    pcall(RegisterKeyBind, Key.F10, {}, function()
        dump_all_to_log()
        Print("[SUTK Trainer] Dump written to UE4SS log\n")
    end)
end

-- ============ 启动 ============
local function on_game_ready()
    Print("[SUTK Trainer] Initializing...\n")
    register_hotkeys()
    scan_resources()

    -- 注册 ImGui 菜单（多种方式尝试）
    pcall(function()
        if RegisterImGuiTab then
            RegisterImGuiTab("SUTK Trainer", draw_menu)
        end
    end)
    pcall(function()
        if imgui and imgui.RegisterTab then
            imgui.RegisterTab("SUTK Trainer", draw_menu)
        end
    end)

    -- 定时重扫 + 冻结
    local function tick()
        local now = os.clock()
        if now - state.last_scan_time > CFG.scan_interval then
            state.last_scan_time = now
            scan_resources()
        end
        apply_freeze()
        ExecuteWithDelay(500, tick)
    end
    ExecuteWithDelay(3000, tick)
end

-- 等待游戏加载
ExecuteWithDelay(5000, function()
    local ok, err = pcall(on_game_ready)
    if not ok then
        Print("[SUTK Trainer] Init error: " .. tostring(err) .. "\n")
    end
end)

Print("[SUTK Trainer] Mod loaded. Waiting for game world...\n")
