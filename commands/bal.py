from discord.ext import commands
import discord
from database import user_init, get_wallet_bank

class Bal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def bal(self, ctx, member: commands.MemberConverter = None):
        if(member == None):
            user_init(ctx.guild.id,ctx.author.id)
            user = get_wallet_bank(ctx.guild.id,ctx.author.id)
        else :
            try :
                user_init(ctx.guild.id,member.id)
                user = get_wallet_bank(ctx.guild.id,member.id)
            except : 
                user_init(ctx.guild.id,ctx.author.id)
                user = get_wallet_bank(ctx.guild.id,ctx.author.id)
        wallet = user["wallet"]
        bank = user["bank"]
        embed = discord.Embed(
            title=f"💰 Solde de {ctx.author.display_name if member == None else member.display_name}",
            color=0x000000
        )
        embed.add_field(name="💼 Wallet", value=f"{wallet} coins", inline=True)
        embed.add_field(name="🏦 Bank", value=f"{bank} coins", inline=True)

        await ctx.reply(embed=embed)
        

async def setup(bot):
    await bot.add_cog(Bal(bot))
