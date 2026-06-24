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

# ================= ポイント・データ定義 =================
POINTS = {
    "SS": 350, "S": 220, "A": 150, "B": 100, "C": 60,
    "変ヒル": 200, "豪華": 350, "貴重": 200, "普通&精巧": 120, "釣り": 18
}

# ================= クラス定義 =================
class HuntView(discord.ui.View):
    # 永続化用コンストラクタ
    def __init__(self, host_id=None, team_name="大会", minutes=15, is_host_mode=False):
        super().__init__(timeout=None) 
        self.host_id = host_id
        self.team_name = team_name
        self.is_host_mode = is_host_mode
        self.score = 0
        self.counts = {k: 0 for k in POINTS.keys()}
        self.end_time = int(time.time()) + (minutes * 60)
        self.is_ended = False

    def get_embed(self, final=False):
        if final:
            embed = discord.Embed(title=f"🏁 終了: {self.team_name}", color=discord.Color.gold())
            desc = "\n".join([f"{k}: {v}回" for k, v in self.counts.items() if v > 0])
            embed.description = f"最終合計: {self.score}pt\n\n{desc}"
            return embed
        embed = discord.Embed(title=f"🏆 狩猟大会中: {self.team_name}", color=discord.Color.blue())
        embed.add_field(name="残り時間", value=f"<t:{self.end_time}:R>", inline=False)
        return embed

    async def update(self, i, key):
        if self.is_host_mode and i.user.id != self.host_id:
            return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        self.score += POINTS[key]
        self.counts[key] += 1
        await i.response.edit_message(embed=self.get_embed(), view=self)

    # 各ボタンに custom_id を設定して永続化に対応
    @discord.ui.button(label="SS", style=discord.ButtonStyle.danger, custom_id="hunt_ss")
    async def b1(self, i, b): await self.update(i, "SS")
    @discord.ui.button(label="S", style=discord.ButtonStyle.danger, custom_id="hunt_s")
    async def b2(self, i, b): await self.update(i, "S")
    @discord.ui.button(label="A", style=discord.ButtonStyle.danger, custom_id="hunt_a")
    async def b3(self, i, b): await self.update(i, "A")
    @discord.ui.button(label="B", style=discord.ButtonStyle.danger, custom_id="hunt_b")
    async def b4(self, i, b): await self.update(i, "B")
    @discord.ui.button(label="C", style=discord.ButtonStyle.danger, custom_id="hunt_c")
    async def b5(self, i, b): await self.update(i, "C")
    @discord.ui.button(label="変ヒル", style=discord.ButtonStyle.danger, custom_id="hunt_h")
    async def b6(self, i, b): await self.update(i, "変ヒル")
    @discord.ui.button(label="釣り", style=discord.ButtonStyle.primary, custom_id="hunt_f")
    async def b7(self, i, b): await self.update(i, "釣り")
    @discord.ui.button(label="豪華", style=discord.ButtonStyle.success, custom_id="hunt_g")
    async def c1(self, i, b): await self.update(i, "豪華")
    @discord.ui.button(label="貴重", style=discord.ButtonStyle.success, custom_id="hunt_ki")
    async def c2(self, i, b): await self.update(i, "貴重")
    @discord.ui.button(label="普通&精巧", style=discord.ButtonStyle.success, custom_id="hunt_p")
    async def c3(self, i, b): await self.update(i, "普通&精巧")
    @discord.ui.button(label="強制終了", style=discord.ButtonStyle.secondary, custom_id="hunt_end")
    async def end_btn(self, i, b):
        self.is_ended = True
        await i.response.edit_message(embed=self.get_embed(final=True), view=None)

class HuntBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        # 永続化用Viewはインスタンス生成時に引数を渡さない
        self.add_view(HuntView()) 
        synced = await self.tree.sync()
        print(f'★ 同期完了: {len(synced)} 個のコマンド')

bot = HuntBot()

@bot.tree.command(name="start-hunt", description="狩猟大会を開始")
async def start(interaction: discord.Interaction, team_name: str, minutes: int = 15, is_host_mode: bool = False):
    view = HuntView(interaction.user.id, team_name, minutes, is_host_mode)
    await interaction.response.send_message(embed=view.get_embed(), view=view)
    
    # 終了監視ループ
    while time.time() < view.end_time:
        if view.is_ended: return
        await asyncio.sleep(10)
    
    if not view.is_ended:
        view.is_ended = True
        # view=discord.ui.View() でボタンなしViewを渡す
        await interaction.followup.send(embed=view.get_embed(final=True), view=discord.ui.View())

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)