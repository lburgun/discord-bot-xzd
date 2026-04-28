import discord
from discord.ext import commands
import random
import asyncio
from database import user_init, update_wallet, get_wallet_bank
import datetime

class RouletteView(discord.ui.View):
    def __init__(self, ctx, bet):
        super().__init__(timeout=20)
        self.ctx = ctx
        self.bet = bet
        self.message = None
        self.done = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Ce n'est pas ton jeu !", ephemeral=True)
            return False
        return True

    async def finish(self, interaction, choice):
            self.done = True

            for child in self.children:
                child.disabled = True

            # Affiche le gif pendant 10 secondes
            embed = discord.Embed(title="🎡 La roue tourne...", color=0x000000)
            embed.set_image(url="https://cdn.discordapp.com/attachments/1295827543563309177/1389002545321476146/Animation_-_1749249549832.gif?ex=686308ed&is=6861b76d&hm=0d17d6b534b28af2d5f442fe802c9a326842710c0319894af2d4a3845b4a397a&")
            await interaction.response.edit_message(embed=embed,view=None)
            await asyncio.sleep(10)
        

            colors = ["🟥 Rouge", "⬛ Noir", "🟩 Vert"]
            weights = [0.475, 0.475, 0.05]
            result = random.choices(colors, weights=weights)[0]

            if (choice == "rouge" and result == "🟥 Rouge") or \
            (choice == "noir" and result == "⬛ Noir") or \
            (choice == "vert" and result == "🟩 Vert"):
                if result == "🟩 Vert":
                    gain = self.bet * 14
                    result_text = f"🎯 Tu as misé sur Vert... et c'était bien Vert !"
                else:
                    gain = self.bet
                    result_text = f"🎯 Tu as bien deviné : {result} !"
            else:
                gain = -self.bet
                result_text = f"❌ Perdu ! Le résultat était : {result}"

            update_wallet(self.ctx.guild.id, self.ctx.author.id, gain)

            embed = discord.Embed(title="🎡 Roulette - Résultat", color=0x000000)
            embed.add_field(name="Mise", value=f"{self.bet} coins sur **{choice.capitalize()}**", inline=False)
            embed.add_field(name="Résultat", value=result_text, inline=False)
            embed.add_field(name="Gain", value=f"{'+' if gain > 0 else ''}{gain} coins", inline=False)

            await self.message.edit(embed=embed, view=None)
            self.stop()

    

    @discord.ui.button(label="🟥 Rouge", style=discord.ButtonStyle.danger)
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "rouge")

    @discord.ui.button(label="⬛ Noir", style=discord.ButtonStyle.blurple)
    async def black(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "noir")

    @discord.ui.button(label="🟩 Vert", style=discord.ButtonStyle.success)
    async def green(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "vert")

    async def on_timeout(self):
        if not self.done:
            self.done = True
            gain = -self.bet // 2
            embed = discord.Embed(title="🎡 roulette - Temps écoulé", color=0x000000)
            embed.add_field(
                name="Résultat",
                value="⏰ Temps écoulé, partie abandonnée automatiquement. Vous perdez la moitié de votre mise.",
                inline=False
            )
            for child in self.children:
                child.disabled = True
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=None)
                except:
                    pass
            update_wallet(self.ctx.guild.id, self.ctx.author.id, gain)
            self.stop()

class Roulette(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["rlt"])
    @commands.cooldown(1, 12, commands.BucketType.user)
    async def roulette(self, ctx, amount: str = None):
        user_init(ctx.guild.id, ctx.author.id)
        user = get_wallet_bank(ctx.guild.id, ctx.author.id)
        if amount is None:
            return await ctx.reply("❌ Veuillez entrer une somme à miser.")
        if amount.lower() == "all":
            bet = user["wallet"]
        else:
            if not amount.isdigit():
                return await ctx.reply("❌ Montant invalide.")
            bet = int(amount)

        if bet <= 0 or bet > user["wallet"]:
            return await ctx.reply("❌ Vous n'avez pas assez d'argent.")

        view = RouletteView(ctx, bet)
        embed = discord.Embed(
            title="🎡 Roulette",
            description="Choisis une couleur :",
            color=0x000000
        )
        embed.add_field(name="🟥 Rouge", value="x2", inline=True)
        embed.add_field(name="⬛ Noir", value="x2", inline=True)
        embed.add_field(name="🟩 Vert", value="x14", inline=True)
        embed.set_footer(text=f"Pari : {bet} coins")

        msg = await ctx.reply(embed=embed, view=view)
        view.message = msg


    @roulette.error
    async def roulette_error(self, ctx, error):
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
    await bot.add_cog(Roulette(bot))
