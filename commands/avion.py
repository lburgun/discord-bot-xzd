import discord
import random
import asyncio
from discord.ext import commands
from database import get_wallet_bank, update_wallet


class CrashButton(discord.ui.View):
    def __init__(self, user: discord.User, bet: int, ctx ):
        super().__init__(timeout=None)
        self.user = user
        self.bet = bet
        self.crashed = False
        self.stopped = False
        self.multiplier = 0.8  # Commence à 0.8x (donc en perte)
        self.message = None
        self.task = None
        self.ctx = ctx 

    async def start(self, message: discord.Message):
        self.message = message
        self.task = asyncio.create_task(self.crash_loop())

    def get_embed(self):
        embed = discord.Embed(
            title="✈️ Jeu de l'Avion",
            description="",
            color=0x000000
        )

        if self.crashed:
            desc = f"💥 **Crash à {self.multiplier:.2f}x** ! Tu as perdu **{self.bet}€**."
            embed.set_image(url="https://cdn.discordapp.com/attachments/1295827543563309177/1389010463240622213/crash-illustration-avion_1284-27251.png?ex=6863104d&is=6861becd&hm=c9aa983497142caee2464cebde3edff64c3725a54c2d9eaec61c90b15fb21a31&")
        elif self.stopped:
            gain = int(self.bet * self.multiplier)
            penalty = 0

            if self.multiplier < 1.1:
                penalty = int(gain * 0.1)
                gain -= penalty

            desc = f"✅ Tu as retiré à **{self.multiplier:.2f}x** ! Tu gagnes **{gain}€**"
            if penalty > 0:
                desc += f" *(taxe de {penalty}€ pour retrait précoce)*"

        else:
            desc = (
                f"L'avion vole... **{self.multiplier:.2f}x**\n"
                f"Clique sur **Retirer** avant qu'il ne s'écrase !"
            )

        embed.description = desc
        return embed

    async def crash_loop(self):
        while not self.stopped:
            await asyncio.sleep(1)

            # Crash aléatoire : plus le temps passe, plus les chances augmentent
            crash_chance = min(0.05 + (self.multiplier - 0.8) * 0.05, 0.5)
            if random.random() < crash_chance:
                self.crashed = True
                break
            # Vitesse de montée :
            if self.multiplier < 1.0:
                step = random.uniform(0.01, 0.05)  # très lent avant 1.0x
            elif self.multiplier < 1.5:
                step = random.uniform(0.05, 0.08)  # lent
            elif self.multiplier < 2.0:
                step = random.uniform(0.08, 0.12)  # moyen
            else:
                step = random.uniform(0.12, 0.2)   # rapide

            self.multiplier = round(self.multiplier + step, 2)
            await self.message.edit(embed=self.get_embed(), view=self)

        await self.message.edit(embed=self.get_embed(), view=None)

    @discord.ui.button(label="✋ Retirer", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Tu ne joues pas à cette partie.", ephemeral=True)

        if not self.crashed and not self.stopped:
            self.stopped = True
            await interaction.response.defer()
            gain = int(self.bet * self.multiplier)
            penalty = 0

            if self.multiplier < 1.1:
                penalty = int(gain * 0.1)
                gain -= penalty
            update_wallet(self.ctx.guild.id, self.ctx.author.id, gain)
            await self.message.edit(embed=self.get_embed(), view=None)

class Crash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="crash")
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def crash_game(self, ctx: commands.Context, bet: str = None):
        """Lance un jeu de crash (avion) avec une mise."""
        user = get_wallet_bank(ctx.guild.id, ctx.author.id)
        if bet is None:
            return await ctx.reply("❌ Veuillez entrer une somme à miser.")
        if bet.lower() == "all":
            bet = user["wallet"]
        else:
            if not bet.isdigit():
                return await ctx.reply("❌ Montant invalide.")
            bet = int(bet)

        if bet > user["wallet"] : 
            return await ctx.reply("❌ Vous n'avez pas assez d'argent.")
        update_wallet(ctx.guild.id, ctx.author.id, -bet)
        embed = discord.Embed(title="Décollage...", color=0x000000)
        embed.set_image(url="https://media.discordapp.net/attachments/1002173915549937714/1371043464929607690/flying.gif?ex=6862f57a&is=6861a3fa&hm=4ca079dcef5f441ec52d4bb4ea10c9c85701ef165cff79837c5d440919da10cc&=&width=500&height=375")
        message = await ctx.reply(embed=embed)
        await asyncio.sleep(3)
        view = CrashButton(ctx.author, bet, ctx)
        await view.start(message)
        await message.edit(embed=view.get_embed(), view=view)

    
    @crash_game.error
    async def crash_game_error(self, ctx, error):
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
    await bot.add_cog(Crash(bot))
