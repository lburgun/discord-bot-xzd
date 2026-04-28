# duel.py

import random
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button

class DuelGame:
    active_games = {}  # key: message_id, value: DuelView

class JoinDuelButton(Button):
    def __init__(self, bet, owner_id):
        super().__init__(label="Rejoindre le duel", style=discord.ButtonStyle.blurple)
        self.bet = bet
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        view: DuelView = self.view

        if view.player2 is not None:
            return await interaction.response.send_message("Ce duel a déjà un adversaire.", ephemeral=True)

        if interaction.user.id == self.owner_id:
            return await interaction.response.send_message("Tu ne peux pas rejoindre ton propre duel.", ephemeral=True)

        view.player2 = interaction.user
        DuelGame.active_games[interaction.message.id] = view

        # Affiche les deux joueurs et le countdown
        start_time = discord.utils.utcnow().timestamp() + 10
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="💥 Duel",
                description=(
                    f"**Mise :** {self.bet} 💰\n"
                    f"**Joueurs :** {interaction.guild.get_member(self.owner_id).mention} vs {view.player2.mention}\n"
                    f"⏳ Préparez-vous... Le duel commence <t:{int(start_time)}:R> !"
                ),
                color=0x000000
            ),
            view=None
        )

        await asyncio.sleep(10)
        await view.start_duel(interaction)


class RedButton(Button):
    def __init__(self):
        super().__init__(label="💀 Tirer", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        view: DuelView = self.view
        if interaction.user not in [view.owner, view.player2]:
            return await interaction.response.send_message("Tu ne participes pas à ce duel.", ephemeral=True)

        loser = interaction.user
        winner = view.player2 if interaction.user == view.owner else view.owner

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="💥 Duel terminé",
                description=f"{loser.mention} a tiré trop tôt et a perdu !\n🏆 {winner.mention} remporte {view.bet} 💰",
                color=0x000000
            ),
            view=None
        )
        DuelGame.active_games.pop(interaction.message.id, None)
        view.stop()


class GreenButton(Button):
    def __init__(self):
        super().__init__(label="🏆 Tirer", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view: DuelView = self.view
        if interaction.user not in [view.owner, view.player2]:
            return await interaction.response.send_message("Tu ne participes pas à ce duel.", ephemeral=True)

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="💥 Duel terminé",
                description=f"{interaction.user.mention} a tiré au bon moment !\n🏆 Il remporte {view.bet} 💰",
                color=0x000000
            ),
            view=None
        )
        DuelGame.active_games.pop(interaction.message.id, None)
        view.stop()


class DuelView(View):
    def __init__(self, owner: discord.User, bet: int):
        super().__init__(timeout=None)
        self.owner = owner
        self.bet = bet
        self.player2: discord.User = None

        self.join_button = JoinDuelButton(bet=bet, owner_id=owner.id)
        self.add_item(self.join_button)

    async def start_duel(self, interaction: discord.Interaction):
        self.clear_items()
        self.add_item(RedButton())
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="🎯 Duel en cours",
                description="**Appuyez sur le bouton dès qu'il devient vert !**",
                color=0x000000
            ),
            view=self
        )

        await asyncio.sleep(random.randint(6, 20))

        # Montrer le bouton vert
        self.clear_items()
        self.add_item(GreenButton())
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="✅ Tirez maintenant !",
                description="**Le bouton est vert !** Le premier à cliquer gagne.",
                color=0x000000
            ),
            view=self
        )


class Duel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="duel")
    async def duel(self, ctx: commands.Context, bet: int):
        if bet <= 0:
            return await ctx.send("La mise doit être supérieure à 0.")

        view = DuelView(owner=ctx.author, bet=bet)
        msg = await ctx.send(
            embed=discord.Embed(
                title="⚔️ Duel lancé",
                description=f"{ctx.author.mention} attend un adversaire...\n**Mise :** {bet} 💰",
                color=0x000000
            ),
            view=view
        )
        DuelGame.active_games[msg.id] = view


async def setup(bot):
    await bot.add_cog(Duel(bot))
