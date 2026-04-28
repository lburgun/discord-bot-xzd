import discord
from discord.ext import commands
import random
import string
import asyncio

class NukeView(discord.ui.View):
    def __init__(self, cog: 'NukeCog'):
        super().__init__()
        self.cog = cog
        self.value = None

    @discord.ui.button(label="\ud83d\udca3 Lancer", style=discord.ButtonStyle.danger)
    async def launch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        
        if interaction.user.id != interaction.guild.owner_id:
            embed = discord.Embed(
                title="\u274c Erreur",
                description="Seul le propri\u00e9taire du serveur peut utiliser cette commande.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        formatted_code = '-'.join([code[i:i+4] for i in range(0, 16, 4)])
        self.cog.verification_codes[interaction.guild.id] = code

        try:
            embed_dm = discord.Embed(
                title="\ud83d\udd10 Code de v\u00e9rification pour le nuke",
                description=f"Voici votre code de v\u00e9rification pour le nuke du serveur **{interaction.guild.name}** :\n\n`{formatted_code}`\n\nCe code est valide pendant 5 minutes.",
                color=0xFF0000
            )
            await interaction.user.send(embed=embed_dm)

            embed_response = discord.Embed(
                title="\ud83d\udd10 V\u00e9rification requise",
                description="Un code de v\u00e9rification vous a \u00e9t\u00e9 envoy\u00e9 en message priv\u00e9. Veuillez entrer ce code pour confirmer le nuke.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed_response, ephemeral=True)

            def check(m):
                return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and m.content.replace("-", "").upper() == code

            try:
                await interaction.client.wait_for('message', timeout=300.0, check=check)
                await self.cog.execute_nuke(interaction)
                del self.cog.verification_codes[interaction.guild.id]
            except asyncio.TimeoutError:
                embed_timeout = discord.Embed(
                    title="\u23f0 D\u00e9lai expir\u00e9",
                    description="Le code de v\u00e9rification a expir\u00e9. Veuillez recommencer la proc\u00e9dure.",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed_timeout, ephemeral=True)
                del self.cog.verification_codes[interaction.guild.id]

        except discord.Forbidden:
            embed_error = discord.Embed(
                title="\u274c Erreur",
                description="Impossible de vous envoyer un message priv\u00e9. Veuillez activer les messages priv\u00e9s pour ce serveur.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed_error, ephemeral=True)

    @discord.ui.button(label="\u274c Abandonner", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="\ud83d\udeab Nuke annul\u00e9",
            description="L'op\u00e9ration de nuke a \u00e9t\u00e9 annul\u00e9e.",
            color=0x000000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()

class NukeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verification_codes = {}

    @commands.command(name="nuke")
    @commands.guild_only()
    async def nuke(self, ctx):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return

        if ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                title="\u274c Erreur",
                description="Seul le propri\u00e9taire du serveur peut utiliser cette commande.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="\ud83d\udca3 Nuke du serveur",
            description=(
                "\u26a0\ufe0f **ATTENTION** \u26a0\ufe0f\n\n"
                "Vous \u00eates sur le point de **SUPPRIMER D\u00c9FINITIVEMENT** :\n"
                "- Tous les salons\n"
                "- Tous les r\u00f4les\n"
                "- Toutes les cat\u00e9gories\n\n"
                "Cette action est **IRR\u00c9VERSIBLE**. \u00cates-vous s\u00fbr de vouloir continuer ?"
            ),
            color=0xFF0000
        )
        embed.set_image(url="https://media.giphy.com/media/oe33xf3B50fsc/giphy.gif")

        view = NukeView(self)
        await ctx.send(embed=embed, view=view)

    async def execute_nuke(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        embed_start = discord.Embed(
            title="\ud83d\udca3 Nuke en cours",
            description="D\u00e9but de la suppression de tous les \u00e9l\u00e9ments du serveur...",
            color=0xFF0000
        )
        await interaction.followup.send(embed=embed_start, ephemeral=True)

        for role in interaction.guild.roles:
            if role.name != "@everyone":
                try:
                    await role.delete()
                    await asyncio.sleep(0.5)
                except (discord.Forbidden, discord.HTTPException):
                    continue

        for channel in interaction.guild.channels:
            try:
                await channel.delete()
                await asyncio.sleep(0.5)
            except (discord.Forbidden, discord.HTTPException):
                continue

        embed_final = discord.Embed(
            title="\ud83d\udca5 Nuke termin\u00e9",
            description="Le serveur a \u00e9t\u00e9 enti\u00e8rement nettoy\u00e9.",
            color=0xFF0000
        )
        try:
            await interaction.user.send(embed=embed_final)
        except:
            pass

async def setup(bot):
    await bot.add_cog(NukeCog(bot))
