import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import time

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running!"

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

POINTS = {
    "SS": 350, "S": 220, "A": 150, "B": 100, "C": 60, 
    "変ヒル": 200, "豪華": 500, "貴重": 300, "普通&精巧": 200, 
    "釣り": 50, "原型": 2000
}
BOSS_MAPPING = {"SS": "地方伝説すべて", "S": "黄金王獣・純水精霊", "A": "無相草・ダック・霊主", "B": "その他フィールドボス", "C": "急凍樹・爆炎樹"}

# 権限チェック用ヘルパー
def is_authorized(i, host_id, is_host_mode):
    if is_host_mode and i.user.id != host_id:
        return False
    return True

class EditModal(discord.ui.Modal):
    def __init__(self, message, end_time, host_id, is_host_mode, counts, targets, title):
        super().__init__(title=title)
        self.message, self.end_time = message, end_time
        self.host_id, self.is_host_mode = host_id, is_host_mode
        self.inputs = {}
        for k in targets:
            ti = discord.ui.TextInput(label=k, default=str(counts[k]), placeholder='0', required=True)
            self.add_item(ti)
            self.inputs[k] = ti

    async def on_submit(self, i: discord.Interaction):
        if not is_authorized(i, self.host_id, self.is_host_mode):
            return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        counts = ResultView.get_counts_static(self.message)
        try:
            for k, ti in self.inputs.items(): counts[k] = int(ti.value)
        except ValueError:
            return await i.response.send_message("数字で入力してください。", ephemeral=True)
        new_score = sum(counts[k] * POINTS[k] for k in POINTS.keys())
        new_embed = HuntView().get_embed(self.message.embeds[0].title.split(': ')[-1], new_score, counts, self.end_time, self.host_id, self.is_host_mode, True)
        await i.response.edit_message(embed=new_embed, view=ResultView(self.message, self.end_time, self.host_id, self.is_host_mode))

class HuntView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    def get_embed(self, team_name, score, counts, end_time, host_id, is_host_mode, final=False):
        counts_str = ",".join([str(counts.get(k, 0)) for k in POINTS.keys()])
        data_value = f"{score}|{end_time}|{host_id}|{int(is_host_mode)}|{counts_str}"
        if final:
            lines = ["```diff", "+ 狩猟結果詳細", "--------------------------"]
            for k, v in POINTS.items():
                if counts.get(k, 0) > 0: lines.append(f"{k:2}: {counts[k]:2}回 × {v:3}pt = {counts[k]*v:4}pt")
            lines.append("--------------------------"); lines.append(f"最終合計: {score} pt```")
            embed = discord.Embed(title=f"🏁 終了: {team_name}", description="\n".join(lines), color=discord.Color.gold())
            embed.add_field(name="_data", value=data_value, inline=False)
            return embed
        
        info_text = "```css\n[ 討伐対象リスト ]\n"
        for r, d in BOSS_MAPPING.items(): info_text += f"{r:2} : {d}\n"
        info_text += "\n[ ポイント表 ]\n"
        for k, v in POINTS.items(): info_text += f"{k:2}: {v}pt\n"
        info_text += "--------------------------\n"
        info_text += f"現在スコア: {score} pt\n```"
        embed = discord.Embed(title=f"🏆 狩猟大会中: {team_name}", description=info_text, color=discord.Color.blue())
        embed.add_field(name="終了時間", value=f"終了予定: <t:{end_time}:F>\n(残り: <t:{end_time}:R>)", inline=False)
        embed.add_field(name="_data", value=data_value, inline=False)
        return embed

    async def _handle_update(self, i, key):
        data = [f.value for f in i.message.embeds[0].fields if f.name == "_data"][0].split('|')
        host_id, is_host_mode = int(data[2]), bool(int(data[3]))
        if not is_authorized(i, host_id, is_host_mode):
            return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        
        counts = ResultView.get_counts_static(i.message)
        if time.time() > int(data[1]):
            await self.end_hunt_logic(i.message)
            return await i.response.send_message("大会は終了しました。", ephemeral=True)
        counts[key] += 1
        new_score = sum(counts[k] * POINTS[k] for k in POINTS.keys())
        await i.response.edit_message(embed=self.get_embed(i.message.embeds[0].title.split(': ')[-1], new_score, counts, int(data[1]), host_id, is_host_mode), view=self)

    async def end_hunt_logic(self, message):
        counts = ResultView.get_counts_static(message)
        data = [f.value for f in message.embeds[0].fields if f.name == "_data"][0].split('|')
        await message.edit(embed=self.get_embed(message.embeds[0].title.split(': ')[-1], int(data[0]), counts, int(data[1]), int(data[2]), bool(int(data[3])), True), view=ResultView(message, int(data[1]), int(data[2]), bool(int(data[3]))))

    @discord.ui.button(label="SS", style=discord.ButtonStyle.danger, custom_id="h1")
    async def b1(self, i, b): await self._handle_update(i, "SS")
    @discord.ui.button(label="S", style=discord.ButtonStyle.danger, custom_id="h2")
    async def b2(self, i, b): await self._handle_update(i, "S")
    @discord.ui.button(label="A", style=discord.ButtonStyle.danger, custom_id="h3")
    async def b3(self, i, b): await self._handle_update(i, "A")
    @discord.ui.button(label="B", style=discord.ButtonStyle.danger, custom_id="h4")
    async def b4(self, i, b): await self._handle_update(i, "B")
    @discord.ui.button(label="C", style=discord.ButtonStyle.danger, custom_id="h5")
    async def b5(self, i, b): await self._handle_update(i, "C")
    @discord.ui.button(label="変ヒル", style=discord.ButtonStyle.primary, custom_id="h6")
    async def b6(self, i, b): await self._handle_update(i, "変ヒル")
    @discord.ui.button(label="釣り", style=discord.ButtonStyle.success, custom_id="h7")
    async def b7(self, i, b): await self._handle_update(i, "釣り")
    @discord.ui.button(label="豪華", style=discord.ButtonStyle.success, custom_id="h8")
    async def c1(self, i, b): await self._handle_update(i, "豪華")
    @discord.ui.button(label="貴重", style=discord.ButtonStyle.success, custom_id="h9")
    async def c2(self, i, b): await self._handle_update(i, "貴重")
    @discord.ui.button(label="普通&精巧", style=discord.ButtonStyle.success, custom_id="h10")
    async def c3(self, i, b): await self._handle_update(i, "普通&精巧")
    @discord.ui.button(label="原型", style=discord.ButtonStyle.success, custom_id="h12")
    async def c4(self, i, b): await self._handle_update(i, "原型")
    @discord.ui.button(label="強制終了", style=discord.ButtonStyle.secondary, custom_id="h11")
    async def end_btn(self, i, b):
        data = [f.value for f in i.message.embeds[0].fields if f.name == "_data"][0].split('|')
        if not is_authorized(i, int(data[2]), bool(int(data[3]))):
            return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        await self.end_hunt_logic(i.message)

class ResultView(discord.ui.View):
    def __init__(self, message=None, end_time=None, host_id=None, is_host_mode=None):
        super().__init__(timeout=None)
        self.message, self.end_time = message, end_time
        self.host_id, self.is_host_mode = host_id, is_host_mode

    @staticmethod
    def get_counts_static(message):
        data = [f.value for f in message.embeds[0].fields if f.name == "_data"][0].split('|')
        return {k: int(data[4].split(',')[idx]) for idx, k in enumerate(POINTS.keys())}

    @discord.ui.button(label="討伐修正", style=discord.ButtonStyle.danger, custom_id="res_fix_hunt")
    async def fix_hunt(self, i, b):
        if not is_authorized(i, self.host_id, self.is_host_mode): return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        await i.response.send_modal(EditModal(i.message, self.end_time, self.host_id, self.is_host_mode, self.get_counts_static(i.message), ["SS", "S", "A", "B", "C"], "討伐修正"))
    @discord.ui.button(label="変ヒル修正", style=discord.ButtonStyle.primary, custom_id="res_fix_hilly")
    async def fix_hilly(self, i, b):
        if not is_authorized(i, self.host_id, self.is_host_mode): return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        await i.response.send_modal(EditModal(i.message, self.end_time, self.host_id, self.is_host_mode, self.get_counts_static(i.message), ["変ヒル"], "変ヒル修正"))
    @discord.ui.button(label="採集修正", style=discord.ButtonStyle.success, custom_id="res_fix_collect")
    async def fix_collect(self, i, b):
        if not is_authorized(i, self.host_id, self.is_host_mode): return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        await i.response.send_modal(EditModal(i.message, self.end_time, self.host_id, self.is_host_mode, self.get_counts_static(i.message), ["釣り", "豪華", "貴重", "普通&精巧", "原型"], "採集修正"))

class HuntBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(HuntView())
        self.add_view(ResultView()) # デフォルト引数で初期化可能に
        self.add_view(ExtremeTrialView())
        self.auto_end.start()
        await self.tree.sync()

    @tasks.loop(seconds=30)
    async def auto_end(self):
        for guild in self.guilds:
            for channel in guild.text_channels:
                async for msg in channel.history(limit=50):
                    if msg.author == self.user and msg.embeds and "_data" in [f.name for f in msg.embeds[0].fields]:
                        data = [f.value for f in msg.embeds[0].fields if f.name == "_data"][0].split('|')
                        if time.time() > int(data[1]) and "🏆" in msg.embeds[0].title: await HuntView().end_hunt_logic(msg)

bot = HuntBot()

@bot.tree.command(name="start-hunt", description="狩猟大会を開始")
async def start(interaction: discord.Interaction, team_name: str, minutes: int = 15, is_host_mode: bool = False):
    end_t = int(time.time()) + (minutes * 60)
    counts = {k: 0 for k in POINTS.keys()}
    view = HuntView()
    await interaction.response.send_message(embed=view.get_embed(team_name, 0, counts, end_t, interaction.user.id, is_host_mode), view=view)

def calculate_extreme_score(d):
    def get_artifact_coeff(s):
        if s >= 200: return 0.25
        if s >= 180: return 0.5
        if s >= 170: return 0.75
        if s >= 160: return 1.0
        if s >= 140: return 1.75
        if s >= 120: return 2.5
        if s >= 100: return 3.5
        return 6.0

    base_char = {4: 0.25, 3: 0.5, 2: 1.0, 1: 1.75, 0: 3.0}
    c_coeff = base_char.get(d['char_count'], 0.25)
    c_penalty = (d['max_c_const'] * 0.15) + (d['sum_c_const'] / 10)
    c_coeff = max(0.05, c_coeff - c_penalty)

    w_coeff = 2.25 - (d['w5_count'] * 0.5) + (d['w3_count'] * 0.5)
    w_penalty = (d['max_w_refine'] * 0.25) + (d['sum_w_refine'] / 15)
    w_coeff = max(0.05, w_coeff - w_penalty)

    a_coeff = get_artifact_coeff(d['artifact_score'])

    limit = d['time_limit']
    time_score = limit - (d['time'] ** 2 / limit) if d['time'] <= limit else 0

    score = (a_coeff + c_coeff + w_coeff) * max(0, time_score)

    return score, a_coeff, c_coeff, w_coeff

def build_extreme_embed(team_name, data_str, result=None):
    d = data_str.split(',')

    labels = [
        ("①聖遺物スコア", d[0]),
        ("②☆5キャラ人数", d[1]),
        ("③最大凸数", d[2]),
        ("④その他凸合計", d[3]),
        ("⑤☆5武器数", d[4]),
        ("⑥☆3武器数", d[5]),
        ("⑦最多凸武器精錬", d[6]),
        ("⑧その他武器精錬合計", d[7]),
        ("⑨討伐タイム(秒)", d[8]),
        ("制限時間(秒)", d[9]),
    ]

    desc = "```yaml\n"
    for k, v in labels:
        desc += f"{k}: {v}\n"
    desc += "```"

    embed = discord.Embed(
        title=f"極限編成トライアル: {team_name}",
        description=desc,
        color=discord.Color.purple()
    )

    if result:
        score, a, c, w = result
        embed.add_field(
            name="計算結果",
            value=(
                "```diff\n"
                f"+ 総合スコア : {score:.2f}\n"
                f"聖遺物係数   : {a:.2f}\n"
                f"キャラ係数   : {c:.2f}\n"
                f"武器係数     : {w:.2f}\n"
                "```"
            ),
            inline=False
        )

    embed.add_field(name="_data", value=data_str, inline=False)
    return embed

class TrialEditModal(discord.ui.Modal):
    def __init__(self, message, part):
        title = "極限トライアル入力1" if part == 1 else "極限トライアル入力2"
        super().__init__(title=title)

        self.message = message
        self.part = part

        data = [f.value for f in message.embeds[0].fields if f.name == "_data"][0].split(',')
        self.d = data
        self.inputs = []

        labels = [
            ["①聖遺物スコア", "②☆5キャラ人数", "③最大凸数", "④その他凸合計"],
            ["⑤☆5武器数", "⑥☆3武器数", "⑦最多凸武器精錬", "⑧その他武器精錬合計", "⑨討伐タイム(秒)"]
        ]

        for label in labels[part - 1]:
            idx = labels[0].index(label) if part == 1 else labels[1].index(label) + 4
            ti = discord.ui.TextInput(
                label=label,
                default=str(self.d[idx]),
                style=discord.TextStyle.short
            )
            self.add_item(ti)
            self.inputs.append(ti)

    async def on_submit(self, i):
        new_d = self.d[:]

        for idx, ti in enumerate(self.inputs):
            target_idx = idx if self.part == 1 else idx + 4
            new_d[target_idx] = ti.value

        data_str = ",".join(new_d)

        team_name = i.message.embeds[0].title.replace(
            "極限編成トライアル: ",
            ""
        )

        embed = build_extreme_embed(team_name, data_str)
        await i.response.edit_message(embed=embed)

class ExtremeTrialView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="入力1", style=discord.ButtonStyle.primary, custom_id="tr_1")
    async def b1(self, i, b):
        await i.response.send_modal(TrialEditModal(i.message, 1))

    @discord.ui.button(label="入力2", style=discord.ButtonStyle.primary, custom_id="tr_2")
    async def b2(self, i, b):
        await i.response.send_modal(TrialEditModal(i.message, 2))

    @discord.ui.button(label="計算実行", style=discord.ButtonStyle.success, custom_id="tr_calc")
    async def b3(self, i, b):
        data_str = [f.value for f in i.message.embeds[0].fields if f.name == "_data"][0]
        d_list = data_str.split(',')

        d = {
            'artifact_score': float(d_list[0]),
            'char_count': int(d_list[1]),
            'max_c_const': int(d_list[2]),
            'sum_c_const': int(d_list[3]),
            'w5_count': int(d_list[4]),
            'w3_count': int(d_list[5]),
            'max_w_refine': int(d_list[6]),
            'sum_w_refine': int(d_list[7]),
            'time': int(d_list[8]),
            'time_limit': int(d_list[9]),
        }

        score, a, c, w = calculate_extreme_score(d)

        team_name = i.message.embeds[0].title.replace(
            "極限編成トライアル: ",
            ""
        )

        embed = build_extreme_embed(
            team_name,
            data_str,
            (score, a, c, w)
        )

        await i.response.edit_message(embed=embed)

@bot.tree.command(name="extreme-trial", description="極限編成トライアルを開始")
async def extreme_trial(
    interaction: discord.Interaction,
    team_name: str,
    time_limit: int = 300
):
    view = ExtremeTrialView()

    initial_data = f"150.0,0,0,0,0,0,0,0,60,{time_limit}"

    embed = build_extreme_embed(team_name, initial_data)

    await interaction.response.send_message(
        embed=embed,
        view=view
    )

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)