import random
from discord.ext import commands
import discord
from database import update_wallet, user_init

class Beg(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.cooldown(1, 900, commands.BucketType.user)  # Cooldown 30 sec par utilisateur
    async def beg(self, ctx):
        amount = random.randint(1, 50)
        user_init(ctx.guild.id, ctx.author.id)
        update_wallet(ctx.guild.id,ctx.author.id, amount)

        embed = discord.Embed(
            title="🙏 Mendicité réussie !",
            description=f"Tu as reçu **{amount} coins** en mendiant.",
            color=0x000000
        )
        embed.set_footer(text="Patiente 30 secondes avant de mendier à nouveau.")
        embed.timestamp = ctx.message.created_at

        await ctx.reply(embed=embed)

    @beg.error
    async def beg_error(self, ctx, error):
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
    await bot.add_cog(Beg(bot))
