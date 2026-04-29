import discord
from discord.ext import commands
import json
import zlib
from datetime import datetime
import asyncio
from database import save_db_backup, get_user_backups, get_backup_data, delete_db_backup

class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="backup")
    @commands.has_permissions(administrator=True)
    async def backup_cmd(self, ctx):
        """Menu de gestion des sauvegardes personnelles (Structure complète)"""
        embed = discord.Embed(
            title="💎 Système de Sauvegarde Avancé",
            description=(
                "Sauvegardez la structure complète d'un serveur et restaurez-la où vous voulez.\n\n"
                "**Ce qui est sauvegardé :**\n"
                "• Hiérarchie des Rôles (Couleurs, Permissions globales)\n"
                "• Catégories et Salons (Texte, Vocal, Stage)\n"
                "• **Permissions précises** par salon et catégorie (Overwrites)\n"
                "• Configuration par utilisateur (utilisable sur n'importe quel serveur)"
            ),
            color=0x2b2d31
        )
        embed.set_footer(text="Sauvegardes stockées de manière sécurisée par utilisateur.")
        await ctx.reply(embed=embed, view=BackupMainView(ctx))

class BackupMainView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    @discord.ui.button(label="📥 Créer une sauvegarde", style=discord.ButtonStyle.green)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Action non autorisée.", ephemeral=True)
        await interaction.response.send_modal(CreateBackupModal())

    @discord.ui.button(label="📂 Gérer mes sauvegardes", style=discord.ButtonStyle.blurple)
    async def list_backups(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Action non autorisée.", ephemeral=True)
        
        backups = get_user_backups(str(interaction.user.id))
        if not backups:
            return await interaction.response.send_message("❌ Aucune sauvegarde trouvée dans votre compte.", ephemeral=True)
        
        view = discord.ui.View()
        options = []
        for bid, name, date, gid in backups[:25]:
            options.append(discord.SelectOption(
                label=name, 
                description=f"ID: {bid} | Date: {date}", 
                value=str(bid),
                emoji="📄"
            ))
        
        select = discord.ui.Select(placeholder="Choisissez une sauvegarde à gérer...", options=options)
        
        async def select_callback(inter: discord.Interaction):
            backup_id = select.values[0] # C'est dÃ©jÃ  une string (ObjectId)
            await inter.response.edit_message(
                content=f"⚙️ **Gestion de la sauvegarde #{backup_id}**", 
                embed=None, 
                view=BackupActionView(backup_id, self.ctx)
            )
        
        select.callback = select_callback
        view.add_item(select)
        await interaction.response.send_message("Vos sauvegardes personnelles :", view=view, ephemeral=True)

class CreateBackupModal(discord.ui.Modal, title="Nommer la sauvegarde"):
    name = discord.ui.TextInput(label="Nom", placeholder="Ex: Ma_Config_Gaming", min_length=3, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ Analyse et sauvegarde de la structure en cours...", ephemeral=True)
        
        guild = interaction.guild
        backup_data = {
            "backup_name": self.name.value,
            "roles": [],
            "categories": []
        }

        # 1. Sauvegarde des Rôles (on ignore les rôles de bots et @everyone)
        # On sauvegarde le nom pour pouvoir mapper les permissions même sur un autre serveur
        for role in sorted(guild.roles, key=lambda r: r.position):
            if not role.is_default() and not role.managed:
                backup_data["roles"].append({
                    "name": role.name,
                    "color": role.color.value,
                    "permissions": role.permissions.value,
                    "hoist": role.hoist,
                    "mentionable": role.mentionable
                })

        # 2. Sauvegarde des Catégories et Salons avec Overwrites
        for cat in guild.categories:
            cat_info = {
                "name": cat.name,
                "overwrites": [],
                "channels": []
            }
            
            # Overwrites de catégorie (on stocke le NOM du rôle pour le mappage futur)
            for target, overwrite in cat.overwrites.items():
                if isinstance(target, discord.Role):
                    cat_info["overwrites"].append({
                        "name": target.name,
                        "type": "role",
                        "allow": overwrite.pair()[0].value,
                        "deny": overwrite.pair()[1].value
                    })

            for chan in cat.channels:
                chan_data = {
                    "name": chan.name,
                    "type": str(chan.type),
                    "topic": getattr(chan, "topic", None),
                    "overwrites": []
                }
                # Overwrites de salon
                for target, overwrite in chan.overwrites.items():
                    if isinstance(target, discord.Role):
                        chan_data["overwrites"].append({
                            "name": target.name,
                            "type": "role",
                            "allow": overwrite.pair()[0].value,
                            "deny": overwrite.pair()[1].value
                        })
                cat_info["channels"].append(chan_data)
            
            backup_data["categories"].append(cat_info)

        # Compression et stockage
        compressed = zlib.compress(json.dumps(backup_data).encode('utf-8'))
        save_db_backup(str(guild.id), str(interaction.user.id), self.name.value, compressed)
        
        await interaction.followup.send(f"✅ Sauvegarde **{self.name.value}** réussie ! Vous pouvez la restaurer sur n'importe quel serveur.", ephemeral=True)

class BackupActionView(discord.ui.View):
    def __init__(self, backup_id, ctx):
        super().__init__(timeout=300)
        self.backup_id = backup_id
        self.ctx = ctx

    @discord.ui.button(label="🚀 Restaurer ici", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def restore(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⚠️ **ATTENTION** : La restauration va SUPPRIMER tous les salons et rôles existants pour cloner la sauvegarde.\n"
            "Tapez `CONFIRMER LA RESTAURATION` dans ce salon pour valider.", 
            ephemeral=True
        )
        
        def check(m): return m.author == interaction.user and m.channel == interaction.channel and m.content == "CONFIRMER LA RESTAURATION"
        try:
            await self.ctx.bot.wait_for('message', check=check, timeout=60.0)
        except asyncio.TimeoutError:
            return await interaction.followup.send("❌ Délai dépassé. Restauration annulée.", ephemeral=True)

        raw = get_backup_data(self.backup_id)
        if not raw: return await interaction.followup.send("❌ Données corrompues.")
        
        data = json.loads(zlib.decompress(raw).decode('utf-8'))
        guild = interaction.guild
        
        await interaction.followup.send("🏗️ Nettoyage du serveur et début de la reconstruction...")

        # 1. Nettoyage total
        for c in guild.channels:
            try: await c.delete()
            except: pass
        for r in guild.roles:
            if not r.is_default() and not r.managed:
                try: await r.delete()
                except: pass

        # 2. Création des Rôles et mapping par nom
        role_map = {}
        for r_data in data["roles"]:
            try:
                new_role = await guild.create_role(
                    name=r_data["name"],
                    color=discord.Color(r_data["color"]),
                    permissions=discord.Permissions(r_data["permissions"]),
                    hoist=r_data["hoist"],
                    mentionable=r_data["mentionable"]
                )
                role_map[r_data["name"]] = new_role
            except: pass

        # 3. Reconstruction des Catégories et Salons avec mappage des permissions
        for c_data in data["categories"]:
            # Préparer les overwrites de catégorie
            cat_overwrites = {}
            for ov in c_data["overwrites"]:
                target_role = role_map.get(ov["name"])
                if target_role:
                    cat_overwrites[target_role] = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(ov["allow"]),
                        discord.Permissions(ov["deny"])
                    )

            new_cat = await guild.create_category(name=c_data["name"], overwrites=cat_overwrites)

            for ch in c_data["channels"]:
                # Préparer les overwrites du salon
                chan_overwrites = {}
                for ov in ch["overwrites"]:
                    target_role = role_map.get(ov["name"])
                    if target_role:
                        chan_overwrites[target_role] = discord.PermissionOverwrite.from_pair(
                            discord.Permissions(ov["allow"]),
                            discord.Permissions(ov["deny"])
                        )

                if ch["type"] == "text":
                    await guild.create_text_channel(name=ch["name"], category=new_cat, topic=ch["topic"], overwrites=chan_overwrites)
                elif ch["type"] == "voice":
                    await guild.create_voice_channel(name=ch["name"], category=new_cat, overwrites=chan_overwrites)

        await interaction.followup.send("✅ **Restauration terminée !** La structure et les permissions ont été clonées.")

    @discord.ui.button(label="🗑️ Supprimer", style=discord.ButtonStyle.grey)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if delete_db_backup(self.backup_id, str(interaction.user.id)):
            await interaction.response.edit_message(content="✅ Sauvegarde définitivement supprimée.", view=None)
        else:
            await interaction.response.send_message("❌ Impossible de supprimer cette sauvegarde.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Backup(bot))
