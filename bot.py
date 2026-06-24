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

POINTS = {"SS": 350, "S": 220, "A": 150, "B": 100, "C": 60, "変ヒル": 200, "豪華": 500, "貴重": 300, "普通&精巧": 200, "釣り": 50}
BOSS_MAPPING = {"SS": "地方伝説すべて", "S": "黄金王獣・純水精霊", "A": "無相草・ダック・霊主", "B": "その他フィールドボス", "C": "急凍樹・爆炎樹"}

class FishingModal(discord.ui.Modal, title='釣り数の修正'):
    count = discord.ui.TextInput(label='追加する釣り数', placeholder='半角数字で入力', required=True)

    def __init__(self, message, end_time, host_id, is_host_mode):
        super().__init__()
        self.message = message
        self.end_time = end_time
        self.host_id = host_id
        self.is_host_mode = is_host_mode

    async def on_submit(self, i: discord.Interaction):
        try:
            add_count = int(self.count.value)
        except ValueError:
            return await i.response.send_message("数字で入力してください。", ephemeral=True)

        # 既存データの抽出と更新
        embed = self.message.embeds[0]
        data = embed.fields[1].value.split('|')
        score = int(data[0])
        counts_str = data[4].split(',')
        counts = {k: int(counts_str[idx]) for idx, k in enumerate(POINTS.keys())}
        
        # 釣り数を更新してスコアを再計算
        old_fish = counts["釣り"]
        counts["釣り"] += add_count
        score += (add_count * POINTS["釣り"])
        
        # 結果画面を再生成
        new_embed = HuntView().get_embed(embed.title.split(': ')[1], score, counts, self.end_time, self.host_id, self.is_host_mode, True)
        await i.response.edit_message(embed=new_embed, view=ResultView(self.message, self.end_time, self.host_id, self.is_host_mode))

class HuntView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def get_embed(self, team_name, score, counts, end_time, host_id, is_host_mode, final=False):
        if final:
            lines = ["```diff", "+ 狩猟結果詳細", "--------------------------"]
            for k, v in POINTS.items():
                if counts.get(k, 0) > 0: lines.append(f"{k:2}: {counts[k]:2}回 × {v:3}pt = {counts[k]*v:4}pt")
            lines.append("--------------------------")
            lines.append(f"最終合計: {score} pt```")
            return discord.Embed(title=f"🏁 終了: {team_name}", description="\n".join(lines), color=discord.Color.gold())
        
        info_text = "```css\n[ 討伐対象リスト ]\n"
        for r, d in BOSS_MAPPING.items(): info_text += f"{r:2} : {d}\n"
        info_text += "\n[ ポイント表 ]\n"
        for k, v in POINTS.items(): info_text += f"{k:2}: {v}pt\n"
        info_text += "--------------------------\n"
        info_text += f"現在スコア: {score} pt\n```"
        embed = discord.Embed(title=f"🏆 狩猟大会中: {team_name}", description=info_text, color=discord.Color.blue())

        embed.add_field(
            name="終了時間", 
            value=f"終了予定: <t:{end_time}:F>\n(残り: <t:{end_time}:R>)", 
            inline=False
        )

        counts_str = ",".join([str(counts.get(k, 0)) for k in POINTS.keys()])
        embed.add_field(name="_data", value=f"{score}|{end_time}|{host_id}|{int(is_host_mode)}|{counts_str}", inline=False)
        return embed

    async def end_hunt_logic(self, message):
        embed = message.embeds[0]
        # フィールドが1つしかない場合などを考慮し、安全に取得
        data = embed.fields[1].value.split('|')
        
        score = int(data[0])
        end_time = int(data[1])
        host_id = int(data[2])
        is_host_mode = bool(int(data[3]))
        # データ末尾のリスト部分は data[4:] にすべて入っているはず
        counts_list = data[4].split(',')
        
        counts = {k: int(counts_list[idx]) for idx, k in enumerate(POINTS.keys())}

        await message.edit(
            embed=self.get_embed(embed.title.split(': ')[1], score, counts, end_time, host_id, is_host_mode, True), 
            view=ResultView(message, end_time, host_id, is_host_mode)
        )


    async def update(self, i, key):
        embed = i.message.embeds[0]
        data = embed.fields[1].value.split('|')
        
        score = int(data[0])
        end_time = int(data[1])
        host_id = int(data[2])
        is_host_mode = bool(int(data[3]))
        counts_list = data[4].split(',')
        
        counts = {k: int(counts_list[idx]) for idx, k in enumerate(POINTS.keys())}
        if is_host_mode and i.user.id != host_id:
            return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        if time.time() > end_time:
            await self.end_hunt_logic(i.message)
            return await i.response.send_message("大会は終了しました。", ephemeral=True)
            
        score += POINTS[key]
        counts[key] += 1
        await i.response.edit_message(embed=self.get_embed(embed.title.split(': ')[1], score, counts, end_time, host_id, is_host_mode), view=self)

    # ボタン定義 (h1~h11)
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
        await self.end_hunt_logic(i.message)

class ResultView(discord.ui.View):
    def __init__(self, message, end_time, host_id, is_host_mode):
        super().__init__(timeout=None)
        self.message = message
        self.end_time = end_time
        self.host_id = host_id
        self.is_host_mode = is_host_mode

    @discord.ui.button(label="釣り数を修正", style=discord.ButtonStyle.primary, custom_id="res_fix")
    async def fix_btn(self, i: discord.Interaction, b: discord.ui.Button):
        message = self.message or i.message
        await i.response.send_modal(FishingModal(message, self.end_time, self.host_id, self.is_host_mode))

class HuntBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(HuntView())
        self.add_view(ResultView(None, None, None, None))
        self.auto_end.start()
        await self.tree.sync()

    @tasks.loop(seconds=30)
    async def auto_end(self):
        for guild in self.guilds:
            for channel in guild.text_channels:
                async for msg in channel.history(limit=50):
                    if msg.author == self.user and msg.embeds and "🏆" in msg.embeds[0].title and msg.components:
                        data = msg.embeds[0].fields[1].value.split('|')
                        if time.time() > int(data[1]):
                            await HuntView().end_hunt_logic(msg)

bot = HuntBot()

@bot.tree.command(name="start-hunt", description="狩猟大会を開始")
async def start(interaction: discord.Interaction, team_name: str, minutes: int = 15, is_host_mode: bool = False):
    end_t = int(time.time()) + (minutes * 60)
    counts = {k: 0 for k in POINTS.keys()}
    view = HuntView()
    await interaction.response.send_message(embed=view.get_embed(team_name, 0, counts, end_t, interaction.user.id, is_host_mode), view=view)

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)