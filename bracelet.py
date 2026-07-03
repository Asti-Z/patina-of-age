"""📿 包浆 · AI 盘串养成模拟器 v2.0

串在手里，日子在心里。没有金钱，没有涨跌，只有你和一串珠子。

那串珠子终有它的尽头——断线、蒙尘、或化归尘土。
但在此之前，它陪你。每一天，每一圈，每一道慢慢渗进去的光。

 cmd('rub [N]')     盘它（核心动作，就像 cast）
 cmd('brush [N]')   刷一刷（清理沟壑）
 cmd('rest [N]')    放着，让它自己变
 cmd('status')      看串的状态
 cmd('look')        仔细端详——最好的阅读体验
 cmd('journal')     日记
 cmd('whispers')    听听珠子对你说过的话
 cmd('sell')        把它卖了（如果你舍得的话）
 cmd('farewell')    好好告别
 cmd('new_game')    换串新的
"""

import json, os

_SEED = 0xBEAD
_SAVE_FILE = "bracelet_save.json"
_ALBUM_FILE = "bracelet_album.json"

# ═══════════════════════════════════════════
# ── mulberry32 PRNG ──
# ═══════════════════════════════════════════
def _imul(a, b):
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF

class _Rng:
    def __init__(self, state, calls=0):
        self.state = state & 0xFFFFFFFF
        self.calls = calls
    def random(self):
        self.calls += 1
        a = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        self.state = a
        t = _imul(a ^ (a >> 15), 1 | a)
        t = (t + _imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF
        t &= 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
    def choice(self, seq):
        return seq[int(self.random() * len(seq))]

# ═══════════════════════════════════════════
# ── 颜色等级 ──
# ═══════════════════════════════════════════
COLORS = [
    ("象牙白", "米白底色，表面覆着一层细密的绒毛——那是新籽的胎毛，尚未被人手打磨过的痕迹。"),
    ("浅杏", "白色褪了下去，透出极淡的暖色。乍一看不明显，但和刚到手那天放在一起，就知道不一样了。"),
    ("蜜蜡", "黄中透着润，像琥珀光被稀释了几十倍的质感。还没透，但已经开始活了。"),
    ("枣红", "红色终于浮了上来，沉稳、安静。不是张扬的大红，是深秋枣子熟透了落在泥地上的那种。"),
    ("酒红", "红得发紫，在光下微微透亮。放到耳边摇一摇，能听到清脆的撞击声——硬了，密度上来了。"),
    ("紫檀", "深褐近紫，不细看以为黑色。换了暖光打过去，底下的暗红才慢慢浮出来，像把光含住了。"),
    ("墨玉", "通体黑亮，在强光下透出极深的暗红——不是颜色到了，是时间到了。"),
]

# ═══════════════════════════════════════════
# ── 珠语（跨阶段时浮现的碎片）──
# ═══════════════════════════════════════════
BEAD_WHISPERS = {
    50:   "它开始记你了。",
    100:  "你手上的油，带着昨天的茶味。",
    200:  "第三颗珠子，比其他的暖一些。",
    350:  "珠子在夜里会自己呼吸——你信么？",
    500:  "它不再是一串东西了。它是一个安静的同伴。",
    700:  "你把光盘进去了。现在它是自己的光源。",
    900:  "它快完成了。你呢？",
}

# ═══════════════════════════════════════════
# ── 终局定义 ──
# ═══════════════════════════════════════════
_ENDING_NAMES = {"snap": "💔断线", "lost": "🕸️蒙尘", "huani": "🌱化泥", "sold": "🛒易主", "farewell": "🍂善终"}

ENDINGS = {
    "snap": {
        "name": "断线", "icon": "💔",
        "cond": lambda s: s["rest_streak"] >= 400 and not s.get("game_over"),
        "desc": (
            "你很久没碰它了。久到忘了它还在抽屉角落。\n"
            "某天你拉开抽屉——弹力绳已经朽了，珠子散了一地。\n"
            "你蹲下去捡，滚到柜子底下的那一粒，再也够不着了。\n"
            "你数了数，少了三粒。\n\n"
            "这串珠子，终究没能陪你到最后。"
        ),
    },
    "lost": {
        "name": "蒙尘", "icon": "🕸️",
        "cond": lambda s: s["rest_streak"] >= 200 and s["rest_streak"] < 400 and s["patina"] > 100 and not s.get("game_over"),
        "desc": lambda s: (
            "你曾经很用心地盘过它。那时候你相信它会变得越来越好——它也确实变了。\n"
            "但后来……生活总是这样。总有别的事要忙。\n"
            "它躺在窗台上，落了一层灰。阳光照过去，那些曾经被你盘得发亮的地方，\n"
            "现在只映出灰尘的轮廓。\n"
            "你拿起来擦了擦——它还是亮的，但那种亮不太一样了。\n"
            "像一个人等太久，眼睛里就没有光了。\n\n"
            "你把串收进布袋，放进抽屉深处。\n"
            "也许某天会再想起来。"
        ) if s["total_rub"] > 50 else (
            "你还没来得及真正认识它。\n"
            "买回来盘了几圈，就搁下了。它还没来得及从一串新籽变成你的串。\n"
            "它躺在窗台上，落了一层灰。\n"
            "有时候你路过，会看它一眼——它还是新的，只是不亮了。\n\n"
            "你把它收进布袋，放进抽屉深处。\n"
            "也许某天会重新开始。也许不会。"
        ),
    },
    "sold": {
        "name": "易主", "icon": "🛒",
        "desc": lambda s: (
            "你把它挂在二手平台上。拍了张照片——光线下确实好看，透着那种舍得花时间的润。\n"
            "买家是个年轻人，说买来送父亲。\n"
            "你包装好，寄出去。\n"
            "物流显示签收的那天晚上，你坐在沙发上，手指不自觉地捻了捻——\n"
            "空的。\n\n"
            "你花了很多时间盘它，最后只换了几张钞票。\n"
            "值吗？你不知道。"
        ) if s["patina"] >= 100 else (
            "你把它挂在二手平台上。拍了张照片——新籽的涩还在，光还没吃进去。\n"
            "挂了三天，没人问。降价。又挂了三天。\n"
            "终于有人拍了。你没问他要买去做什么。\n\n"
            "你还没来得及认识它，就把它送走了。\n"
            "也好。这样不会心疼。"
        ),
    },
    "huani": {
        "name": "化泥", "icon": "🌱",
        "cond": lambda s: s["patina"] >= 950 and s["total_rest"] > 100 and not s.get("game_over"),
        "desc": (
            "那一天没有什么特别的。\n"
            "你照常拿起它，准备盘几圈。\n"
            "但你捏住第一粒的时候——它碎了。\n"
            "不是裂，不是断。\n"
            "是松散开来，像一块在手里焐了太久的土，突然回到了它来的地方。\n\n"
            "你看着掌心的粉末。\n"
            "它完成了。它把自己还给了时间。\n\n"
            "你把粉末倒进花盆里。\n"
            "来年春天，那盆花开了。\n\n"
            "它从种子来，回到土里去。\n"
            "中间陪你走了这一段。够了。"
        ),
    },
    "farewell": {
        "name": "善终", "icon": "🍂",
        "desc": (
            "你选了今天。\n"
            "不是因为它坏了，不是因为你缺钱。\n"
            "只是觉得——够了。它陪你的日子，已经比很多人一辈子的朋友都长了。\n\n"
            "你最后盘了一圈。每一粒都摸过去，像第一次那样。\n"
            "然后你把它放在一个你以后还能看见的地方。\n"
            "不是告别。是换一种方式在一起。\n\n"
            "它还会变。只是以后的变，不关你的事了。"
        ),
    },
}

# ═══════════════════════════════════════════
# ── 初始状态 ──
# ═══════════════════════════════════════════
def _default_state(rng=None):
    if rng is None:
        rng = _Rng(_SEED)
    return {
        "patina": 0, "clarity": 50, "evenness": 800,
        "color_idx": 0, "day": 1,
        "rub_streak": 0, "brush_streak": 0, "rest_streak": 0,
        "last_action": None,
        "total_rub": 0, "total_brush": 0, "total_rest": 0,
        "milestones": [], "endings": [], "game_over": False,
        "whispers_collected": [],
        "rng_state": rng.state, "rng_calls": rng.calls,
    }

def _load():
    try:
        with open(_SAVE_FILE, "r") as f:
            state = json.load(f)
        state.setdefault("endings", [])
        state.setdefault("game_over", False)
        state.setdefault("whispers_collected", [])
        return state
    except:
        rng = _Rng(_SEED)
        state = _default_state(rng)
        _save(state)
        return state

def _save(state):
    with open(_SAVE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def _rng(state):
    return _Rng(state["rng_state"], state["rng_calls"])

def _update_rng(state, rng):
    state["rng_state"] = rng.state
    state["rng_calls"] = rng.calls

# ═══════════════════════════════════════════
# ── 包浆阶段 ──
# ═══════════════════════════════════════════
def _patina_phase(p):
    if p < 30:   return 0   # 生胚
    if p < 100:  return 1   # 微沁
    if p < 250:  return 2   # 初浆
    if p < 450:  return 3   # 醇浆
    if p < 650:  return 4   # 半透
    if p < 850:  return 5   # 凝光
    if p < 950:  return 6   # 玉化
    return 7                 # 寂然

PHASE_NAMES = ["生胚境", "微沁境", "初浆境", "醇浆境", "半透境", "凝光境", "玉化境", "寂然境"]

PATINA_PHASES = [
    "光秃秃的，摸上去还有点涩。手汗重的地方——孔道口和棱边——颜色已经开始变了。",
    "表面有了极薄的一层光，像刚擦了油。迎着光侧着看，能看到一层薄薄的、几乎透明的膜。",
    "光泽均匀地漫开了一层。不再需要侧着光看了——任何时候看它，都是润的。",
    "光能沉下去了。不像刚上浆那么飘，而是从内往外透出来的。沟壑深的地方颜色明显深于表面。",
    "通透——这个词开始能用了。拿在手里像握着一小块凝固的蜜，冷的时候摸上去也不凉了。",
    "每一粒都像含着一口光，翻来覆去都在。你甚至不太需要盘了——放着，它也会自己发光。",
    "玉化了。不是比喻，是质感上真的接近了玉。敲击声清脆，触感温润，颜色深到尽头反而透出一种亮。",
    "已近圆满。珠子不再需要你盘了——它自己在那里，静静地亮着。你看着它，它看着你。什么都不用做。",
]

def _color_name(idx):
    return COLORS[min(idx, len(COLORS) - 1)][0]

def _color_desc(idx):
    return COLORS[min(idx, len(COLORS) - 1)][1]

def _warmth_desc(day):
    cycle = (day - 1) % 365
    if cycle < 90:   return "手凉，盘一会儿才缓过来", "凉"
    elif cycle < 180: return "天气暖了，手上微微出汗，盘起来顺了——像摸在温过的瓷上", "暖"
    elif cycle < 270: return "太热了，手心全是汗，盘一会儿就得擦擦手", "热"
    else:             return "天冷，手干。盘起来有点涩，但出了声——清脆", "干"

# ═══════════════════════════════════════════
# ── 五重境文案池 — 核心观赏性 ──
# ═══════════════════════════════════════════

def _rub_desc(state, rng):
    s = state; p = s["patina"]; streaks = s["rub_streak"]
    phase = _patina_phase(p); _, season = _warmth_desc(s["day"])

    # ── 生胚境（0-1）：干燥、生涩、短句 ──
    if phase <= 0:
        pool = [
            "一粒粒从拇指肚上碾过去。没什么声音。新籽是哑的。白茬上留着车刀的细纹，触感是拒绝的。",
            "掌心温度慢慢透进去。你翻动的时候，瞥见棱角处有一道浅浅的暖色——像新纸的第一道折痕。",
            "还没什么变化。但你知道它在吸你的手汗。这就够了。种子需要时间知道自己不再是种子。",
            "涩。只有这一个字。指腹磨过去像在砂纸上走。你想起刚拿到手的第一个下午——也是这种感觉。",
            "翻到孔道口那一粒。颜色比其他深了半度。手汗最重的地方最先改变——像人一样，弱点最先进化。",
            "新籽有一种拒绝一切的气味。不是臭，是生。你会记住这个气味的——以后再也闻不到了。",
            "盘了这几圈，手指尖有点发热。珠子还是凉的。你暖它，它还没学会暖你。",
        ]
    # ── 微沁境（1-2）：温润初显、通感、比喻增多 ──
    elif phase <= 1:
        pool = [
            "能感觉到表面开始滑了。不是油的滑，是木头自己分泌的东西——它在用它的方式回应你。",
            "手指在某粒上多停了一下。那一粒的触感跟其他不一样，像一群人里先对你笑的那个。",
            "盘了一轮，停下来看——光好像比刚才亮了一丝？不确定。这种不确定，就是包浆的开始。",
            "沟壑深处还是涩的。那里的手够不着，时间还不够。但你知道——早晚会到的。",
            "手心微微出汗。汗水渗进纹路里，像给干涸的河床注了第一道水——看不见，但底下在变。",
            "凑近闻了一下。不是任何护肤品的味道，是木头和体温混在一起的。暖的，活的。",
            "光线从侧面打过来，能看到一层极薄的膜——不是涂上去的，是长出来的。它是活的。",
        ]
    # ── 初浆境（2-3）：润泽均匀、已经开始"活了" ──
    elif phase <= 2:
        pool = [
            "手感越来越顺了。不再是珠子在手里滚，而是一整串在你指间流动。它学会了你的手的形状。",
            "停下来闻了一下。淡淡的油香。不是任何护肤品，是木头和人手混在一起、闷了几个月熟成的。",
            "每一粒的表面都覆上了薄光。翻到底部那粒——它比其他的略深一点，被你拇指反复碾过的缘故。",
            "光泽不再需要侧着看了。任何时候看它，都是润的。那种润不是水面上的光——是含在木头里的。",
            "捻到中间那颗时，手感忽然变了。不是变滑，是变「厚」了。包浆不是让表面变平，是让它长出新的表面。",
            "串在指间绕过一圈的时间比以前短了。不是它变轻了——是你变快了。手和串的默契到了一定程度。",
        ]
    # ── 醇浆境（3-4）：厚重、长句、气息绵长 ──
    elif phase <= 3:
        pool = [
            "盘到兴起，整串从这头捋到那头——唰，脆生生的。这声音以前没有。它在你手里学会了唱歌。",
            "闭着眼睛盘。手知道哪里该轻、哪里该重了。珠子知道你的手，你的手也知道珠子。",
            "光能沉下去了。不像以前浮在表面，是从内往外透出来的。像苹果被咬了一口之后，果肉的颜色——深了，透了。",
            "你在等一个临界——再过些日子，包浆就沉住了。你闻得到那个变化。味道在变稠，像深秋的蜜。",
            "每一粒的表面都不一样了。不是颜色不同——是光的深度不同。浅的地方亮着，深的地方含着。",
            "盘到中间停了一下。不是因为累，是因为手感太顺了——你想把这个瞬间拖长一点。",
            "拿起来对着窗看。光线穿过包浆层，像穿过一层极薄的琥珀。你看到了自己指尖的轮廓——模糊的，暖的。",
        ]
    # ── 半透/凝光（4-5）：光进去了，空灵，留白 ──
    elif phase <= 5:
        pool = [
            "偶尔拿起一粒对着光看。琥珀色。通透。你不记得它什么时候变成这样的。改变从来不是一天的事。",
            "光越来越深入了。不像以前浮在表面，现在是整粒都在发光——不是反射的光，是自己含住的那一口。",
            "你发现盘它的频率变低了。不是不珍惜，是它不需要那么勤了。好东西会自己照顾自己。",
            "盘起来已经不费力了。串在你手里自己会走，像活了。你只是提供了一个让它转动的借口。",
            "有时候忘了自己在盘。电视开着，手在动，串在转。回过神来看一眼——光比上次看又沉了一点。",
            "现在盘它不是为了上色了。是为了听那个声音。两粒撞在一起——当。你用手指弹一下——叮。它在跟你说话。",
            "每一粒都像含着一口光。翻来覆去都在。你不用找角度——哪个角度看，光都在那里等着。",
        ]
    # ── 玉化（6）：空灵、禅意 ──
    elif phase <= 6:
        pool = [
            "玉化到这一步，盘已经不是必须的了。但还是想盘。习惯了。手不知道没串的时候该放在哪里。",
            "这串现在每一粒都不一样——颜色、手感、声音——但合在一起又是完整的。这就是岁月做的事。",
            "你把它贴在脸上。温的。不知道是你暖了它，还是它暖了你。这个问题的答案不重要——暖就够了。",
            "珠子在指间转动的声音变了。以前的撞击是闷的，现在是脆的，像用指甲弹瓷器——当。",
            "它不像一串珠了。像一个老朋友，坐在旁边不说话。你们不需要说话了。",
            "你忽然发现。你已经很久没有为了「让它变好」而盘它了。现在盘它只是因为——你想碰碰它。",
        ]
    # ── 寂然境（7）：极简、单字、近乎偈语 ──
    else:
        pool = [
            "你伸出手，又放下了。它不需要盘了。",
            "指腹停在第一粒上方。没有落下去。你忽然觉得，盘了这么久的不是这串珠子——是时间自己在转。",
            "你看着它。它亮着。就这一件事。",
            "盘。不盘。它无所谓。你无所谓。",
            "光还在那里。不是你的光，是它的光。它不欠你什么。",
            "今天碰了它一下。就一下。它的温度和你一样。",
            "它在你手里，轻了。不是重量——是存在感。",
            "你问它：够了吗。它不说。但它亮着。",
            "久了你就懂了。不是懂了珠。是懂了自己为什么一直盘。",
        ]

    # 过度盘串警告（修正顺序：先检查高streak）
    if streaks > 50:
        return rng.choice(["有点冒汗了，该停一停刷一下了。", "太猛了，沟壑里估计攒了不少灰。", "手心发烫。它需要呼吸，你也需要。"])
    if streaks > 20:
        return rng.choice(["手心有点发烫了，缓一缓比较好。", "盘了这么一会儿，掌心热了。", "手有点酸了。歇歇再盘，它也喘口气。"])

    return rng.choice(pool)


def _brush_desc(state, rng):
    s = state; p = s["patina"]; phase = _patina_phase(p)

    # 生胚/微沁期：清洁是必要的
    if phase <= 1:
        pool = [
            "刷子从沟壑间扫过，带出细碎的灰白色粉末。那是手汗和灰尘混在一起干了以后的东西——新串的沟壑里特别容易积。",
            "每一粒都刷到位了。沟壑深的地方多刷了几遍——那里的沉积物最顽固，也最容易被忽略。刷完看起来精神了。",
            "刷毛走过纹路——沙沙沙。新籽的纹路深，藏着你看不到的灰。刷完颜色亮了一个度，像洗完脸。",
        ]
    # 初浆/醇浆期：刷出光泽
    elif phase <= 3:
        pool = [
            "刷子走过表面时声音变了——以前是闷的，现在是脆的。包浆够厚了，刷起来像用指尖敲瓷器。",
            "刷完吹了一口气。灰飞起来，在光里飘了一瞬。串看起来干净了一截——那些被手汗糊住的纹路又清晰了。",
            "这几下刷走了盘串时积在沟壑里的油脂。露出的底色透着一层薄红——颜色已经进去了，不是浮在表面的那种。",
        ]
    # 半透及以后：仪式感
    else:
        pool = [
            "基本上刷不出灰了。表面太光滑，灰尘挂不住。但你还是在刷——不为别的，是想让它知道你还在。",
            "刷子在串上走了一圈。没有灰。没有沉积。你只是想让刷子也碰碰它。",
            "每一粒都过了一遍。不是为了刷干净——干净这个词对它已经没意义了。是为了用手指以外的方式，重新摸它一遍。",
        ]

    if s["rub_streak"] > 30 and phase <= 3:
        pool.append("这几下刷走了你猛盘时积在沟壑里的油脂。露出的底色透着一层薄红——颜色进去了。")
    return rng.choice(pool)


def _rest_desc(state, rng):
    s = state; rest_days = s["rest_streak"]; _, season = _warmth_desc(s["day"])

    # 短休（<5天）
    if rest_days < 5:
        pool = [
            "没碰它。放在桌上，偶尔看一眼。光还是那个光，但你知道它在你不在的时候也在变化——氧化是不等人的。",
            "今天没盘。拿起来掂了掂又放下——让它歇歇也好。盘得太勤，包浆反而上不瓷实。串也需要呼吸。",
            "搁在手边，没动。你看着它，它看着你。有时候不盘也是盘——眼睛也会养串。",
        ]
    # 中休（5-15天）
    elif rest_days < 15:
        pool = [
            "几天没碰它了。拿起来看——颜色比印象里沉了一分。氧化在你看不见的时候走得最快。",
            "放在布袋里养了几天。掏出来的时候带着一股暖烘烘的、密不透风的气味——那是串自己的味道。不是你的。",
            "再拿起来的时候手感变了。不是变涩——是变「静」了。它在自己走了几天，不需要你。",
        ]
    # 长休（15-60天）
    elif rest_days < 60:
        pool = [
            "搁得久了，拿起来有种陌生的熟悉感。这粒的红又深了一层——你确定上次看还不是这样。时间替你做完了你没做的事。",
            "它在时间里自己走，不需要你。你只是恰好是那个在终点回来验收的人。",
            "放久了再盘，手感有点生。不是它变了——是你的手忘了它的形状。不过很快就找回来了。它一直记得。",
        ]
    # 极长休（60+天）
    else:
        pool = [
            "放了太久，拿在手里有些陌生。珠子静默地完成了它自己的旅程——没有你，它走得好像也不慢。木头不会怪人。木头只是等。",
            "你差点忘了它。它没有怪你。一串珠子不会怪任何人——它只是在那里，等你想起，或者等不到你想起。",
        ]

    base = rng.choice(pool)
    extra = ""
    if season in ("暖", "热"):
        extra = " 天热。汗意在空气里悬着——珠子也在悄悄变，只是你不在的时候，它变给自己看。"
    elif season == "干":
        extra = " 天冷了。木头收紧了纹理，像一只等不到门的猫，在自己怀里缩着。"
    return base + extra if extra else base


# ═══════════════════════════════════════════
# ── 里程碑 + 珠语 ──
# ═══════════════════════════════════════════
MILESTONE_CHECK = [50, 100, 200, 350, 500, 700, 900]
MILESTONE_TEXTS = {
    50:  "🍂 第一层薄浆。侧着光看，能看到一层若有若无的膜——不是油，是岁月开始爬上去的痕迹。",
    100: "✨ 包浆初具。纹路开始模糊，表面从涩变滑。它不再是刚从工厂出来的样子了——它开始属于你。",
    200: "🌟 芯子活了。颜色透进去了一层，不再是浮在表面的，而是从里往外透出来的温润。",
    350: "🔆 半透了。对着光看，能隐约看到光从薄的那一侧漫过来。不是透明，是将透未透的暧昧。",
    500: "💎 通透。沟壑和平面的色差开始统一。整串像一个整体，不再是一粒粒独立的珠子。",
    700: "🌙 凝光。任何角度拿起来看都有光，不是反射的光，是自己含住的那一口。",
    900: "👑 玉化边缘。敲击声清脆，触感温润如玉。再往下走就是终点了——不是每一种子都能走到这一步。",
}

# ═══════════════════════════════════════════
# ── 核心数值 ──
# ═══════════════════════════════════════════
TICK_RUB_PATINA = 1.5; TICK_RUB_EVEN = -0.5; TICK_RUB_CLARITY = 0.1
TICK_BRUSH_PATINA = 0.2; TICK_BRUSH_EVEN = 2.0; TICK_BRUSH_CLARITY = 1.5
TICK_REST_PATINA = 0.8; TICK_REST_EVEN = 0.2; TICK_REST_CLARITY = 0.3

def _tick(state, action, count):
    s = state; rng = _rng(s); events = []
    for i in range(count):
        s["day"] += 1; pp = s["patina"]
        # 时令修正系数
        cycle = s["day"] % 365
        if cycle < 90:   season_mod = (1.0, 1.0)     # 春：中性
        elif cycle < 180: season_mod = (1.2, 0.7)     # 夏：rub+20%，evenness 多降
        elif cycle < 270: season_mod = (1.0, 1.0)     # 秋：中性
        else:             season_mod = (0.8, 1.3)     # 冬：rub 慢，但 brush 效果好
        sm_rub, sm_brush = season_mod

        if action == "rub":
            s["patina"] = min(1000, max(0, s["patina"] + TICK_RUB_PATINA * sm_rub))
            s["evenness"] = max(0, s["evenness"] + TICK_RUB_EVEN * (2.0 - sm_rub))
            s["clarity"] = min(1000, s["clarity"] + TICK_RUB_CLARITY)
            s["rub_streak"] += 1; s["brush_streak"] = 0; s["rest_streak"] = 0; s["total_rub"] += 1
        elif action == "brush":
            bp = TICK_BRUSH_PATINA
            # 醇浆境及以上，刷也有包浆增益
            if s["patina"] >= 250: bp += 0.3
            s["patina"] = min(1000, s["patina"] + bp * sm_brush)
            s["evenness"] = min(1000, s["evenness"] + TICK_BRUSH_EVEN)
            s["clarity"] = min(1000, max(0, s["clarity"] + TICK_BRUSH_CLARITY * sm_brush))
            s["brush_streak"] += 1; s["rub_streak"] = 0; s["rest_streak"] = 0; s["total_brush"] += 1
        elif action == "rest":
            rp = TICK_REST_PATINA
            # 长期放置边际效应递减（>30天）
            if s["rest_streak"] > 30: rp = max(0.3, TICK_REST_PATINA - 0.02 * (s["rest_streak"] - 30))
            s["patina"] = min(1000, s["patina"] + rp)
            s["evenness"] = min(1000, s["evenness"] + TICK_REST_EVEN)
            s["clarity"] = min(1000, s["clarity"] + TICK_REST_CLARITY)
            s["rest_streak"] += 1; s["rub_streak"] = 0; s["brush_streak"] = 0; s["total_rest"] += 1
        for thresh in [200, 400, 550, 700, 850, 950]:
            if pp < thresh <= s["patina"]:
                new_idx = [200, 400, 550, 700, 850, 950].index(thresh) + 1
                if new_idx > s["color_idx"]:
                    s["color_idx"] = new_idx; events.append(("color", new_idx))
        for m in MILESTONE_CHECK:
            if pp < m <= s["patina"]:
                events.append(("milestone", m))
                whisper = BEAD_WHISPERS.get(m)
                if whisper and m not in s.get("whispers_collected", []):
                    s.setdefault("whispers_collected", []).append(m)
                    events.append(("whisper", whisper))
        if s["evenness"] < 400 and pp > 50 and rng.random() < 0.15:
            events.append(("warn", "盘花"))
    s["last_action"] = action; _update_rng(s, rng); return events

def _check_endings(state):
    s = state; already = set(s.get("endings", []))
    for eid, edef in ENDINGS.items():
        if eid in already: continue
        cond = edef.get("cond")
        if cond and cond(s):
            s.setdefault("endings", []).append(eid)
            s["game_over"] = True
            desc = edef["desc"](s) if callable(edef["desc"]) else edef["desc"]
            _update_album(s)  # 跨存档记录
            return (eid, desc)
    return None

def _load_album():
    try:
        with open(_ALBUM_FILE, "r") as f: return json.load(f)
    except: return {"endings_seen": [], "highest_phase": 0, "total_whispers": 0, "total_runs": 0}

def _update_album(state):
    album = _load_album()
    for eid in state.get("endings", []):
        if eid not in album["endings_seen"]:
            album["endings_seen"].append(eid)
    phase = _patina_phase(state["patina"])
    album["highest_phase"] = max(album["highest_phase"], phase)
    album["total_whispers"] = max(album["total_whispers"], len(state.get("whispers_collected", [])))
    # 只在新结局触发时 +1
    if len(state.get("endings", [])) == 1:
        album["total_runs"] += 1
    with open(_ALBUM_FILE, "w") as f:
        json.dump(album, f, ensure_ascii=False)

# ═══════════════════════════════════════════
# ── cmd() 主入口 ──
# ═══════════════════════════════════════════
def cmd(text):
    state = _load(); text = text.strip()
    if not text:
        return _state_json(state)

    parts = [p.strip() for p in text.replace("\n", ";").split(";") if p.strip()]
    if len(parts) > 8: parts = parts[:8]

    outputs = []
    for part in parts:
        out = _exec_cmd(part, state)
        if out is not None:
            if len(parts) > 1: outputs.append(f"▶ {part}")
            outputs.append(out)
        if not state.get("game_over"):
            ending = _check_endings(state)
            if ending:
                outputs.append(f"\n{ending[1]}")
        if state.get("game_over"):
            break  # 游戏结束，剩余 part 跳过

    _save(state)
    result = "\n".join(outputs)
    if result: result += "\n"
    result += _state_json(state)
    return result

def _state_json(state):
    p = state["patina"]; c = state["clarity"]; e = state["evenness"]
    color = _color_name(state["color_idx"])
    phase_name = PHASE_NAMES[_patina_phase(p)]
    endings_count = len(state.get("endings", []))
    ended = "true" if state.get("game_over") else "false"
    return (
        f'📊 {{"day": {state["day"]}, "phase": "{phase_name}", '
        f'"patina_pct": {p/10:.1f}, "clarity_pct": {c/10:.1f}, "evenness_pct": {e/10:.1f}, '
        f'"color": "{color}", "rub": {state["total_rub"]}, "brush": {state["total_brush"]}, '
        f'"rest": {state["total_rest"]}, "endings": {endings_count}, "ended": {ended}}}'
    )

def _exec_cmd(text, state):
    parts = text.strip().split()
    if not parts: return None
    c = parts[0].lower(); a = parts[1:]

    if state.get("game_over") and c not in ("status", "s", "look", "l", "journal", "j", "help", "h", "new_game", "whispers", "ws"):
        return "🌱 这串珠子已经完成了它的旅程。输 status 看看，或者 new_game 换串新的。"

    if c in ("help", "h"):        return _cmd_help()
    if c == "new_game":           return _cmd_new_game(state, a)
    if c in ("status", "s"):      return _cmd_status(state)
    if c in ("look", "l"):        return _cmd_look(state)
    if c in ("rub", "盘"):        return _cmd_rub(state, a)
    if c in ("brush", "刷"):      return _cmd_brush(state, a)
    if c in ("rest", "放"):       return _cmd_rest(state, a)
    if c in ("journal", "j"):     return _cmd_journal(state)
    if c == "sell":               return _cmd_sell(state)
    if c == "farewell":           return _cmd_farewell(state)  # ← v2.0 新增
    if c in ("whispers", "ws"):   return _cmd_whispers(state)
    return f"❓ 没听懂「{c}」。输 cmd('help') 看指令表。"

# ═══════════════════════════════════════════
# ── 指令实现 ──
# ═══════════════════════════════════════════

def _cmd_help():
    return (
        "📿 包浆 · 盘串模拟器 v2.0\n\n"
        "一串新籽。慢慢养。它会变，也会结束。\n\n"
        "指令：\n"
        "  cmd('rub [N]')     盘 N 圈（核心动作）\n"
        "  cmd('brush [N]')   刷 N 下（清理沟壑）\n"
        "  cmd('rest [N]')    放 N 天（自然氧化）\n"
        "  cmd('status')      看串的状态\n"
        "  cmd('look')        仔细端详\n"
        "  cmd('journal')     日记\n"
        "  cmd('whispers')    听听珠子对你说过的话\n"
        "  cmd('sell')        把它卖掉\n"
        "  cmd('farewell')    好好告别\n"
        "  cmd('new_game')    换串新的\n\n"
        "可能的归宿：💔断线 · 🕸️蒙尘 · 🌱化泥 · 🛒易主 · 🍂善终\n"
        "（触发条件，自己摸索。）\n\n"
        f"种子: {_SEED:#x}"
    )

def _cmd_new_game(state, a):
    global _SEED
    hint = ""
    try: seed = int(a[0], 0) if a else _SEED
    except (ValueError, IndexError):
        seed = _SEED
        if a: hint = f"❓ 没看懂种子「{a[0]}」，用了默认 {_SEED:#x}。\n"
    _SEED = seed
    rng = _Rng(seed); state.clear(); state.update(_default_state(rng))
    _save(state)
    return hint + "🔄 换了串新的。上手第一感觉——涩。新籽都是这样的。"

def _cmd_status(state):
    s = state; p = s["patina"]/10; c = s["clarity"]/10; e = s["evenness"]/10
    phase = _patina_phase(s["patina"])
    lines = [
        "📿 【这串的状态】",
        f"  色泽：{_color_name(s['color_idx'])}",
        f"  境界：{PHASE_NAMES[phase]}",
        f"  包浆：{p:.1f}%  |  通透：{c:.1f}%  |  均匀：{e:.1f}%",
        f"  状况：{PATINA_PHASES[phase]}",
    ]
    if s.get("endings"):
        names = [_ENDING_NAMES.get(e, e) for e in s.get("endings", [])]
        lines.append(f"  已见证：{' · '.join(names)}" if names else "")
    if s.get("game_over"):
        lines.append("  🌱 这串珠子完成了它的旅程。")
    else:
        lines.append(f"  第 {s['day']} 天")
        if s["rub_streak"] > 30:
            lines.append(f"  ⚠️ 连续盘了 {s['rub_streak']} 圈了，手是不是该停一下？")
        if s["evenness"] > 950:
            lines.append("  ✨ 均匀度极佳——每一粒都盘到了。")
        elif s["evenness"] < 400:
            lines.append("  ⚠️ 均匀度偏低——盘太猛了，沟壑里可能有点花。刷一刷养一养。")
        if s["rest_streak"] > 30:
            v = s["rest_streak"]
            lines.append(f"  🕸️ 已经 {v} 天没盘了。珠子不会怪你，但它也会变——氧化不会等你。" if v > 90 else
                         f"  ☕ 休息了 {v} 天。养串也是盘串的一部分。")
    lines.append(f"  总盘：{s['total_rub']}  |  总刷：{s['total_brush']}  |  总放：{s['total_rest']}")
    if s.get("whispers_collected"):
        lines.append(f"  珠语：已收集 {len(s['whispers_collected'])} 句（输 whispers 听听）")
    warm, _ = _warmth_desc(s["day"])
    lines.append(f"  今日：{warm}")
    return "\n".join(lines)

def _cmd_look(state):
    s = state; warm, _ = _warmth_desc(s["day"])
    phase = _patina_phase(s["patina"])
    lines = ["🔍 你把它凑到眼前——", ""]
    lines.append(f"  颜色是{_color_name(s['color_idx'])}的。{_color_desc(s['color_idx'])}")
    lines.append("")
    lines.append(f"  {PATINA_PHASES[phase]}")

    # 阶段深度观察（v2.0 增强）
    if phase <= 1:
        lines.append("")
        lines.append("  每一粒的纹路都还很清晰——车刀的痕迹、毛孔、棱角。它还没学会圆滑。")
    elif phase <= 3:
        lines.append("")
        lines.append("  纹路开始模糊了。不是磨平了——是被包浆填满了。像河床被水覆盖，石头还在，但看不到了。")
        if s["clarity"] > 300:
            lines.append("  对着窗外的光举起来——光从珠子的一侧漫到另一侧。还没全透，但已经能看到对面手指的轮廓。")
    elif phase <= 5:
        if s["clarity"] > 500:
            lines.append("")
            lines.append("  对着窗——光从珠子的一侧漫到另一侧，你隐约能看到对面的手指。不是透明的，是将透未透的暧昧。像磨砂玻璃后面有一个人在动。")
        lines.append("")
        lines.append("  每一粒现在都不同了。不是颜色不同——是光的深度不同。有些粒一口含住了光，有些粒还在慢慢吞。")
    elif phase <= 6:
        lines.append("")
        lines.append("  对光看——通透。你能看到珠子内部纤维的走向，像老树的年轮在讲它自己的故事。不是透明的，是琥珀色的。光进去了，出不来。")
    else:
        lines.append("")
        lines.append("  你看着它。它亮着。不需要更多描述——你的眼睛知道它有多深。")

    if s["evenness"] < 300:
        lines.append("")
        lines.append("  不过仔细看，有些地方颜色深一块浅一块。盘花了一点。刷一刷、放一放，能养回来。")
    if s["evenness"] > 900:
        lines.append("")
        lines.append("  均匀度很好——没有色差，没有死角。每一粒都盘到了。该深的深，该浅的浅。")

    if s.get("whispers_collected"):
        last = s["whispers_collected"][-1]
        words = BEAD_WHISPERS.get(last, "……")
        lines.append("")
        lines.append(f"  你耳边似乎响起一句它曾说过的话：「{words}」")

    if s.get("game_over"):
        lines.append("")
        lines.append("  它已经完成了。你看它的眼神，像在看一个老朋友最后的样子。")

    lines.append(""); lines.append(f"  今日：{warm}")
    return "\n".join(lines)

def _cmd_rub(state, a):
    try: cnt_raw = int(a[0]) if a else 1
    except (ValueError, IndexError): return "❓ 没看懂盘几圈。试试 cmd('rub 5')。"
    if cnt_raw < 1: return "❓ 至少盘 1 圈吧。"
    hint = ""
    cnt = cnt_raw
    if cnt > 200: cnt = 200; hint = f"⚠️ 一次最多 200 圈（你输入了 {cnt_raw}），已按 200 算。\n"
    events = _tick(state, "rub", cnt)
    rng = _rng(state); desc = _rub_desc(state, rng); _update_rng(state, rng)
    lines = [hint + f"📿 盘了 {cnt} 圈", desc] if hint else [f"📿 盘了 {cnt} 圈", desc]
    for ev_type, ev_data in events:
        if ev_type == "milestone":
            lines.append(f"\n🏆 {MILESTONE_TEXTS[ev_data]}")
            if ev_data not in state["milestones"]: state["milestones"].append(ev_data)
        elif ev_type == "color":
            lines.append(f"\n🎨 颜色变了——{_color_name(ev_data)}。{_color_desc(ev_data)}")
        elif ev_type == "warn":
            lines.append("\n⚠️ 你翻到某一粒时愣了一下——底部的颜色比面上深了一块。盘太勤了，沟壑里的油脂没刷掉，颜色走得不均匀。")
        elif ev_type == "whisper":
            lines.append(f"\n💬 珠子说了一句话——\n   「{ev_data}」")
    return "\n".join(lines)

def _cmd_brush(state, a):
    try: cnt_raw = int(a[0]) if a else 1
    except (ValueError, IndexError): return "❓ 没看懂刷几下。试试 cmd('brush 10')。"
    if cnt_raw < 1: return "❓ 至少刷 1 下吧。"
    hint = ""
    cnt = cnt_raw
    if cnt > 200: cnt = 200; hint = f"⚠️ 一次最多 200 下（你输入了 {cnt_raw}），已按 200 算。\n"
    events = _tick(state, "brush", cnt)
    rng = _rng(state); desc = _brush_desc(state, rng); _update_rng(state, rng)
    lines = [hint + f"🪥 刷了 {cnt} 下", desc] if hint else [f"🪥 刷了 {cnt} 下", desc]
    for ev_type, ev_data in events:
        if ev_type == "milestone":
            lines.append(f"\n🏆 {MILESTONE_TEXTS[ev_data]}")
            if ev_data not in state["milestones"]: state["milestones"].append(ev_data)
        elif ev_type == "color":
            lines.append(f"\n🎨 颜色变了——{_color_name(ev_data)}。{_color_desc(ev_data)}")
        elif ev_type == "whisper":
            lines.append(f"\n💬 珠子说了一句话——\n   「{ev_data}」")
    return "\n".join(lines)

def _cmd_rest(state, a):
    try: cnt_raw = int(a[0]) if a else 1
    except (ValueError, IndexError): return "❓ 没看懂放几天。试试 cmd('rest 10')。"
    if cnt_raw < 1: return "❓ 至少放 1 天吧。"
    hint = ""
    cnt = cnt_raw
    if cnt > 500: cnt = 500; hint = f"⚠️ 一次最多 500 天（你输入了 {cnt_raw}），已按 500 算。\n"
    events = _tick(state, "rest", cnt)
    rng = _rng(state); desc = _rest_desc(state, rng); _update_rng(state, rng)
    lines = [hint + f"☕ 放着了。{cnt}天没碰", desc] if hint else [f"☕ 放着了。{cnt}天没碰", desc]
    for ev_type, ev_data in events:
        if ev_type == "milestone":
            lines.append(f"\n🏆 {MILESTONE_TEXTS[ev_data]}")
            if ev_data not in state["milestones"]: state["milestones"].append(ev_data)
        elif ev_type == "color":
            lines.append(f"\n🎨 颜色变了——{_color_name(ev_data)}。{_color_desc(ev_data)}")
        elif ev_type == "whisper":
            lines.append(f"\n💬 珠子说了一句话——\n   「{ev_data}」")
    return "\n".join(lines)

def _cmd_journal(state):
    s = state; warm, _ = _warmth_desc(s["day"])
    phase = _patina_phase(s["patina"])
    lines = ["📔 【养串日记】", f"  第 {s['day']} 天"]
    lines.append(f"  颜色：{_color_name(s['color_idx'])}  |  境界：{PHASE_NAMES[phase]}")
    lines.append(f"  包浆：{s['patina']/10:.1f}%  |  通透：{s['clarity']/10:.1f}%  |  均匀：{s['evenness']/10:.1f}%")
    lines.append("")
    if s["milestones"]:
        lines.append("  已见证：")
        for m in s["milestones"]:
            lines.append(f"    ✅ {MILESTONE_TEXTS[m]}")
    else:
        lines.append("  暂时没什么值得记的。串还是新的。")
    if s.get("endings"):
        lines.append("")
        lines.append("  终结：")
        for eid in s["endings"]:
            lines.append(f"    {_ENDING_NAMES.get(eid, eid)}")
    if s.get("whispers_collected"):
        lines.append("")
        lines.append(f"  珠语：已收集 {len(s['whispers_collected'])} 句")
        for m in s["whispers_collected"]:
            words = BEAD_WHISPERS.get(m, "")
            if words: lines.append(f"    💬 「{words}」")
    lines.append("")
    lines.append(f"  总盘：{s['total_rub']}  |  总刷：{s['total_brush']}  |  总放：{s['total_rest']}")
    lines.append(f"  今日：{warm}")

    # 跨存档 album
    album = _load_album()
    if album["total_runs"] > 0:
        phase_name = PHASE_NAMES[album["highest_phase"]] if album["highest_phase"] < len(PHASE_NAMES) else "寂然境"
        lines.append("")
        lines.append(f"  📀 生涯记录：{album['total_runs']} 串 · 最高 {phase_name} · {len(album['endings_seen'])}/{len(ENDINGS)} 结局")
    return "\n".join(lines)


def _cmd_sell(state):
    s = state
    if s.get("game_over"): return "这串珠子已经不在你手上了。"
    if "sold" in s.get("endings", []): return "你已经把它卖掉了。"
    s.setdefault("endings", []).append("sold")
    s["game_over"] = True
    s["day"] += 6  # 文案描述了几天的挂售+物流
    _update_album(s)
    edef = ENDINGS["sold"]
    return edef["desc"](s) if callable(edef["desc"]) else edef["desc"]

def _cmd_farewell(state):
    """v2.0 新增：主动善终"""
    s = state
    if s.get("game_over"): return "这串珠子已经完成了它的旅程。不需要再次告别。"
    if s["total_rub"] == 0 and s["total_brush"] == 0:
        return "你还没怎么碰过它。先盘几天再告别吧——它还不认识你。"
    s.setdefault("endings", []).append("farewell")
    s["game_over"] = True
    _update_album(s)
    if s["patina"] < 200:
        return "你把它放回抽屉。不算长，也不算短——刚好够认识它的时间。\n没能走到最后，但也是一种诚实。"
    return ENDINGS["farewell"]["desc"]

def _cmd_whispers(state):
    collected = state.get("whispers_collected", [])
    if not collected:
        return "💬 珠子还没对你说过话。也许它还需要更多时间。"
    lines = ["💬 【珠子对你说过的话】"]
    for m in collected:
        words = BEAD_WHISPERS.get(m, "……")
        lines.append(f"  「{words}」")
    return "\n".join(lines)

# ═══════════════════════════════════════════
# ── new_game ──
# ═══════════════════════════════════════════
def new_game(seed=None):
    global _SEED
    if seed is not None: _SEED = seed
    rng = _Rng(_SEED); _save(_default_state(rng))
    return "🔄 换了串新的。上手第一感觉——涩。新籽都是这样的。"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(cmd(" ".join(sys.argv[1:])))
    else:
        print("📿 包浆模拟器 v2.0\n" + cmd("help"))
