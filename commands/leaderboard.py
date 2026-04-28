import discord
from discord.ext import commands

from database import get_all_users_with_balances  # ta fonction base de données

class LeaderboardPaginator(discord.ui.View):
    def __init__(self, bot, users, per_page=10):
        super().__init__(timeout=120)
        self.bot = bot
        self.users = sorted(users, key=lambda x: x[1] + x[2], reverse=True)
        self.per_page = per_page
        self.page = 0
        self.max_page = (len(self.users) - 1) // per_page

        # Désactive le bouton précédent si on est à la première page
        self.previous_button.disabled = True
        if self.max_page == 0:
            self.next_button.disabled = True

    def get_embed(self):
        embed = discord.Embed(
            title="🏆 Leaderboard",
            description=f"Top joueurs les plus riches 💰 (page {self.page + 1}/{self.max_page + 1})",
            color=0x000000
        )
        start = self.page * self.per_page
        end = start + self.per_page
        to_show = self.users[start:end]

        for i, (user_id, wallet, bank) in enumerate(to_show, start=start + 1):
            total = wallet + bank
            user = self.bot.get_user(int(user_id))
            username = user.name if user else f"Utilisateur inconnu ({user_id})"
            embed.add_field(
                name=f"{i}. {username}",
                value=f"💰 Total: {total} coins (💼 {wallet} | 🏦 {bank})",
                inline=False
            )
        return embed

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.next_button.disabled = False
            if self.page == 0:
                self.previous_button.disabled = True
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
            self.previous_button.disabled = False
            if self.page == self.max_page:
                self.next_button.disabled = True
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["lb"])
    async def leaderboard(self, ctx):
        rows = get_all_users_with_balances(ctx.guild.id)

        if not rows:
            embed = discord.Embed(
                title="",
                description="**Aucun joueur**",
                color=0x000000
            )
            await ctx.reply(embed=embed)
            return

        paginator = LeaderboardPaginator(self.bot, rows, per_page=10)
        await ctx.reply(embed=paginator.get_embed(), view=paginator)


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
