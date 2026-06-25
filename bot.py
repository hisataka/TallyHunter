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


# --- 極限編成トライアル用計算ロジック ---
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
    
    if d['time'] > d['limit']: time_score = 0
    else: time_score = d['limit'] - (d['time']**2 / d['limit'])
    
    return (a_coeff + c_coeff + w_coeff) * max(0, time_score), a_coeff, c_coeff, w_coeff

# --- モーダル定義 ---
class ExtremeSecondModal(discord.ui.Modal, title="極限編成トライアル入力(2/2)"):
    def __init__(self, team_name, first_data, limit):
        super().__init__()
        self.team_name, self.first_data, self.limit = team_name, first_data, limit
        self.w5_count = discord.ui.TextInput(label="⑤☆5武器の本数", placeholder="0")
        self.w3_count = discord.ui.TextInput(label="⑥☆3武器の本数", placeholder="0")
        self.max_w_refine = discord.ui.TextInput(label="⑦最多凸☆5武器の精錬ランク", placeholder="1")
        self.sum_w_refine = discord.ui.TextInput(label="⑧その他☆5武器精錬合計", placeholder="0")
        self.time = discord.ui.TextInput(label="⑨討伐タイム(秒)", placeholder="60")
        for item in [self.w5_count, self.w3_count, self.max_w_refine, self.sum_w_refine, self.time]: self.add_item(item)

    async def on_submit(self, i: discord.Interaction):
        d = self.first_data
        d.update({'w5_count': int(self.w5_count.value), 'w3_count': int(self.w3_count.value),
                  'max_w_refine': int(self.max_w_refine.value), 'sum_w_refine': int(self.sum_w_refine.value),
                  'time': int(self.time.value), 'limit': self.limit})
        score, a_c, c_c, w_c = calculate_extreme_score(d)
        embed = discord.Embed(title=f"結果: {self.team_name}", color=discord.Color.green())
        embed.description = f"聖遺物係数: {a_c}\nキャラ係数: {c_c:.2f}\n武器係数: {w_c:.2f}\n討伐タイム: {d['time']}秒"
        embed.add_field(name="トータルスコア", value=f"**{score:.2f} pt**")
        await i.response.send_message(embed=embed)

class ExtremeFirstModal(discord.ui.Modal, title="極限編成トライアル入力(1/2)"):
    def __init__(self, team_name, limit):
        super().__init__()
        self.team_name, self.limit = team_name, limit
        self.a_score = discord.ui.TextInput(label="①PT内最高聖遺物スコア", placeholder="200.0")
        self.c_count = discord.ui.TextInput(label="②☆5キャラの編成人数", placeholder="4")
        self.max_c_const = discord.ui.TextInput(label="③最多凸☆5キャラの凸数", placeholder="0")
        self.sum_c_const = discord.ui.TextInput(label="④その他☆5キャラ凸合計", placeholder="0")
        for item in [self.a_score, self.c_count, self.max_c_const, self.sum_c_const]: self.add_item(item)

    async def on_submit(self, i: discord.Interaction):
        data = {'artifact_score': float(self.a_score.value), 'char_count': int(self.c_count.value),
                'max_c_const': int(self.max_c_const.value), 'sum_c_const': int(self.sum_c_const.value)}
        await i.response.send_modal(ExtremeSecondModal(self.team_name, data, self.limit))

@bot.tree.command(name="extreme-trial", description="極限編成トライアルのスコア算出")
async def extreme_trial(interaction: discord.Interaction, team_name: str, limit_seconds: int = 300):
    await interaction.response.send_modal(ExtremeFirstModal(team_name, limit_seconds))

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)