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

# ポイント表の更新
POINTS = {
    "SS": 350, "S": 220, "A": 150, "B": 100, "C": 60, 
    "変ヒル": 200, "豪華": 500, "貴重": 300, "普通&精巧": 200, 
    "釣り": 50, "原型": 1500
}
BOSS_MAPPING = {"SS": "地方伝説すべて", "S": "黄金王獣・純水精霊", "A": "無相草・ダック・霊主", "B": "その他フィールドボス", "C": "急凍樹・爆炎樹"}

class EditCountModal(discord.ui.Modal):
    def __init__(self, message, end_time, host_id, is_host_mode, target_key):
        super().__init__(title=f'{target_key}の修正')
        self.message = message
        self.end_time = end_time
        self.host_id = host_id
        self.is_host_mode = is_host_mode
        self.target_key = target_key
        self.count = discord.ui.TextInput(label=f'追加する{target_key}の数', placeholder='半角数字', required=True)
        self.add_item(self.count)

    async def on_submit(self, i: discord.Interaction):
        if self.is_host_mode and i.user.id != self.host_id:
            return await i.response.send_message("ホストのみ修正可能です。", ephemeral=True)
        try:
            add_count = int(self.count.value)
        except ValueError:
            return await i.response.send_message("数字で入力してください。", ephemeral=True)

        embed = self.message.embeds[0]
        data = embed.fields[1].value.split('|')
        score = int(data[0])
        counts_list = data[4].split(',')
        counts = {k: int(counts_list[idx]) for idx, k in enumerate(POINTS.keys())}
        
        counts[self.target_key] += add_count
        score += (add_count * POINTS[self.target_key])
        
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
        embed.add_field(name="終了時間", value=f"終了予定: <t:{end_time}:F>\n(残り: <t:{end_time}:R>)", inline=False)
        counts_str = ",".join([str(counts.get(k, 0)) for k in POINTS.keys()])
        embed.add_field(name="_data", value=f"{score}|{end_time}|{host_id}|{int(is_host_mode)}|{counts_str}", inline=False)
        return embed

    async def end_hunt_logic(self, message):
        embed = message.embeds[0]
        data = embed.fields[1].value.split('|')
        score, end_time, host_id, is_host_mode = int(data[0]), int(data[1]), int(data[2]), bool(int(data[3]))
        counts_list = data[4].split(',')
        counts = {k: int(counts_list[idx]) for idx, k in enumerate(POINTS.keys())}
        await message.edit(embed=self.get_embed(embed.title.split(': ')[1], score, counts, end_time, host_id, is_host_mode, True), view=ResultView(message, end_time, host_id, is_host_mode))

    async def update(self, i, key):
        embed = i.message.embeds[0]
        data = embed.fields[1].value.split('|')
        score, end_time, host_id, is_host_mode = int(data[0]), int(data[1]), int(data[2]), bool(int(data[3]))
        counts_list = data[4].split(',')
        counts = {k: int(counts_list[idx]) for idx, k in enumerate(POINTS.keys())}
        if is_host_mode and i.user.id != host_id: return await i.response.send_message("ホストのみ操作可能です。", ephemeral=True)
        if time.time() > end_time:
            await self.end_hunt_logic(i.message)
            return await i.response.send_message("大会は終了しました。", ephemeral=True)
        score += POINTS[key]; counts[key] += 1
        await i.response.edit_message(embed=self.get_embed(embed.title.split(': ')[1], score, counts, end_time, host_id, is_host_mode), view=self)

    # ボタン定義
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
    @discord.ui.button(label="原型", style=discord.ButtonStyle.success, custom_id="h12")
    async def c4(self, i, b): await self.update(i, "原型")
    @discord.ui.button(label="強制終了", style=discord.ButtonStyle.secondary, custom_id="h11")
    async def end_btn(self, i, b): await self.end_hunt_logic(i.message)

class ResultView(discord.ui.View):
    def __init__(self, message, end_time, host_id, is_host_mode):
        super().__init__(timeout=None)
        self.message = message
        self.end_time = end_time
        self.host_id = host_id
        self.is_host_mode = is_host_mode

    @discord.ui.button(label="釣り数修正", style=discord.ButtonStyle.primary, custom_id="res_fish")
    async def fix_fish(self, i: discord.Interaction, b: discord.ui.Button):
        if self.is_host_mode and i.user.id != self.host_id: return await i.response.send_message("ホストのみ修正可能です。", ephemeral=True)
        await i.response.send_modal(EditCountModal(self.message or i.message, self.end_time, self.host_id, self.is_host_mode, "釣り"))

    @discord.ui.button(label="原型数修正", style=discord.ButtonStyle.primary, custom_id="res_proto")
    async def fix_proto(self, i: discord.Interaction, b: discord.ui.Button):
        if self.is_host_mode and i.user.id != self.host_id: return await i.response.send_message("ホストのみ修正可能です。", ephemeral=True)
        await i.response.send_modal(EditCountModal(self.message or i.message, self.end_time, self.host_id, self.is_host_mode, "原型"))

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
                        if time.time() > int(data[1]): await HuntView().end_hunt_logic(msg)

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