import discord
from discord.ext import commands
from discord import ui
from database import (
    update_config, get_config, add_command_permission, 
    remove_command_permission, get_command_permissions,
    set_global_lock, get_global_lock, reset_all_permissions
)
from typing import Union

class RestrictedView(ui.View):
    def __init__(self, user_id, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce menu ne vous est pas destiné.", ephemeral=True)
            return False
        return True

class RoleSelect(ui.RoleSelect):
    def __init__(self, command_name, action, guild_id, user_id):
        super().__init__(placeholder=f"Sélectionnez le rôle à {'ajouter' if action == 'add' else 'retirer'}...", min_values=1, max_values=1)
        self.command_name = command_name
        self.action = action
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        if self.action == "add":
            add_command_permission(self.guild_id, self.command_name, role.id)
            await interaction.response.send_message(f"✅ Le rôle **{role.name}** a maintenant accès à `{self.command_name}`.", ephemeral=True)
        else:
            remove_command_permission(self.guild_id, self.command_name, role.id)
            await interaction.response.send_message(f"✅ Le rôle **{role.name}** n'a plus accès à `{self.command_name}` via ce système.", ephemeral=True)

class CommandConfigActionView(RestrictedView):
    def __init__(self, command_name, guild_id, bot, user_id):
        super().__init__(user_id=user_id, timeout=60)
        self.command_name = command_name
        self.guild_id = guild_id
        self.bot = bot

    def get_roles_list(self, interaction):
        role_ids = get_command_permissions(self.guild_id, self.command_name)
        if not role_ids:
            return "Aucun rôle spécifique configuré (permissions de base uniquement)."
        
        role_mentions = []
        for rid in role_ids:
            role = interaction.guild.get_role(int(rid))
            if role:
                role_mentions.append(f"• {role.mention}")
            else:
                role_mentions.append(f"• ID: {rid} (Rôle supprimé)")
        
        return "\n".join(role_mentions)

    @ui.button(label="Ajouter un rôle", style=discord.ButtonStyle.green, emoji="➕")
    async def add_role(self, interaction: discord.Interaction, button: ui.Button):
        view = RestrictedView(user_id=self.user_id)
        view.add_item(RoleSelect(self.command_name, "add", self.guild_id, self.user_id))
        await interaction.response.edit_message(content=f"⚙️ Configurer `{self.command_name}` : Choisissez le rôle à **ajouter**.", embed=None, view=view)

    @ui.button(label="Retirer un rôle", style=discord.ButtonStyle.red, emoji="➖")
    async def remove_role(self, interaction: discord.Interaction, button: ui.Button):
        view = RestrictedView(user_id=self.user_id)
        view.add_item(RoleSelect(self.command_name, "remove", self.guild_id, self.user_id))
        await interaction.response.edit_message(content=f"⚙️ Configurer `{self.command_name}` : Choisissez le rôle à **retirer**.", embed=None, view=view)

    @ui.button(label="Retour", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        view = CommandPaginationView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🛠️ Gestion des Permissions",
            description="Choisissez une commande dans le menu ci-dessous pour modifier les rôles autorisés à l'utiliser.",
            color=0x2b2d31
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)

class CommandSelect(ui.Select):
    def __init__(self, bot, user_id, page=0):
        self.bot = bot
        self.user_id = user_id
        self.page = page
        self.per_page = 25
        
        # Obtenir toutes les commandes sauf command_config pour éviter de se bloquer soi-même
        cmds = sorted([c.name for c in bot.commands if c.name != "command_config"])
        
        start = page * self.per_page
        end = start + self.per_page
        subset = cmds[start:end]
        
        options = []
        for cmd_name in subset:
            options.append(discord.SelectOption(label=cmd_name, description=f"Gérer les accès pour {cmd_name}"))
            
        super().__init__(placeholder=f"Commandes (Page {page+1})", options=options)

    async def callback(self, interaction: discord.Interaction):
        command_name = self.values[0]
        view = CommandConfigActionView(command_name, interaction.guild_id, self.bot, self.user_id)
        
        roles_text = view.get_roles_list(interaction)
        
        embed = discord.Embed(
            title=f"⚙️ Configuration : `{command_name}`",
            description=f"Voici les rôles qui ont actuellement accès à cette commande (en plus des administrateurs) :\n\n{roles_text}",
            color=0x2b2d31
        )
        
        await interaction.response.edit_message(content=None, embed=embed, view=view)

class CommandPaginationView(RestrictedView):
    def __init__(self, bot, user_id, page=0):
        super().__init__(user_id=user_id, timeout=60)
        self.bot = bot
        self.page = page
        
        cmds = sorted([c.name for c in bot.commands if c.name != "command_config"])
        self.total_pages = (len(cmds) - 1) // 25 + 1
        
        self.add_item(CommandSelect(bot, user_id, page))
        
        if self.total_pages > 1:
            if page > 0:
                prev_button = ui.Button(label="Précédent", style=discord.ButtonStyle.grey, emoji="⬅️")
                prev_button.callback = self.prev_page
                self.add_item(prev_button)
            
            if page < self.total_pages - 1:
                next_button = ui.Button(label="Suivant", style=discord.ButtonStyle.grey, emoji="➡️")
                next_button.callback = self.next_page
                self.add_item(next_button)

    @ui.button(label="LOCK/UNLOCK", style=discord.ButtonStyle.danger, emoji="🔒", row=2)
    async def toggle_lock(self, interaction: discord.Interaction, button: ui.Button):
        current_lock = get_global_lock(str(interaction.guild_id))
        new_lock = not current_lock
        set_global_lock(str(interaction.guild_id), new_lock)
        
        status = "🔒 **ACTIVÉ** (Seul l'Owner peut utiliser le bot)" if new_lock else "🔓 **DÉSACTIVÉ** (Retour au fonctionnement normal)"
        await interaction.response.send_message(f"🚨 **Lock Global** : {status}", ephemeral=True)

    @ui.button(label="RESET PERMS", style=discord.ButtonStyle.secondary, emoji="♻️", row=2)
    async def reset_perms(self, interaction: discord.Interaction, button: ui.Button):
        reset_all_permissions(str(interaction.guild_id))
        await interaction.response.send_message("✅ **Toutes les permissions ont été réinitialisées.** (Permissions Discord par défaut rétablies)", ephemeral=True)

    async def prev_page(self, interaction: discord.Interaction):
        view = CommandPaginationView(self.bot, self.user_id, self.page - 1)
        await interaction.response.edit_message(view=view)

    async def next_page(self, interaction: discord.Interaction):
        view = CommandPaginationView(self.bot, self.user_id, self.page + 1)
        await interaction.response.edit_message(view=view)

class ConfigRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="command_config")
    @commands.is_owner()
    async def command_config(self, ctx):
        """Ouvre le menu interactif de gestion des permissions par rôle"""
        view = CommandPaginationView(self.bot, ctx.author.id)
        
        embed = discord.Embed(
            title="🛠️ Gestion des Permissions",
            description="Choisissez une commande dans le menu ci-dessous pour modifier les rôles autorisés à l'utiliser.",
            color=0x2b2d31
        )
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="setup_welcome")
    async def setup_welcome(self, ctx, channel: Union[discord.TextChannel, discord.Thread], *, message: str):
        """Configure le message de bienvenue. Utilisez {user} pour mentionner le joueur."""
        update_config(ctx.guild.id, welcome_channel_id=channel.id, welcome_message=message)
        await ctx.send(embed=discord.Embed(title="✅ Bienvenue configuré", description=f"Salon: {channel.mention}\nMessage: {message}", color=0x2b2d31))

    @commands.command(name="setup_welcome_image")
    async def setup_welcome_image(self, ctx, url: str):
        """Définit l'image de l'embed de bienvenue."""
        update_config(ctx.guild.id, welcome_image_url=url)
        await ctx.send(f"✅ Image de bienvenue mise à jour.")

    @commands.command(name="setup_leave")
    async def setup_leave(self, ctx, channel: Union[discord.TextChannel, discord.Thread], *, message: str):
        """Configure le message d'au revoir. Utilisez {user} pour le nom du joueur."""
        update_config(ctx.guild.id, leave_channel_id=channel.id, leave_message=message)
        await ctx.send(embed=discord.Embed(title="✅ Au revoir configuré", description=f"Salon: {channel.mention}\nMessage: {message}", color=0x2b2d31))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = get_config(member.guild.id)
        if not config or not config.get("welcome_channel_id"): return
        channel = member.guild.get_channel(int(config["welcome_channel_id"]))
        if not channel:
            try: channel = await member.guild.fetch_channel(int(config["welcome_channel_id"]))
            except: return
        msg = config.get("welcome_message", "Bienvenue {user} !").replace("{user}", member.mention)
        embed = discord.Embed(title=f"Bienvenue sur {member.guild.name} !", description=msg, color=0x2b2d31)
        if config.get("welcome_image_url"): embed.set_image(url=config["welcome_image_url"])
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Membres : {member.guild.member_count}")
        await channel.send(content=member.mention, embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = get_config(member.guild.id)
        if not config or not config.get("leave_channel_id"): return
        
        channel_id = int(config["leave_channel_id"])
        channel = member.guild.get_channel(channel_id)
        if not channel:
            try: channel = await member.guild.fetch_channel(channel_id)
            except: return

        msg = config.get("leave_message", "{user} a quitté le serveur.").replace("{user}", f"**{member.display_name}**")
        embed = discord.Embed(title="Un membre nous a quittés...", description=msg, color=0x2b2d31)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Il reste {member.guild.member_count} membres.")
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ConfigRoles(bot))
