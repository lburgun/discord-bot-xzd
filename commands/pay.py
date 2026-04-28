import discord
from discord.ext import commands
from database import get_wallet_bank, update_bank, user_init

class Pay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def pay(self, ctx, member: commands.MemberConverter, amount: int):
        sender = ctx.author.id
        receiver = member.id

        if sender == receiver:
            embed = discord.Embed(
                description="❌ Tu ne peux pas te transférer des coins à toi-même.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return
        
        if amount <= 0:
            embed = discord.Embed(
                description="❌ Le montant doit être supérieur à zéro.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        user_init(ctx.guild.id,sender)
        user_init(ctx.guild.id,receiver)
        data = get_wallet_bank(ctx.guild.id,sender)
        if data.get("bank", 0) < amount:
            embed = discord.Embed(
                description="💸 Tu n'as pas assez de coins dans ta banque.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        # Effectuer le transfert
        update_bank(ctx.guild.id,sender,-amount)
        update_bank(ctx.guild.id,receiver,amount)
        
        embed = discord.Embed(
            title="💱 Transfert effectué",
            description=f"💸 Tu as transféré **{amount} coins** à **{member.display_name}**.",
            color=0x000000
        )
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Pay(bot))
