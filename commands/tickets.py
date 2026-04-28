import discord
from discord.ext import commands
from database import get_config, create_ticket, close_ticket, has_open_ticket
import asyncio
from datetime import timedelta

class TicketModal(discord.ui.Modal, title="Ouverture d'un Ticket"):
    subject = discord.ui.TextInput(
        label="Sujet du problème",
        placeholder="Ex: Problème de connexion, Question...",
        min_length=5,
        max_length=100
    )
    description = discord.ui.TextInput(
        label="Description détaillée",
        placeholder="Décrivez votre souci ici...",
        style=discord.TextStyle.paragraph,
        min_length=10,
        max_length=1000
    )

    def __init__(self, config):
        super().__init__()
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(int(self.config["ticket_category_id"]))
        
        if not category:
            return await interaction.response.send_message("❌ Catégorie introuvable.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        mentions = [interaction.user.mention]
        if self.config.get("support_role_ids"):
            import json
            try:
                role_ids = json.loads(self.config["support_role_ids"]) if isinstance(self.config["support_role_ids"], str) else self.config["support_role_ids"]
                for role_id in role_ids:
                    role = guild.get_role(int(role_id))
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                        mentions.append(role.mention)
            except: pass

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        
        create_ticket(channel.id, guild.id, interaction.user.id)
        
        embed = discord.Embed(
            title=f"Ticket de {interaction.user.name}",
            description=f"Un nouveau ticket a été ouvert par {interaction.user.mention}.",
            color=discord.Color.green()
        )
        embed.add_field(name="Sujet", value=self.subject.value, inline=False)
        embed.add_field(name="Description", value=self.description.value, inline=False)
        embed.set_footer(text="Utilisez le bouton ci-dessous pour fermer le ticket.")

        await channel.send(content=" ".join(mentions), embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Ton ticket a été créé : {channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="ticket_open_persistent")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if has_open_ticket(interaction.guild_id, interaction.user.id):
            return await interaction.response.send_message("❌ Tu as déjà un ticket ouvert !", ephemeral=True)

        config = get_config(interaction.guild_id)
        if not config or not config.get("ticket_category_id"):
            return await interaction.response.send_message("❌ Le système n'est pas configuré.", ephemeral=True)
        
        await interaction.response.send_modal(TicketModal(config))

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close_persistent")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        close_ticket(interaction.channel_id)
        await interaction.response.send_message("Le ticket va être fermé dans 5 secondes...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="send_ticket_panel")
    @commands.has_permissions(administrator=True)
    async def send_ticket_panel(self, ctx):
        """Envoie le panneau de tickets"""
        embed = discord.Embed(
            title="🎫 Support Technique", 
            description="Besoin d'aide ? Cliquez sur le bouton ci-dessous pour remplir le formulaire et ouvrir un ticket.", 
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=TicketView())

async def setup(bot):
    await bot.add_cog(Tickets(bot))
