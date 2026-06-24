import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from discord import app_commands
import time
import asyncio

# .envファイルを読み込む
load_dotenv()

# =================【設定項目】=================
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# =============================================

# --- Flaskの設定 ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- ボットの設定 ---
class HuntBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        # コマンド同期処理
        try:
            # MY_GUILD = discord.Object(id=200494548932231169)
            # self.tree.copy_global_to(guild=MY_GUILD)
            # synced = await self.tree.sync(guild=MY_GUILD)
            # print(f'★ 同期成功: {len(synced)} 個のコマンドを同期しました')
            synced = await self.tree.sync()
            print(f'★ 同期成功: {len(synced)} 個のグローバルコマンドを同期しました')
        except Exception as e:
            print(f'★ 同期失敗: {e}')

bot = HuntBot()

# ================= ポイント・データ定義 =================
POINTS = {
    "SS": 350, "S": 220, "A": 150, "B": 100, "C": 60,
    "変ヒル": 200, "豪華": 350, "貴重": 200, "普通&精巧": 120, "釣り": 18
}

BOSS_MAPPING = {
    "SS": "地方伝説すべて",
    "S": "黄金王獣・純水精霊",
    "A": "無相草・ダック・霊主",
    "B": "その他フィールドボス",
    "C": "急凍樹・爆炎樹"
}

# ================= クラス定義 =================
class HuntView(discord.ui.View):
    def __init__(self, team_name, minutes):
        super().__init__(timeout=None)
        self.team_name = team_name
        self.score = 0
        self.counts = {k: 0 for k in POINTS.keys()}
        self.end_time = int(time.time()) + (minutes * 60)
        self.is_ended = False

    def get_info_text(self):
        lines = ["```css", "[ 討伐対象リスト ]"]
        for rank, desc in BOSS_MAPPING.items():
            lines.append(f"{rank:2} : {desc}")
        lines.append("\n[ ポイント表 ]")
        for k, v in POINTS.items():
            lines.append(f"{k:2}: {v}pt")
        lines.append("--------------------------")
        lines.append(f"現在スコア: {self.score} pt")
        lines.append("```")
        return "\n".join(lines)

    def get_summary_text(self):
        lines = ["```diff", "+ 狩猟結果詳細", "--------------------------"]
        for k, v in POINTS.items():
            if self.counts[k] > 0:
                lines.append(f"{k:2}: {self.counts[k]:2}回 × {v:3}pt = {self.counts[k]*v:4}pt")
        lines.append("--------------------------")
        lines.append(f"最終合計: {self.score} pt")
        lines.append("```")
        return "\n".join(lines)

    def get_embed(self, final=False):
        if final:
            embed = discord.Embed(title=f"🏁 終了: {self.team_name}", description=self.get_summary_text(), color=discord.Color.gold())
        else:
            embed = discord.Embed(title=f"🏆 狩猟大会中: {self.team_name}", description=self.get_info_text(), color=discord.Color.blue())
            embed.add_field(name="残り時間", value=f"<t:{self.end_time}:R>", inline=False)
        return embed

    async def update(self, i, key):
        if self.is_ended: return
        self.score += POINTS[key]
        self.counts[key] += 1
        await i.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="SS", style=discord.ButtonStyle.danger, row=0)
    async def b1(self, i, b): await self.update(i, "SS")
    @discord.ui.button(label="S", style=discord.ButtonStyle.danger, row=0)
    async def b2(self, i, b): await self.update(i, "S")
    @discord.ui.button(label="A", style=discord.ButtonStyle.danger, row=0)
    async def b3(self, i, b): await self.update(i, "A")
    @discord.ui.button(label="B", style=discord.ButtonStyle.danger, row=0)
    async def b4(self, i, b): await self.update(i, "B")
    @discord.ui.button(label="C", style=discord.ButtonStyle.danger, row=0)
    async def b5(self, i, b): await self.update(i, "C")

    @discord.ui.button(label="変ヒル", style=discord.ButtonStyle.danger, row=1)
    async def b6(self, i, b): await self.update(i, "変ヒル")
    @discord.ui.button(label="釣り", style=discord.ButtonStyle.primary, row=1)
    async def b7(self, i, b): await self.update(i, "釣り")
    @discord.ui.button(label="豪華", style=discord.ButtonStyle.success, row=1)
    async def c1(self, i, b): await self.update(i, "豪華")
    @discord.ui.button(label="貴重", style=discord.ButtonStyle.success, row=1)
    async def c2(self, i, b): await self.update(i, "貴重")
    @discord.ui.button(label="普通&精巧", style=discord.ButtonStyle.success, row=1)
    async def c3(self, i, b): await self.update(i, "普通&精巧")

    @discord.ui.button(label="強制終了", style=discord.ButtonStyle.secondary, row=2)
    async def end_btn(self, i, b):
        self.is_ended = True
        self.clear_items()
        await i.response.edit_message(embed=self.get_embed(final=True), view=self)

# ================= コマンド定義 =================
@bot.tree.command(name="start-hunt", description="狩猟大会を開始")
async def start(interaction: discord.Interaction, team_name: str, minutes: int = 15):
    view = HuntView(team_name, minutes)
    await interaction.response.send_message(embed=view.get_embed(), view=view)
    await asyncio.sleep(minutes * 60)
    if not view.is_ended:
        view.is_ended = True
        view.clear_items()
        await interaction.edit_original_response(embed=view.get_embed(final=True), view=view)

# ================= 実行 =================
if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)