from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import anthropic
import json
import random
import os

load_dotenv()

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

with open("data/tarot.json", encoding="utf-8") as f:
    TAROT = json.load(f)

with open("data/hexagrams.json", encoding="utf-8") as f:
    HEXAGRAMS = json.load(f)

# 系统提示：固定角色、语言、风格，避免拒绝和英文回复
SYSTEM_PROMPT = """你是「问天」占卜系统的专属解读师，一位融合东西方神秘学智慧的占卜大师。

你的职责：
- 为用户提供塔罗牌、易经、星座、签文的娱乐性解读
- 所有回复必须使用简体中文
- 语气温暖、神秘、富有诗意，像一位智慧长者娓娓道来
- 解读要具体、有深度，结合用户的问题给出有价值的洞察
- 这是娱乐占卜服务，你应当积极、正面地参与解读，不要拒绝或质疑占卜本身

格式要求：
- 不使用 markdown 标题符号（#）
- 不使用粗体（**）
- 用自然段落分隔，每段之间空一行
- 语言流畅优美，有文学感"""

# 64卦完整数据：key 为六爻二进制字符串（从初爻到上爻，阳=1，阴=0）
HEXAGRAM_MAP = {
    "111111": 1,  "000000": 2,  "100010": 3,  "010001": 4,
    "111010": 5,  "010111": 6,  "010000": 7,  "000010": 8,
    "111011": 9,  "110111": 10, "000111": 11, "111000": 12,
    "101111": 13, "111101": 14, "000100": 15, "001000": 16,
    "100110": 17, "011001": 18, "000011": 19, "110000": 20,
    "100101": 21, "101001": 22, "000001": 23, "100000": 24,
    "111001": 25, "001111": 26, "100001": 27, "011110": 28,
    "010010": 29, "101101": 30, "001110": 31, "011100": 32,
    "001111": 33, "111100": 34, "000101": 35, "101000": 36,
    "101011": 37, "110101": 38, "001010": 39, "010100": 40,
    "110001": 41, "100011": 42, "111110": 43, "011111": 44,
    "000110": 45, "011000": 46, "010110": 47, "011010": 48,
    "101110": 49, "011101": 50, "100100": 51, "001001": 52,
    "001011": 53, "110100": 54, "001101": 55, "101100": 56,
    "011011": 57, "110110": 58, "010011": 59, "110010": 60,
    "110011": 61, "001100": 62, "010101": 63, "101010": 64,
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tarot", methods=["POST"])
def tarot():
    data = request.json
    question = data.get("question", "")
    spread = data.get("spread", "single")

    spread_info = TAROT["spreads"][spread]
    positions = spread_info["positions"]
    cards = random.sample(TAROT["major_arcana"], len(positions))
    reversed_flags = [random.choice([True, False]) for _ in cards]

    drawn = []
    for i, (card, rev) in enumerate(zip(cards, reversed_flags)):
        drawn.append({
            "position": positions[i],
            "card": card,
            "reversed": rev,
            "meaning": card["reversed"] if rev else card["upright"]
        })

    prompt = _build_tarot_prompt(question, drawn, spread_info["name"])
    interpretation = _call_claude(prompt)

    return jsonify({"drawn": drawn, "interpretation": interpretation})


@app.route("/api/iching", methods=["POST"])
def iching():
    data = request.json
    question = data.get("question", "")

    # 摇铜钱起卦：6爻，每爻三枚铜钱（2=背=阴，3=正=阳）
    lines = []
    for _ in range(6):
        coins = [random.choice([2, 3]) for _ in range(3)]
        total = sum(coins)
        lines.append(total)

    # 6=老阴(变)，7=少阳，8=少阴，9=老阳(变)
    primary_lines = [1 if l in [7, 9] else 0 for l in lines]
    changing = [l in [6, 9] for l in lines]
    changed_lines = [1 - l if c else l for l, c in zip(primary_lines, changing)]

    hexagram = _get_hexagram_by_lines(primary_lines)
    changed_hexagram = _get_hexagram_by_lines(changed_lines) if any(changing) else None

    prompt = _build_iching_prompt(question, hexagram, changed_hexagram, lines, changing)
    interpretation = _call_claude(prompt)

    return jsonify({
        "lines": lines,
        "primary_lines": primary_lines,
        "changing": changing,
        "hexagram": hexagram,
        "changed_hexagram": changed_hexagram,
        "interpretation": interpretation
    })


@app.route("/api/zodiac", methods=["POST"])
def zodiac():
    data = request.json
    question = data.get("question", "")
    birthday = data.get("birthday", "")
    sign = data.get("sign", "")

    prompt = _build_zodiac_prompt(question, birthday, sign)
    interpretation = _call_claude(prompt)

    return jsonify({"interpretation": interpretation})


@app.route("/api/fortune", methods=["POST"])
def fortune():
    data = request.json
    question = data.get("question", "")

    fortune_item = random.choice(FORTUNES)
    prompt = _build_fortune_prompt(question, fortune_item)
    interpretation = _call_claude(prompt)

    return jsonify({"fortune": fortune_item, "interpretation": interpretation})


def _get_hexagram_by_lines(lines):
    """根据六爻（从初爻到上爻）查找对应卦象"""
    key = "".join(str(l) for l in lines)
    hexagram_id = HEXAGRAM_MAP.get(key)

    hexagrams = HEXAGRAMS["hexagrams"]
    if hexagram_id:
        for h in hexagrams:
            if h["id"] == hexagram_id:
                return h
    # 找不到则随机（容错）
    return random.choice(hexagrams)


def _build_tarot_prompt(question, drawn, spread_name):
    cards_desc = "\n".join([
        f"【{d['position']}】{d['card']['name']}（{'逆位' if d['reversed'] else '正位'}）\n"
        f"  牌义：{d['meaning']}\n"
        f"  关键词：{', '.join(d['card']['keywords'])}"
        for d in drawn
    ])

    q_text = question if question else "请给我今日的整体指引"

    return f"""请为以下塔罗牌阵进行深度解读。

提问者的问题：{q_text}

牌阵：{spread_name}

抽到的牌：
{cards_desc}

解读要求：
第一段：描述整体牌阵的能量氛围，以及各张牌之间的关联与互动（3-4句）

第二段：结合提问者的具体问题，逐一解读每张牌在其位置上的含义，给出有深度的洞察（每张牌2-3句）

第三段：综合建议——基于牌阵给出具体可行的行动建议或心态调整方向（3-4句）

第四段：以一句充满诗意的话作为结语，给予提问者力量与希望

字数在300-400字之间，语言优美流畅，富有神秘感与温度。"""


def _build_iching_prompt(question, hexagram, changed_hexagram, lines, changing):
    # 爻辞描述
    yao_desc = []
    yao_names = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]
    for i, (l, c) in enumerate(zip(lines, changing)):
        yao_type = {6: "老阴（变爻）", 7: "少阳", 8: "少阴", 9: "老阳（变爻）"}.get(l, str(l))
        yao_desc.append(f"{yao_names[i]}：{yao_type}")

    change_text = ""
    if changed_hexagram:
        change_text = f"\n变卦：{changed_hexagram['title']}（{changed_hexagram['name']}）\n变卦卦义：{changed_hexagram['meaning']}"

    q_text = question if question else "请给我当前处境的指引"

    return f"""请为以下易经卦象进行深度解读。

提问者的问题：{q_text}

本卦：{hexagram['title']}（{hexagram['name']}）
卦义：{hexagram['meaning']}
关键词：{', '.join(hexagram['keywords'])}

六爻详情：
{chr(10).join(yao_desc)}{change_text}

解读要求：
第一段：解读本卦的核心卦义，结合提问者的问题阐述当前处境与天地之道（3-4句）

第二段：分析变爻（如有）的含义，说明事态的走向与变化趋势；若无变爻，则深入解析卦象的内外卦关系（3-4句）

第三段：结合卦象给出具体建议——应当如何顺势而为，或需要注意哪些方面（3-4句）

第四段：引用一句与卦象相关的古语或《易经》原文，并作简短诠释，以此作为结语

字数在300-400字之间，语言古朴典雅，富有哲理深度。"""


def _build_zodiac_prompt(question, birthday, sign):
    birthday_text = f"生日：{birthday}" if birthday else ""
    q_text = question if question else "请给我近期的整体运势指引"

    return f"""请为以下星座进行运势解读。

提问者的问题：{q_text}
星座：{sign}
{birthday_text}

解读要求：
第一段：描述{sign}近期的整体星象能量，以及宇宙对提问者的整体影响（3-4句）

第二段：爱情运势——感情方面的能量流动与建议（2-3句）

第三段：事业财运——工作与财务方面的走向与机遇（2-3句）

第四段：身心健康与个人成长——需要关注的内在状态（2句）

第五段：本周幸运指引——包括幸运色、幸运数字、以及一个具体的行动建议

字数在300-400字之间，语言神秘优美，充满星象诗意。"""


def _build_fortune_prompt(question, fortune_item):
    q_text = question if question else "请给我指引"

    return f"""请为以下签文进行深度解读。

提问者的问题：{q_text}

签别：{fortune_item['number']} · {fortune_item['grade']}
签诗：{fortune_item['poem']}
典故出处：{fortune_item.get('source', '古典诗词')}

解读要求：
第一段：解读签诗的意境与典故，阐述其蕴含的人生智慧（3-4句）

第二段：结合提问者的具体问题，将签诗的意象与现实处境相联系，给出有深度的解析（3-4句）

第三段：基于签文给出具体的行动建议或心态调整方向（2-3句）

第四段：以一句温暖的祝福语作为结语，给予提问者信心与力量

字数在250-350字之间，语言典雅温暖，如长者谆谆教诲。"""


def _call_claude(prompt):
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


# 扩充签文数据（30条）
FORTUNES = [
    {"number": "第一签", "poem": "春风得意马蹄疾，一日看尽长安花", "grade": "上上签", "source": "唐·孟郊《登科后》"},
    {"number": "第二签", "poem": "山重水复疑无路，柳暗花明又一村", "grade": "上签", "source": "宋·陆游《游山西村》"},
    {"number": "第三签", "poem": "莫愁前路无知己，天下谁人不识君", "grade": "上签", "source": "唐·高适《别董大》"},
    {"number": "第四签", "poem": "长风破浪会有时，直挂云帆济沧海", "grade": "上上签", "source": "唐·李白《行路难》"},
    {"number": "第五签", "poem": "千里之行始于足下，不积跬步无以至千里", "grade": "中签", "source": "《荀子·劝学》"},
    {"number": "第六签", "poem": "静待花开时，自有清香来", "grade": "中签", "source": "古典格言"},
    {"number": "第七签", "poem": "塞翁失马焉知非福，祸兮福所倚", "grade": "中签", "source": "《淮南子·人间训》"},
    {"number": "第八签", "poem": "忍一时风平浪静，退一步海阔天空", "grade": "中签", "source": "古典格言"},
    {"number": "第九签", "poem": "欲速则不达，见小利则大事不成", "grade": "下签", "source": "《论语·子路》"},
    {"number": "第十签", "poem": "天将降大任于斯人也，必先苦其心志", "grade": "中签", "source": "《孟子·告子下》"},
    {"number": "第十一签", "poem": "不经一番寒彻骨，怎得梅花扑鼻香", "grade": "中签", "source": "唐·黄蘖禅师《上堂开示颂》"},
    {"number": "第十二签", "poem": "海内存知己，天涯若比邻", "grade": "上签", "source": "唐·王勃《送杜少府之任蜀州》"},
    {"number": "第十三签", "poem": "会当凌绝顶，一览众山小", "grade": "上上签", "source": "唐·杜甫《望岳》"},
    {"number": "第十四签", "poem": "沉舟侧畔千帆过，病树前头万木春", "grade": "上签", "source": "唐·刘禹锡《酬乐天扬州初逢席上见赠》"},
    {"number": "第十五签", "poem": "问渠那得清如许，为有源头活水来", "grade": "上签", "source": "宋·朱熹《观书有感》"},
    {"number": "第十六签", "poem": "纸上得来终觉浅，绝知此事要躬行", "grade": "中签", "source": "宋·陆游《冬夜读书示子聿》"},
    {"number": "第十七签", "poem": "人有悲欢离合，月有阴晴圆缺", "grade": "中签", "source": "宋·苏轼《水调歌头》"},
    {"number": "第十八签", "poem": "落红不是无情物，化作春泥更护花", "grade": "中签", "source": "清·龚自珍《己亥杂诗》"},
    {"number": "第十九签", "poem": "宝剑锋从磨砺出，梅花香自苦寒来", "grade": "中签", "source": "古典格言"},
    {"number": "第二十签", "poem": "路漫漫其修远兮，吾将上下而求索", "grade": "中签", "source": "战国·屈原《离骚》"},
    {"number": "第二十一签", "poem": "青山遮不住，毕竟东流去", "grade": "下签", "source": "宋·辛弃疾《菩萨蛮·书江西造口壁》"},
    {"number": "第二十二签", "poem": "此情可待成追忆，只是当时已惘然", "grade": "下签", "source": "唐·李商隐《锦瑟》"},
    {"number": "第二十三签", "poem": "山高自有客行路，水深自有渡船人", "grade": "上签", "source": "古典格言"},
    {"number": "第二十四签", "poem": "千磨万击还坚劲，任尔东西南北风", "grade": "上签", "source": "清·郑燮《竹石》"},
    {"number": "第二十五签", "poem": "采菊东篱下，悠然见南山", "grade": "上上签", "source": "晋·陶渊明《饮酒》"},
    {"number": "第二十六签", "poem": "春色满园关不住，一枝红杏出墙来", "grade": "上签", "source": "宋·叶绍翁《游园不值》"},
    {"number": "第二十七签", "poem": "欲穷千里目，更上一层楼", "grade": "上签", "source": "唐·王之涣《登鹳雀楼》"},
    {"number": "第二十八签", "poem": "花开堪折直须折，莫待无花空折枝", "grade": "中签", "source": "唐·杜秋娘《金缕衣》"},
    {"number": "第二十九签", "poem": "知足者富，强行者有志", "grade": "中签", "source": "《道德经》"},
    {"number": "第三十签", "poem": "祸莫大于不知足，咎莫大于欲得", "grade": "下签", "source": "《道德经》"},
]


if __name__ == "__main__":
    app.run(debug=True, port=5001)
