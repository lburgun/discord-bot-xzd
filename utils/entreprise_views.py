import discord
from discord import ui
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union, Sequence, TypedDict, cast
from database import (
    update_employe_role, update_employe_salaire, remove_employe, get_employes,
    delete_entreprise, get_entreprise, get_entreprise_by_name, update_entreprise_name,
    update_entreprise_visibility, is_employe, get_entreprise_owner_id, user_init, add_employe,
    get_entreprise_buildings, BUILDING_TYPES, calculate_total_revenue,
    calculate_total_maintenance_cost, calculate_total_work_required,
    update_tresorerie_entreprise, get_tresorerie_entreprise, has_permission as has_permission_db,
    get_employe, get_all_entreprises_by_guild, EMPLOYEE_ROLES, get_name_entreprise,
    update_bank, get_work_restants, get_revenu_par_cycle, set_entreprise_tresorerie,
    set_work_restants, get_work_requis, is_entreprise_owner, create_entreprise,
    get_building_cost, withdraw_entreprise_money, get_name_change_cooldown,
    get_building_upgrade_cost, upgrade_building, add_building
)

class EntreprisePaginator(discord.ui.View):
    def __init__(self, bot: discord.Client, guild_id: str, owner_id: str, user_id: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.user_id = user_id
        self.entreprises = get_all_entreprises_by_guild(guild_id) or []
        self.per_page = 5
        self.page = 0
        self.max_page = (len(self.entreprises) - 1) // self.per_page if self.entreprises else 0

        # Initialement, désactive le bouton précédent
        self.previous_button.disabled = True
        if self.max_page <= 0:
            self.next_button.disabled = True

    def get_embed(self):
        embed = discord.Embed(title="Liste des entreprises", color=0x000000)
        start = self.page * self.per_page
        end = start + self.per_page
        for ent in self.entreprises[start:end]:
            owner_id, nom, tresorerie, tresorerie_max, visibilite, revenu_par_cycle, employee_count = ent
            embed.add_field(
                name=nom,
                value = 
                        f"👥 **Employés** : {employee_count} / 10\n"
                        f"💰 **Trésorerie** : {tresorerie} / {tresorerie_max} coins\n"
                        f"🪙 **Distribution** : {revenu_par_cycle} coins\n"
                        f"🔒 **Visibilité** : {visibilite.capitalize()}",inline=False)
        embed.set_footer(text=f"Page {self.page + 1} / {self.max_page + 1}")
        return embed

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction, button):
        if self.page > 0:
            self.page -= 1
            self.next_button.disabled = False
            if self.page == 0:
                self.previous_button.disabled = True
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction, button):
        if self.page < self.max_page:
            self.page += 1
            self.previous_button.disabled = False
            if self.page == self.max_page:
                self.next_button.disabled = True
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

class GestionEmployeSelect(discord.ui.Select):
    def __init__(self, employes: list, bot: discord.Client, guild_id: str, owner_id: str, user_id: str):
        self.bot = bot
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.user_id = user_id
        self.employes = employes

        options = []
        for emp in employes:
            guild = bot.get_guild(int(guild_id))
            member = guild.get_member(int(emp['employe_id'])) if guild else None
            display_name = member.display_name if member else f"Employé {emp['employe_id']}"
            
            options.append(discord.SelectOption(
                label=display_name,
                description=f"Rôle : {emp['role']} | Salaire : {emp['salaire']} coins",
                value=str(emp['employe_id'])
            ))

        super().__init__(placeholder="Sélectionner un employé à gérer", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("❌ Tu n'es pas autorisé à gérer cet employé.", ephemeral=True)

        employe_id = self.values[0]
        employe = next((emp for emp in self.employes if str(emp['employe_id']) == employe_id), None)
        if not employe:
            return await interaction.response.send_message("❌ Employé non trouvé.", ephemeral=True)

        embed = discord.Embed(title="👤 Gestion de l'employé", color=0x000000)
        embed.add_field(
            name="Informations",
            value=f"🎭 Rôle : {employe['role']}\n💸 Salaire : {employe['salaire']} coins\n🛠️ Work effectués : {employe['nb_work_effectues']}",
            inline=False
        )

        view = EmployeActionView(self.bot, self.guild_id, self.owner_id, self.user_id, employe_id)
        await interaction.response.edit_message(embed=embed, view=view)

class RoleSelect(discord.ui.Select):
    def __init__(self, guild_id: str, owner_id: str, employe_id: str, options: List[discord.SelectOption], user_id: str):
        super().__init__(placeholder="Choisir un rôle", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.employe_id = employe_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("❌ Tu n'es pas autorisé.", ephemeral=True)

        if str(interaction.user.id) != str(self.owner_id):
            if not has_permission_db(self.guild_id, str(interaction.user.id), "gerer_employes"):
                return await interaction.response.send_message("❌ Permission insuffisante.", ephemeral=True)

        update_employe_role(self.guild_id, self.owner_id, self.employe_id, self.values[0])
        role_info = EMPLOYEE_ROLES.get(self.values[0], {})
        nom_role = role_info.get('nom', self.values[0])
        await interaction.response.send_message(f"✅ Rôle changé en **{nom_role}**.", ephemeral=True)

class EmployeActionView(discord.ui.View):
    def __init__(self, bot: discord.Client, guild_id: str, owner_id: str, user_id: str, employe_id: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.user_id = user_id
        self.employe_id = employe_id

    @discord.ui.button(label="🎭 Modifier le rôle", style=discord.ButtonStyle.blurple)
    async def modifier_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.owner_id):
            return await interaction.response.send_message("❌ Seul le propriétaire peut faire ça.", ephemeral=True)

        options = [discord.SelectOption(label=info["nom"], description=info["description"], value=rid) for rid, info in EMPLOYEE_ROLES.items()]
        select = RoleSelect(self.guild_id, self.owner_id, self.employe_id, options, self.user_id)
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("Choisissez le nouveau rôle :", view=view, ephemeral=True)

    @discord.ui.button(label="💰 Modifier le salaire", style=discord.ButtonStyle.green)
    async def modifier_salaire(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.owner_id):
            return await interaction.response.send_message("❌ Seul le propriétaire peut faire ça.", ephemeral=True)

        emp = get_employe(self.guild_id, self.owner_id, self.employe_id)
        role_info = EMPLOYEE_ROLES.get(emp["role"].lower(), EMPLOYEE_ROLES["employe"])

        class SalaireModal(discord.ui.Modal, title="Modifier le salaire"):
            salaire = discord.ui.TextInput(label="Nouveau salaire", placeholder=f"Entre {role_info['salaire_min']} et {role_info['salaire_max']} coins")

            def __init__(self, guild_id, owner_id, employe_id, rinfo):
                super().__init__()
                self.guild_id, self.owner_id, self.employe_id, self.rinfo = guild_id, owner_id, employe_id, rinfo

            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    val = int(self.salaire.value)
                    if val < self.rinfo["salaire_min"] or val > self.rinfo["salaire_max"]:
                        return await modal_interaction.response.send_message(f"❌ Salaire hors limites ({self.rinfo['salaire_min']}-{self.rinfo['salaire_max']})", ephemeral=True)
                    update_employe_salaire(self.guild_id, self.owner_id, self.employe_id, val)
                    await modal_interaction.response.send_message(f"✅ Salaire mis à jour : **{val}** coins", ephemeral=True)
                except: await modal_interaction.response.send_message("❌ Nombre invalide.", ephemeral=True)

        await interaction.response.send_modal(SalaireModal(self.guild_id, self.owner_id, self.employe_id, role_info))

    @discord.ui.button(label="🚫 Renvoyer", style=discord.ButtonStyle.red)
    async def renvoyer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.owner_id):
            return await interaction.response.send_message("❌ Seul le propriétaire peut faire ça.", ephemeral=True)

        remove_employe(self.guild_id, self.owner_id, self.employe_id)
        await interaction.response.edit_message(content="✅ L'employé a été renvoyé.", embed=None, view=None)

class BatimentsView(discord.ui.View):
    def __init__(self, bot: discord.Client, guild_id: str, owner_id: str, user_id: str):
        super().__init__(timeout=60)
        self.bot, self.guild_id, self.owner_id, self.user_id = bot, guild_id, owner_id, user_id

    @discord.ui.button(label="🏗️ Acheter un bâtiment", style=discord.ButtonStyle.green)
    async def acheter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.owner_id):
            return await interaction.response.send_message("❌ Seul le propriétaire peut faire ça.", ephemeral=True)

        options = [discord.SelectOption(label=info["nom"], description=f"Coût : {get_building_cost(rid, 1)} coins", value=rid) for rid, info in BUILDING_TYPES.items()]
        select = BuildingSelect(self.bot, self.guild_id, self.owner_id, self.user_id, options)
        view = discord.ui.View(timeout=60).add_item(select)
        await interaction.response.send_message("Choisissez le bâtiment à acheter :", view=view, ephemeral=True)

    @discord.ui.button(label="⬆️ Améliorer un bâtiment", style=discord.ButtonStyle.blurple)
    async def ameliorer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.owner_id):
            return await interaction.response.send_message("❌ Seul le propriétaire peut faire ça.", ephemeral=True)

        buildings = get_entreprise_buildings(self.guild_id, self.owner_id)
        if not buildings:
            return await interaction.response.send_message("❌ Aucun bâtiment à améliorer.", ephemeral=True)

        options = [discord.SelectOption(label=f"{b['nom']} (ID: {b['building_id']})", description=f"Niveau {b['level']} → {b['level']+1} | Coût : {get_building_upgrade_cost(self.guild_id, self.owner_id, b['building_id'])} coins", value=str(b["building_id"])) for b in buildings]
        select = BuildingUpgradeSelect(self.bot, self.guild_id, self.owner_id, self.user_id, options)
        view = discord.ui.View(timeout=60).add_item(select)
        await interaction.response.send_message("Choisissez le bâtiment à améliorer :", view=view, ephemeral=True)

class BuildingSelect(discord.ui.Select):
    def __init__(self, bot, guild_id, owner_id, user_id, options):
        super().__init__(placeholder="Choisissez un bâtiment", options=options)
        self.bot, self.guild_id, self.owner_id, self.user_id = bot, guild_id, owner_id, user_id

    async def callback(self, interaction: discord.Interaction):
        cost = get_building_cost(self.values[0], 1)
        treso = get_tresorerie_entreprise(self.guild_id, self.owner_id)
        if cost > treso:
            return await interaction.response.send_message(f"❌ Fonds insuffisants ({cost} coins requis).", ephemeral=True)
        if add_building(self.guild_id, self.owner_id, self.values[0]):
            update_tresorerie_entreprise(self.guild_id, self.owner_id, treso - cost)
            await interaction.response.send_message(f"✅ Bâtiment acheté !", ephemeral=True)

class BuildingUpgradeSelect(discord.ui.Select):
    def __init__(self, bot, guild_id, owner_id, user_id, options):
        super().__init__(placeholder="Choisissez un bâtiment à améliorer", options=options)
        self.bot, self.guild_id, self.owner_id, self.user_id = bot, guild_id, owner_id, user_id

    async def callback(self, interaction: discord.Interaction):
        bid = int(self.values[0])
        cost = get_building_upgrade_cost(self.guild_id, self.owner_id, bid)
        treso = get_tresorerie_entreprise(self.guild_id, self.owner_id)
        if cost > treso:
            return await interaction.response.send_message(f"❌ Fonds insuffisants ({cost} coins requis).", ephemeral=True)
        if upgrade_building(self.guild_id, self.owner_id, bid):
            update_tresorerie_entreprise(self.guild_id, self.owner_id, treso - cost)
            await interaction.response.send_message(f"✅ Bâtiment amélioré !", ephemeral=True)

class ParametresView(discord.ui.View):
    def __init__(self, bot, guild_id, owner_id, user_id):
        super().__init__(timeout=60)
        self.bot, self.guild_id, self.owner_id, self.user_id = bot, guild_id, owner_id, user_id

    @discord.ui.button(label="Changer le nom", style=discord.ButtonStyle.blurple, emoji="✏️")
    async def changer_nom(self, interaction: discord.Interaction, button: discord.ui.Button):
        cooldown = get_name_change_cooldown(self.guild_id, self.owner_id)
        if cooldown > 0:
            return await interaction.response.send_message(f"⏳ Attends {cooldown//60}m encore.", ephemeral=True)

        class NomModal(discord.ui.Modal, title="Nouveau nom"):
            nom = discord.ui.TextInput(label="Nom", min_length=3, max_length=50)
            def __init__(self, g, o): super().__init__(); self.g, self.o = g, o
            async def on_submit(self, mi):
                update_entreprise_name(self.g, self.o, self.nom.value, datetime.now().isoformat())
                await mi.response.send_message(f"✅ Nom changé en **{self.nom.value}**.", ephemeral=True)
        await interaction.response.send_modal(NomModal(self.guild_id, self.owner_id))

    @discord.ui.button(label="Changer la visibilité", style=discord.ButtonStyle.grey, emoji="🔒")
    async def changer_visibilite(self, interaction: discord.Interaction, button: discord.ui.Button):
        ent = get_entreprise(self.guild_id, self.owner_id)
        nouvelle = "privée" if ent.get("visibilite") == "publique" else "publique"
        update_entreprise_visibility(self.guild_id, self.owner_id, nouvelle)
        await interaction.response.send_message(f"✅ Visibilité : **{nouvelle}**", ephemeral=True)

    @discord.ui.button(label="Supprimer l'entreprise", style=discord.ButtonStyle.red, emoji="🗑️")
    async def supprimer(self, interaction: discord.Interaction, button: discord.ui.Button):
        delete_entreprise(self.guild_id, self.owner_id)
        await interaction.response.edit_message(content="✅ Entreprise supprimée.", embed=None, view=None)

class MenuEntrepriseSelect(ui.Select):
    def __init__(self, bot, guild_id, owner_id, user_id):
        self.bot, self.guild_id, self.owner_id, self.user_id = bot, guild_id, owner_id, user_id
        options = [discord.SelectOption(label="Statut", emoji="📊")]
        role = None
        if is_employe(guild_id, user_id):
            emp = get_employe(guild_id, owner_id, user_id)
            if emp: role = emp.get("role", "employe")
        
        if str(user_id) == str(owner_id) or has_permission_db(guild_id, user_id, "voir_employes"):
            options.append(discord.SelectOption(label="Employés", emoji="👥"))
        if str(user_id) == str(owner_id) or has_permission_db(guild_id, user_id, "voir_batiments"):
            options.append(discord.SelectOption(label="Bâtiments", emoji="🏢"))
        if str(user_id) == str(owner_id):
            options.append(discord.SelectOption(label="Paramètres", emoji="⚙️"))
        super().__init__(placeholder="Choisissez une section", options=options)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("❌ Pas ton menu.", ephemeral=True)
        
        choice = self.values[0]
        ent = get_entreprise(self.guild_id, self.owner_id)
        if not ent: return await interaction.response.send_message("❌ Entreprise introuvable.", ephemeral=True)

        if choice == "Statut":
            embed = discord.Embed(title=f"🏭 Entreprise {ent['nom']}", color=0x000000)
            base_work = get_work_requis(self.guild_id, self.owner_id)
            total_work = base_work + calculate_total_work_required(self.guild_id, self.owner_id)
            base_rev = get_revenu_par_cycle(self.guild_id, self.owner_id)
            total_rev = base_rev + calculate_total_revenue(self.guild_id, self.owner_id)
            maint = calculate_total_maintenance_cost(self.guild_id, self.owner_id)
            
            embed.add_field(name="💰 Trésorerie", value=f"`{ent['tresorerie']}` / `{ent['tresorerie_max']}` coins")
            embed.add_field(name="🛠️ Work restants", value=f"`{ent['nb_work_restants']}` / `{total_work}`")
            embed.add_field(name="🪙 Revenus cycle", value=f"Total: `{total_rev - maint}` (Rev: {total_rev}, Maint: -{maint})", inline=False)
            await interaction.response.edit_message(embed=embed, view=self.view)

        elif choice == "Employés":
            employes = get_employes(self.guild_id, self.owner_id)
            embed = discord.Embed(title="👥 Employés", color=0x000000)
            for e in employes: embed.add_field(name=f"ID: {e['employe_id']}", value=f"Rôle: {e['role']} | Salaire: {e['salaire']} | Work: {e['nb_work_effectues']}", inline=False)
            view = GestionEmployeSelect(employes, self.bot, self.guild_id, self.owner_id, self.user_id) if str(self.user_id) == str(self.owner_id) else self.view
            await interaction.response.edit_message(embed=embed, view=discord.ui.View().add_item(view) if str(self.user_id) == str(self.owner_id) else self.view)

        elif choice == "Bâtiments":
            embed = discord.Embed(title="🏢 Bâtiments", color=0x000000)
            buildings = get_entreprise_buildings(self.guild_id, self.owner_id)
            for b in buildings: embed.add_field(name=f"{b['nom']} (Lv.{b['level']})", value=f"Rev: {b['revenue']} | Maint: {b['maintenance_cost']}", inline=False)
            await interaction.response.edit_message(embed=embed, view=BatimentsView(self.bot, self.guild_id, self.owner_id, self.user_id))

        elif choice == "Paramètres":
            await interaction.response.edit_message(content="⚙️ Paramètres", view=ParametresView(self.bot, self.guild_id, self.owner_id, self.user_id))

class ConfirmDeleteEntrepriseView(discord.ui.View):
    def __init__(self, bot: discord.Client, guild_id: str, owner_id: str, user_id: str):
        super().__init__(timeout=60)
        self.bot, self.guild_id, self.owner_id, self.user_id = bot, guild_id, owner_id, user_id

    @discord.ui.button(label="✅ Confirmer", style=discord.ButtonStyle.green)
    async def confirmer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("❌ Pas pour toi.", ephemeral=True)
        delete_entreprise(self.guild_id, self.owner_id)
        await interaction.response.edit_message(content="✅ Entreprise supprimée.", embed=None, view=None)

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.red)
    async def annuler(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("❌ Pas pour toi.", ephemeral=True)
        await interaction.response.edit_message(content="❌ Suppression annulée.", embed=None, view=None)

class InviteEntrepriseView(discord.ui.View):
    def __init__(self, bot: discord.Client, guild_id: str, owner_id: str, user_id: str):
        super().__init__(timeout=60)
        self.bot, self.guild_id, self.owner_id, self.user_id = bot, guild_id, owner_id, user_id

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.green)
    async def accepter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("❌ Pas pour toi.", ephemeral=True)
        if is_employe(self.guild_id, str(interaction.user.id)):
            return await interaction.response.send_message("❌ Déjà employé.", ephemeral=True)
        add_employe(self.guild_id, self.owner_id, str(interaction.user.id))
        await interaction.response.edit_message(content=f"✅ <@{interaction.user.id}> a rejoint l'entreprise !", view=None)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.red)
    async def refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("❌ Pas pour toi.", ephemeral=True)
        await interaction.response.edit_message(content=f"❌ Invitation refusée.", view=None)

class MenuEntrepriseView(ui.View):
    def __init__(self, bot, guild_id, owner_id, user_id):
        super().__init__(timeout=None)
        self.add_item(MenuEntrepriseSelect(bot, guild_id, owner_id, user_id))

async def setup(bot): pass
