import discord
from discord.ext import commands
from discord import ui
from database import is_economy_enabled, set_economy_enabled, reset_guild_economy

OWNER_ONLY_MESSAGE = "🚫 Seul le propriétaire du serveur peut utiliser cette commande."

class ToggleButtons(ui.View):
	def __init__(self, guild_id: int, *, timeout: float | None = 180):
		super().__init__(timeout=timeout)
		self.guild_id = guild_id

	@ui.button(label="Activer", style=discord.ButtonStyle.success)
	async def enable(self, interaction: discord.Interaction, button: ui.Button):
		if interaction.user.id != interaction.guild.owner_id:
			await interaction.response.send_message(OWNER_ONLY_MESSAGE, ephemeral=True)
			return
		set_economy_enabled(self.guild_id, True)
		await interaction.response.edit_message(content="✅ Économie activée pour ce serveur.", view=self)

	@ui.button(label="Désactiver", style=discord.ButtonStyle.danger)
	async def disable(self, interaction: discord.Interaction, button: ui.Button):
		if interaction.user.id != interaction.guild.owner_id:
			await interaction.response.send_message(OWNER_ONLY_MESSAGE, ephemeral=True)
			return
		set_economy_enabled(self.guild_id, False)
		await interaction.response.edit_message(content="⛔ Économie désactivée pour ce serveur.", view=self)

class ConfirmReset(ui.View):
	def __init__(self, guild_id: int, *, timeout: float | None = 60):
		super().__init__(timeout=timeout)
		self.guild_id = guild_id

	@ui.button(label="Confirmer le reset", style=discord.ButtonStyle.danger)
	async def confirm(self, interaction: discord.Interaction, button: ui.Button):
		if interaction.user.id != interaction.guild.owner_id:
			await interaction.response.send_message(OWNER_ONLY_MESSAGE, ephemeral=True)
			return
		reset_guild_economy(self.guild_id)
		await interaction.response.edit_message(content="🧹 Économie du serveur réinitialisée.", view=None)

	@ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
	async def cancel(self, interaction: discord.Interaction, button: ui.Button):
		await interaction.response.edit_message(content="❎ Reset annulé.", view=None)

class EcoMenu(ui.Select):
	def __init__(self, guild_id: int):
		self.guild_id = guild_id
		options = [
			discord.SelectOption(label="Activer/Désactiver l'économie", description="Bascule l'accès aux commandes économie"),
			discord.SelectOption(label="Reset économie serveur", description="Efface toutes les données économie de ce serveur"),
		]
		super().__init__(placeholder="Choisis une action…", min_values=1, max_values=1, options=options)

	async def callback(self, interaction: discord.Interaction):
		if interaction.user.id != interaction.guild.owner_id:
			await interaction.response.send_message(OWNER_ONLY_MESSAGE, ephemeral=True)
			return
		choice = self.values[0]
		if choice == "Activer/Désactiver l'économie":
			enabled = is_economy_enabled(self.guild_id)
			text = "Économie actuellement: ✅ activée" if enabled else "Économie actuellement: ⛔ désactivée"
			view = ToggleButtons(self.guild_id)
			await interaction.response.edit_message(content=text, view=view)
		elif choice == "Reset économie serveur":
			await interaction.response.edit_message(content="⚠️ Cette action supprimera toutes les données économie de ce serveur. Confirmer ?", view=ConfirmReset(self.guild_id))

class EcoView(ui.View):
	def __init__(self, guild_id: int):
		super().__init__(timeout=180)
		self.add_item(EcoMenu(guild_id))

class Eco(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

	@commands.command(name="eco")
	async def eco(self, ctx: commands.Context):
		if ctx.guild is None:
			await ctx.reply("Cette commande doit être utilisée dans un serveur.")
			return
		if ctx.author.id != ctx.guild.owner_id:
			await ctx.reply(OWNER_ONLY_MESSAGE)
			return
		enabled = is_economy_enabled(ctx.guild.id)
		text = "Économie actuellement: ✅ activée" if enabled else "Économie actuellement: ⛔ désactivée"
		await ctx.reply(content=text, view=EcoView(ctx.guild.id))

async def setup(bot: commands.Bot):
	await bot.add_cog(Eco(bot)) 