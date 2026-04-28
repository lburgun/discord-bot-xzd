import discord
from discord.ext import commands
from database import user_init, update_bank, update_wallet, get_wallet_bank

class Bank(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def create_transaction_embed(self, title: str, description: str, color: int = 0x000000) -> discord.Embed:
        """Crée un embed pour une transaction."""
        return discord.Embed(
            title=title,
            description=description,
            color=color
        )

    def create_error_embed(self, description: str) -> discord.Embed:
        """Crée un embed d'erreur."""
        return discord.Embed(
            description=description,
            color=0x000000
        )

    @commands.command(aliases=["with", "retirer"])
    async def with_(self, ctx, amount: str):
        user_id = ctx.author.id
        user_init(ctx.guild.id, user_id)

        user = get_wallet_bank(ctx.guild.id, user_id)
        if amount.lower() == "all":
            amount = user["bank"]
        elif amount.isdigit():
            amount = int(amount)
        else:
            return await ctx.reply(embed=self.create_error_embed("Montant invalide."))

        if amount <= 0:
            return await ctx.reply(embed=self.create_error_embed("Tu dois retirer un montant supérieur à zéro."))
        if amount > user["bank"]:
            return await ctx.reply(embed=self.create_error_embed("Tu n'as pas autant dans ta banque."))

        update_bank(ctx.guild.id,user_id, -amount)
        update_wallet(ctx.guild.id,user_id, amount)

        embed = self.create_transaction_embed(
            "💸 Retrait effectué",
            f"Tu as retiré **{amount} coins** de ta banque vers ton portefeuille."
        )
        await ctx.reply(embed=embed)

    @commands.command(aliases=["dep"])
    async def deposit(self, ctx, amount: str):
        user_id = ctx.author.id
        user_init(ctx.guild.id, user_id)

        user = get_wallet_bank(ctx.guild.id, user_id)
        if amount.lower() == "all":
            amount = user["wallet"]
        elif amount.isdigit():
            amount = int(amount)
        else:
            return await ctx.reply(embed=self.create_error_embed("Montant invalide."))

        if amount <= 0:
            return await ctx.reply(embed=self.create_error_embed("Tu dois déposer un montant supérieur à zéro."))
        if amount > user["wallet"]:
            return await ctx.reply(embed=self.create_error_embed("Tu n'as pas autant dans ton portefeuille."))

        update_wallet(ctx.guild.id,user_id, -amount)
        update_bank(ctx.guild.id,user_id, amount)

        embed = self.create_transaction_embed(
            "🏦 Dépôt effectué",
            f"Tu as déposé **{amount} coins** dans ta banque."
        )
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Bank(bot))
