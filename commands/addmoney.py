import discord
from discord.ext import commands
from database import update_bank, user_init

class Addmoney(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def addmoney(self, ctx : commands.Context, member: discord.Member, amount: int =  200):
        user_init(ctx.guild.id, member.id)
        update_bank(ctx.guild.id, member.id, amount)
        
        embed = discord.Embed(
            title="✅ Argent ajouté",
            description=f"💰 {amount} coins ont été ajoutés à **{member.display_name}**.",
            color=0x000000
        )
        await ctx.send(embed=embed)
        

    @addmoney.error
    async def addmoney_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(embed=discord.Embed(
                description="❌ Argument invalide. Usage : `+addmoney @membre montant`",
                color=discord.Color.red()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Une erreur est survenue : {error}",
                color=discord.Color.red()
            ))

async def setup(bot):
    await bot.add_cog(Addmoney(bot))
