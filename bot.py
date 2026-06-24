import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from discord import app_commands
import time
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running!"

def run_web_server():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ポイント・データ定義
POINTS = {
    "SS": 350, "S": 220, "A": 150, "B": 100, "C": 60,
    "変ヒル": 200, "豪華": 350, "貴重": 200, "普通&精巧": 120, "釣り": 18
}

BOSS_MAPPING = {
    "SS": "地方伝説すべて", "S": "黄金王獣・純水精霊", "A": "無相草・ダック・霊主",
    "B": "その他フィールドボス", "C": "急凍樹・爆炎樹"
}

class HuntView(discord.ui.View):
    # 永続化（再起動時）は引数なしで呼ばれる
    def __init__(self, host_id=None, team_name=None, end_time=None, is_host_mode=False):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.team_name = team_name
        self.end_time = end_time
        self.is_host_mode = is_host_mode
        self.score = 0
        self.counts = {k: 0 for k in POINTS.keys()}

    def get_embed(self, final=False):
        if final:
            lines = ["```diff", "+ 狩猟結果詳細", "--------------------------"]
            for k, v in POINTS.items():
                if self.counts[k] > 0:
                    lines.append(f"{k:2}: {self.counts[k]:2}回 × {v:3}pt = {self.counts[k]*v:4}pt")
            lines.append("--------------------------")
            lines.append(f"最終合計: {self.score} pt```")
            return discord.Embed(title=f"🏁 終了: {self.team_name}", description="\n".join(lines), color=discord.Color.gold())
        
        # 以前の表示内容を完全に復元
        info_text = "```css\n[ 討伐対象リスト ]\n"
        for r, d in BOSS_MAPPING.items(): info_text += f"{r:2} : {d}\n"
        info_text += "\n[ ポイント表 ]\n"
        for k, v in POINTS.items(): info_text += f"{k:2}: {v}pt\n"
        info_text += "--------------------------\n"
        info_text += f"現在スコア: {self.score} pt\n```"
        
        embed = discord.Embed(title=f"🏆 狩猟大会中: {self.team_name}", description=info_text, color=discord.Color.blue())
        embed.add_field(name="残り時間", value=f"<t:{self.end_time}:R>", inline=False)
        return embed

    async def update(self, i, key):
        if self.is_host_mode and i.user.id != self.host_id:
            return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        self.score += POINTS[key]
        self.counts[key] += 1
        await i.response.edit_message(embed=self.get_embed(), view=self)

    # 永続化のためcustom_idは固定
    @discord.ui.button(label="SS", style=discord.ButtonStyle.danger, custom_id="h1")
    async def b1(self, i, b): await self.update(i, "SS")
    @discord.ui.button(label="S", style=discord.ButtonStyle.danger, custom_id="h2")
    async def b2(self, i, b): await self.update(i, "S")
    @discord.ui.button(label="A", style=discord.ButtonStyle.danger, custom_id="h3")
    async def b3(self, i, b): await self.update(i, "A")
    @discord.ui.button(label="B", style=discord.ButtonStyle.danger, custom_id="h4")
    async def b4(self, i, b): await self.update(i, "B")
    @discord.ui.button(label="C", style=discord.ButtonStyle.danger, custom_id="h5")
    async def b5(self, i, b): await self.update(i, "C")
    @discord.ui.button(label="変ヒル", style=discord.ButtonStyle.danger, custom_id="h6")
    async def b6(self, i, b): await self.update(i, "変ヒル")
    @discord.ui.button(label="釣り", style=discord.ButtonStyle.primary, custom_id="h7")
    async def b7(self, i, b): await self.update(i, "釣り")
    @discord.ui.button(label="豪華", style=discord.ButtonStyle.success, custom_id="h8")
    async def c1(self, i, b): await self.update(i, "豪華")
    @discord.ui.button(label="貴重", style=discord.ButtonStyle.success, custom_id="h9")
    async def c2(self, i, b): await self.update(i, "貴重")
    @discord.ui.button(label="普通&精巧", style=discord.ButtonStyle.success, custom_id="h10")
    async def c3(self, i, b): await self.update(i, "普通&精巧")
    @discord.ui.button(label="強制終了", style=discord.ButtonStyle.secondary, custom_id="h11")
    async def end_btn(self, i, b):
        self.clear_items()
        await i.response.edit_message(embed=self.get_embed(final=True), view=self)

class HuntBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(HuntView())
        await self.tree.sync()

bot = HuntBot()

@bot.tree.command(name="start-hunt", description="狩猟大会を開始")
async def start(interaction: discord.Interaction, team_name: str, minutes: int = 15, is_host_mode: bool = False):
    end_t = int(time.time()) + (minutes * 60)
    view = HuntView(interaction.user.id, team_name, end_t, is_host_mode)
    await interaction.response.send_message(embed=view.get_embed(), view=view)

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)