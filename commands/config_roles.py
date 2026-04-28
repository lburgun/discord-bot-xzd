import discord
from discord.ext import commands
from discord import ui
from database import update_config, get_config, add_command_permission, remove_command_permission, get_command_permissions
from typing import Union

class RoleSelect(ui.RoleSelect):
    def __init__(self, command_name, action, guild_id):
        super().__init__(placeholder=f"Sélectionnez le rôle à {'ajouter' if action == 'add' else 'retirer'}...", min_values=1, max_values=1)
        self.command_name = command_name
        self.action = action
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        if self.action == "add":
            add_command_permission(self.guild_id, self.command_name, role.id)
            await interaction.response.send_message(f"✅ Le rôle **{role.name}** a maintenant accès à `{self.command_name}`.", ephemeral=True)
        else:
            remove_command_permission(self.guild_id, self.command_name, role.id)
            await interaction.response.send_message(f"✅ Le rôle **{role.name}** n'a plus accès à `{self.command_name}` via ce système.", ephemeral=True)

class CommandConfigActionView(ui.View):
    def __init__(self, command_name, guild_id, bot):
        super().__init__(timeout=60)
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
        view = ui.View()
        view.add_item(RoleSelect(self.command_name, "add", self.guild_id))
        await interaction.response.edit_message(content=f"⚙️ Configurer `{self.command_name}` : Choisissez le rôle à **ajouter**.", view=view)

    @ui.button(label="Retirer un rôle", style=discord.ButtonStyle.red, emoji="➖")
    async def remove_role(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(RoleSelect(self.command_name, "remove", self.guild_id))
        await interaction.response.edit_message(content=f"⚙️ Configurer `{self.command_name}` : Choisissez le rôle à **retirer**.", view=view)

class CommandSelect(ui.Select):
    def __init__(self, bot):
        options = []
        ignored = ["help", "command_config", "setup_welcome", "setup_welcome_image", "setup_leave"]
        
        cmds = sorted([c.name for c in bot.commands if c.name not in ignored])
        for cmd_name in cmds[:25]:
            options.append(discord.SelectOption(label=cmd_name, description=f"Gérer les accès pour {cmd_name}"))
            
        super().__init__(placeholder="Sélectionnez une commande à configurer...", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        command_name = self.values[0]
        view = CommandConfigActionView(command_name, interaction.guild_id, self.bot)
        
        roles_text = view.get_roles_list(interaction)
        
        embed = discord.Embed(
            title=f"⚙️ Configuration : `{command_name}`",
            description=f"Voici les rôles qui ont actuellement accès à cette commande (en plus des administrateurs) :\n\n{roles_text}",
            color=0x2b2d31
        )
        
        await interaction.response.edit_message(content=None, embed=embed, view=view)

class ConfigRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="command_config")
    @commands.has_permissions(administrator=True)
    async def command_config(self, ctx):
        """Ouvre le menu interactif de gestion des permissions par rôle"""
        view = ui.View()
        view.add_item(CommandSelect(self.bot))
        
        embed = discord.Embed(
            title="🛠️ Gestion des Permissions",
            description="Choisissez une commande dans le menu ci-dessous pour modifier les rôles autorisés à l'utiliser.",
            color=0x2b2d31
        )
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="setup_welcome")
    @commands.has_permissions(administrator=True)
    async def setup_welcome(self, ctx, channel: Union[discord.TextChannel, discord.Thread], *, message: str):
        """Configure le message de bienvenue. Utilisez {user} pour mentionner le joueur."""
        update_config(ctx.guild.id, welcome_channel_id=channel.id, welcome_message=message)
        await ctx.send(embed=discord.Embed(title="✅ Bienvenue configuré", description=f"Salon: {channel.mention}\nMessage: {message}", color=0x2b2d31))

    @commands.command(name="setup_welcome_image")
    @commands.has_permissions(administrator=True)
    async def setup_welcome_image(self, ctx, url: str):
        """Définit l'image de l'embed de bienvenue."""
        update_config(ctx.guild.id, welcome_image_url=url)
        await ctx.send(f"✅ Image de bienvenue mise à jour.")

    @commands.command(name="setup_leave")
    @commands.has_permissions(administrator=True)
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
