import discord
from discord.ext import commands

class LFGView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.players = {
            "Duelliste": [],
            "Initiateur": [],
            "Contrôleur": [],
            "Sentinelle": [],
            "Flex": []
        }

    def create_embed(self):
        embed = discord.Embed(title="🎮 Recherche de Team", description="Inscrivez-vous pour former une équipe !", color=discord.Color.red())
        for role, list_players in self.players.items():
            value = "\n".join(list_players) if list_players else "Aucun joueur"
            embed.add_field(name=role, value=value, inline=True)
        return embed

    @discord.ui.button(label="Duelliste", style=discord.ButtonStyle.secondary, custom_id="lfg_duelliste")
    async def duelliste(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_player(interaction, "Duelliste")

    @discord.ui.button(label="Initiateur", style=discord.ButtonStyle.secondary, custom_id="lfg_init")
    async def initiateur(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_player(interaction, "Initiateur")

    @discord.ui.button(label="Contrôleur", style=discord.ButtonStyle.secondary, custom_id="lfg_smoke")
    async def controleur(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_player(interaction, "Contrôleur")

    @discord.ui.button(label="Sentinelle", style=discord.ButtonStyle.secondary, custom_id="lfg_sentinel")
    async def sentinelle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_player(interaction, "Sentinelle")

    @discord.ui.button(label="Flex", style=discord.ButtonStyle.secondary, custom_id="lfg_flex")
    async def flex(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_player(interaction, "Flex")

    @discord.ui.button(label="Vider", style=discord.ButtonStyle.danger, custom_id="lfg_clear")
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ Vous n'avez pas la permission.", ephemeral=True)
        for role in self.players:
            self.players[role] = []
        await interaction.response.edit_message(embed=self.create_embed())

    async def toggle_player(self, interaction, role):
        user_mention = interaction.user.mention
        if user_mention in self.players[role]:
            self.players[role].remove(user_mention)
        else:
            self.players[role].append(user_mention)
        await interaction.response.edit_message(embed=self.create_embed())

class LFG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="lfg_create")
    async def lfg_create(self, ctx):
        """Crée un panneau de recherche de joueurs"""
        view = LFGView()
        await ctx.send(embed=view.create_embed(), view=view)

async def setup(bot):
    await bot.add_cog(LFG(bot))
