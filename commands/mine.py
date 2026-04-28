import discord
from discord.ext import commands, tasks
from database import user_init, get_wallet_bank,  update_wallet
import random
import asyncio

class GameSession:
    def __init__(self, user, grid, mines, mine_count, bet):
        self.user = user
        self.grid = grid  # 2D list bool (True = mine)
        self.mines = mines  # set of (row, col) positions of mines
        self.mine_count = mine_count
        self.clicked = set()
        self.clicks = 0
        self.multiplier = 1.0
        self.lost = False
        self.bet = bet
        self.timeout_task = None

    def update_multiplier(self):
        self.multiplier = get_multiplier(self.clicks, self.mine_count)

    def total_safe_cells(self):
        return (4 * 5) - self.mine_count

def generate_grid(mine_count):
    rows, cols = 4, 5
    grid = [[False for _ in range(cols)] for _ in range(rows)]
    mines = set()
    while len(mines) < mine_count:
        x, y = random.randint(0, rows - 1), random.randint(0, cols - 1)
        mines.add((x, y))
    for (x, y) in mines:
        grid[x][y] = True
    return grid, mines

def get_multiplier(clicks, mine_count):
    base_multipliers = { 
        1:  [1.05, 1.10, 1.15, 1.22, 1.30, 1.40, 1.55, 1.70, 1.85, 2.0, 2.2, 2.5, 2.8, 3.2, 3.6, 4.0, 4.5, 5.0, 5.6],
        2:  [1.10, 1.20, 1.30, 1.45, 1.60, 1.80, 2.0, 2.3, 2.6, 2.9, 3.3, 3.7, 4.2, 4.8, 5.4, 6.0, 6.7, 7.5],
        3:  [1.15, 1.25, 1.35, 1.50, 1.70, 1.90, 2.2, 2.5, 2.9, 3.3, 3.8, 4.3, 5.0, 5.7, 6.5, 7.4, 8.4],
        4:  [1.20, 1.30, 1.45, 1.65, 1.85, 2.1, 2.4, 2.8, 3.2, 3.7, 4.3, 5.0, 5.7, 6.5, 7.4, 8.4],
        5:  [1.25, 1.35, 1.50, 1.70, 1.95, 2.2, 2.5, 2.9, 3.3, 3.8, 4.4, 5.1, 5.9, 6.8, 7.8]
    }
    closest = min(base_multipliers.keys(), key=lambda x: abs(x - mine_count))
    table = base_multipliers[closest]
    if clicks <= 0:
        return 1.0
    elif clicks > len(table):  
        return table[-1]
    else:
        return round(table[clicks - 1], 2)

class MinesStartView(discord.ui.View):
    def __init__(self, user, sessions, bet, ctx):
        super().__init__(timeout=180)
        self.user = user
        self.sessions = sessions
        self.bet = bet
        self.add_item(MinesCountSelect(user, sessions, bet,ctx))

class MinesCountSelect(discord.ui.Select):
    def __init__(self, user, sessions, bet, ctx):
        self.bet = bet
        self.user = user
        self.sessions = sessions
        self.ctx =  ctx
        options = [discord.SelectOption(label=f"{i} mine(s)", value=str(i)) for i in range(1, 6)]
        super().__init__(placeholder="Nombre de mines", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            embed = discord.Embed(description="Tu ne peux pas jouer dans la partie d'un autre !", color=0x000000)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        mine_count = int(self.values[0])
        grid, mines = generate_grid(mine_count)
        session = GameSession(user=self.user, grid=grid, mines=mines, mine_count=mine_count, bet=self.bet)
        self.sessions[self.user.id] = session

        view = GameBoardView(session, self.sessions, self.ctx)
        embed = discord.Embed(
            description=f"🎯 **Jeu de Mines lancé avec {mine_count} mine(s)**.\n💰 Mise : {self.bet}€\nClique sur une case pour tenter ta chance !",
            color=0x000000
        )
        message = await interaction.response.edit_message(embed=embed, view=view)

        # Lancer le timer de 40s d'inactivité
        session.timeout_task = asyncio.create_task(auto_cashout_after_timeout(session, view, message, self.ctx))

async def auto_cashout_after_timeout(session, view, message, ctx, timeout=40):
    await asyncio.sleep(timeout)
    if session.user.id in view.sessions and not session.lost:
        gain = int(session.bet * session.multiplier)
        view.sessions.pop(session.user.id, None)
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        embed = discord.Embed(
            description=f"⏰ Inactivité détectée : Retrait automatique de **{gain}€** avec un multiplicateur de **x{session.multiplier:.2f}**.",
            color=0x000000
        )
        update_wallet(message.guild.id, ctx.author.id, gain)
        await message.edit(embed=embed, view=None)

class GameBoardView(discord.ui.View):
    def __init__(self, session: GameSession, sessions, ctx):
        super().__init__(timeout=300)
        self.session = session
        self.sessions = sessions
        self.ctx = ctx
        rows, cols = 4, 5
        for i in range(rows):
            for j in range(cols):
                self.add_item(GridButton(i, j, session, sessions, self, self.ctx))
        self.add_item(CashOutButton(session, sessions, self))

class GridButton(discord.ui.Button):
    def __init__(self, row, col, session, sessions, view, ctx):
        super().__init__(style=discord.ButtonStyle.secondary, label="⬜", row=row)
        self.row_idx = row
        self.col_idx = col
        self.session = session
        self.sessions = sessions
        self.custom_view = view
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user.id:
            embed = discord.Embed(description="Tu ne joues pas cette partie !", color=0x000000)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        pos = (self.row_idx, self.col_idx)
        if pos in self.session.clicked:
            return await interaction.response.defer()

        if self.session.timeout_task:
            self.session.timeout_task.cancel()                                         
            self.session.timeout_task = asyncio.create_task(auto_cashout_after_timeout(self.session, self.view, interaction.message, self.ctx))

        if pos in self.session.mines:
            self.label = "💣"
            self.style = discord.ButtonStyle.danger
            self.disabled = True
            self.session.lost = True
            for child in self.view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            self.sessions.pop(self.session.user.id, None)
            embed = discord.Embed(description="💥 Tu as cliqué sur une **mine** ! Partie terminée.", color=0x000000)
            return await interaction.response.edit_message(embed=embed, view=self.view)

        self.session.clicked.add(pos)
        self.session.clicks += 1
        self.label = "✅"
        self.style = discord.ButtonStyle.success
        self.disabled = True
        self.session.update_multiplier()

        # Vérifier si toutes les cases sûres sont cliquées
        if len(self.session.clicked) >= self.session.total_safe_cells():
            gain = int(self.session.bet * self.session.multiplier)
            self.sessions.pop(self.session.user.id, None)
            for child in self.view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            embed = discord.Embed(description=f"🎉 Tu as cliqué sur **toutes les cases sûres** ! Tu gagnes **{gain}€** avec un multiplicateur de **x{self.session.multiplier:.2f}** !", color=0x000000)
            return await interaction.response.edit_message(embed=embed, view=self.view)

        embed = discord.Embed(description=f"🟢 **Multiplicateur actuel : x{self.session.multiplier:.2f}**", color=0x000000)
        await interaction.response.edit_message(embed=embed, view=self.view)

class CashOutButton(discord.ui.Button):
    def __init__(self, session, sessions, view):
        super().__init__(label="💸 Retirer", style=discord.ButtonStyle.primary, row=4)
        self.session = session
        self.sessions = sessions
        self.custom_view = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user.id:
            embed = discord.Embed(description="Tu ne peux pas retirer dans la partie d'un autre !", color=0x000000)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if self.session.timeout_task:
            self.session.timeout_task.cancel()

        self.disabled = True
        for child in self.view.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        gain = int(self.session.bet * self.session.multiplier)
        self.sessions.pop(self.session.user.id, None)
        update_wallet(interaction.guild.id,interaction.user.id, gain)
        embed = discord.Embed(
            description=f"✅ Tu as retiré **{gain}€** avec un multiplicateur de **x{self.session.multiplier:.2f}** !",
            color=0x000000
        )
        await interaction.response.edit_message(embed=embed, view=None)

class MinesCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}

    @commands.command(name="")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def mines(self, ctx, bet : str =None):
        user_init(ctx.guild.id, ctx.author.id)
        user = get_wallet_bank(ctx.guild.id, ctx.author.id)
        if user["wallet"]  <= 0 : 
            return await ctx.reply("❌ Vous n'avez pas d'argent sur vous.")
        if bet is None:
            return await ctx.reply("❌ Veuillez saisir une somme à miser.")
        if bet.lower() == "all":
            bet = user["wallet"]
        else:
            if not bet.isdigit():
                return await ctx.reply("❌ Montant invalide.")
            bet = int(bet)
        if bet > user["wallet"] : 
            return await ctx.reply("❌ Vous n'avez pas assez d'argent sur vous.")
        if ctx.author.id in self.sessions:
            embed = discord.Embed(description="Tu as déjà une partie en cours !", color=0x000000)
            return await ctx.reply(embed=embed)

        update_wallet(ctx.guild.id, ctx.author.id, -bet)
        view = MinesStartView(ctx.author, self.sessions, bet, ctx)
        embed = discord.Embed(description="🎮 Choisis le nombre de mines :", color=0x000000)
        await ctx.reply(embed=embed, view=view)


    @mines.error
    async def mines_error(self, ctx, error):
        from time import time
        if isinstance(error, commands.CommandOnCooldown):
            retry_after = round(error.retry_after, 1)
            future_time = int(time() + retry_after)
            embed = discord.Embed(
                description=(
                    f"⏳ Patiente encore, tu pourrass relancer cette commande <t:{future_time}:R>."
                ),
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
        

async def setup(bot):
    await bot.add_cog(MinesCommand(bot))
