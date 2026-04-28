import random
from discord.ext import commands
import discord
from database import update_wallet, user_init

class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)  # 86400 secondes = 24h
    async def daily(self, ctx):
        user_init(ctx.guild.id,ctx.author.id)
        amount = random.randint(100, 300)
        update_wallet(ctx.guild.id,ctx.author.id, amount)

        embed = discord.Embed(
            title="🎁 Récompense quotidienne",
            description=f"Tu as reçu **{amount} coins** pour ta récompense quotidienne !",
            color=0x000000
        )

        await ctx.reply(embed=embed)

    @daily.error
    async def daily_error(self, ctx, error):
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
   await bot.add_cog(Daily(bot))
