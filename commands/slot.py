import discord
from discord.ext import commands
import random
from database import get_wallet_bank, update_wallet, user_init # adapte si besoin
from asyncio import sleep


class Slot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="slot")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def slot_machine(self, ctx, mise: str = None):
        user_init(ctx.guild.id, ctx.author.id)
        user = get_wallet_bank(ctx.guild.id, ctx.author.id)
        if user["wallet"]  <= 0 : 
            return await ctx.reply("❌ Vous n'avez pas d'argent sur vous.")
        if mise is None:
            return await ctx.reply("❌ Veuillez saisir une somme à miser.")
        if mise.lower() == "all":
            mise = user["wallet"]
        else:
            if not mise.isdigit():
                return await ctx.reply("❌ Montant invalide.")
            mise = int(mise)
        if mise > user["wallet"] : 
            return await ctx.reply("❌ Vous n'avez pas assez d'argent sur vous.")

        # Liste d'emojis classés par rareté
        emojis = {
            "🍒": 2, "🍋": 5,  # Commun
            "🍇": 7, "🍉": 10,  # Moyen
            "⭐": 25, "💎": 50  # Rare
        }

        symbols = list(emojis.keys())
        tirage = [random.choice(symbols) for _ in range(3)]

        # Résultat
        if tirage[0] == tirage[1] == tirage[2]:
            multiplicateur = emojis[tirage[0]]
            gain = mise * multiplicateur
            result = f"🎉 **Jackpot ! Tu gagnes {gain} € (x{multiplicateur}) !**"
            update_wallet(ctx.guild.id, ctx.author.id,-mise + gain)
        else:
            gain = 0
            result = f"😢 **Dommage, tu as perdu {mise} €.**"
            update_wallet(ctx.guild.id, ctx.author.id,-mise)

        embed = discord.Embed(
            title="🎰 Machine à Sous",
            description=f"Les slots tournent...",
            color=discord.Color.from_str("#000000")
        )
        embed.set_image(url="https://media.discordapp.net/attachments/1255915156467351592/1384146284130209852/jago33-slot-machine.gif?ex=68515e2e&is=68500cae&hm=50f032583643a27e47d6d74f0da9b60906a5fe09ebb6f29f8f2d321ed583024f&=")
        embed.set_footer(text=f"Mise : {mise} €")
        message =  await ctx.reply(embed=embed)

        await sleep(5)

        # Embed noir
        embed = discord.Embed(
            title="🎰 Machine à Sous",
            description=f"`[ {tirage[0]} | {tirage[1]} | {tirage[2]} ]`\n\n{result}",
            color=discord.Color.from_str("#000000")
        )

        await message.edit(embed=embed)

        

    @slot_machine.error
    async def slot_machine_error(self, ctx, error):
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
    await bot.add_cog(Slot(bot))
