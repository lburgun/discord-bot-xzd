import discord
from discord.ext import commands
from discord import ui
from database import update_config, get_config
from typing import Union
import json

class SupportRoleSelect(ui.RoleSelect):
    def __init__(self, action, guild_id):
        super().__init__(placeholder=f"Sélectionnez le rôle à {'ajouter' if action == 'add' else 'retirer'}...", min_values=1, max_values=1)
        self.action = action
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        config = get_config(self.guild_id) or {}
        roles = config.get("support_role_ids", [])
        
        if self.action == "add":
            if role.id not in roles:
                roles.append(role.id)
                update_config(self.guild_id, support_role_ids=json.dumps(roles))
                await interaction.response.send_message(f"✅ Le rôle **{role.name}** a été ajouté aux supports des tickets.", ephemeral=True)
            else:
                await interaction.response.send_message(f"ℹ️ Ce rôle est déjà dans la liste.", ephemeral=True)
        else:
            if role.id in roles:
                roles.remove(role.id)
                update_config(self.guild_id, support_role_ids=json.dumps(roles))
                await interaction.response.send_message(f"✅ Le rôle **{role.name}** a été retiré des supports.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Ce rôle n'est pas dans la liste.", ephemeral=True)

class SupportConfigView(ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @ui.button(label="Ajouter un rôle support", style=discord.ButtonStyle.green, emoji="➕")
    async def add(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View().add_item(SupportRoleSelect("add", self.guild_id))
        await interaction.response.edit_message(content="Sélectionnez le rôle à **ajouter** :", view=view)

    @ui.button(label="Retirer un rôle support", style=discord.ButtonStyle.red, emoji="➖")
    async def remove(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View().add_item(SupportRoleSelect("remove", self.guild_id))
        await interaction.response.edit_message(content="Sélectionnez le rôle à **retirer** :", view=view)

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup_captcha")
    @commands.has_permissions(administrator=True)
    async def setup_captcha(self, ctx, channel_input: str, role_input: str):
        """Configure le système de captcha (ID ou Mention)"""
        channel = ctx.guild.get_channel(int(channel_input.strip('<#> '))) if not channel_input.isdigit() else ctx.guild.get_channel(int(channel_input))
        role = ctx.guild.get_role(int(role_input.strip('<@&> '))) if not role_input.isdigit() else ctx.guild.get_role(int(role_input))
        if not channel or not role: return await ctx.send("❌ Salon ou Rôle introuvable.")
        update_config(ctx.guild.id, captcha_channel_id=channel.id, verified_role_id=role.id)
        await ctx.send(f"✅ Captcha configuré dans {channel.mention} avec le rôle **{role.name}**")

    @commands.command(name="setup_tickets")
    @commands.has_permissions(administrator=True)
    async def setup_tickets(self, ctx, category_input: str):
        """Configure la catégorie des tickets (ID recommandé)"""
        category = ctx.guild.get_channel(int(category_input)) if category_input.isdigit() else discord.utils.get(ctx.guild.categories, name=category_input)
        if not category or not isinstance(category, discord.CategoryChannel):
            return await ctx.send("❌ Catégorie introuvable. Utilisez l'ID de la catégorie.")
        update_config(ctx.guild.id, ticket_category_id=category.id)
        await ctx.send(f"✅ Catégorie des tickets : **{category.name}**")

    @commands.command(name="ticket_roles")
    @commands.has_permissions(administrator=True)
    async def ticket_roles(self, ctx):
        """Gère les rôles qui peuvent voir et répondre aux tickets"""
        config = get_config(ctx.guild.id) or {}
        role_ids = config.get("support_role_ids", [])
        
        mentions = []
        for rid in role_ids:
            r = ctx.guild.get_role(int(rid))
            if r: mentions.append(r.mention)
        
        roles_text = ", ".join(mentions) if mentions else "Aucun rôle configuré."
        
        embed = discord.Embed(
            title="🎫 Gestion des Rôles Support",
            description=f"Ces rôles ont accès aux tickets créés :\n\n{roles_text}",
            color=0x2b2d31
        )
        await ctx.send(embed=embed, view=SupportConfigView(ctx.guild.id))

    @commands.command(name="setup_voice")
    @commands.has_permissions(administrator=True)
    async def setup_voice(self, ctx, channel_input: str):
        """Définit le salon générateur de vocaux"""
        channel = ctx.guild.get_channel(int(channel_input.strip('<#> '))) if not channel_input.isdigit() else ctx.guild.get_channel(int(channel_input))
        if not channel or not isinstance(channel, discord.VoiceChannel): return await ctx.send("❌ Salon vocal introuvable.")
        update_config(ctx.guild.id, voice_trigger_id=channel.id)
        await ctx.send(f"✅ Salon générateur défini sur {channel.mention}")

async def setup(bot):
    await bot.add_cog(Config(bot))
