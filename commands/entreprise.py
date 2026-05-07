import discord
from discord.ext import commands
from database import (
    get_employes, get_tresorerie_entreprise, get_name_entreprise, update_bank,
    update_tresorerie_entreprise, get_work_restants, get_revenu_par_cycle, get_entreprise,
    set_entreprise_tresorerie, set_work_restants, get_work_requis, get_all_entreprises_by_guild,
    is_employe, is_entreprise_owner, remove_employe, get_entreprise_owner_id, get_entreprise_by_name,
    user_init, add_employe, create_entreprise, get_entreprise_buildings, calculate_total_revenue,
    calculate_total_maintenance_cost, calculate_total_work_required, withdraw_entreprise_money,
    has_permission, EMPLOYEE_ROLES, get_employe, update_employe_role, update_employe_salaire,
    get_wallet_bank, update_wallet, reorganize_building_ids
)
from utils.entreprise_views import MenuEntrepriseView, InviteEntrepriseView, EntreprisePaginator, ConfirmDeleteEntrepriseView
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union, Sequence
from discord.ext.commands import Context


def message_send(ctx: Context, embed: discord.Embed, bot: commands.Bot):
    bot.loop.create_task(ctx.reply(embed=embed))


def calculate_total_maintenance_cost(guild_id: str, owner_id: str) -> int:
    from database import db
    import datetime
    
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    if ent and ent.get("patent_expiry"):
        try:
            expiry = datetime.datetime.fromisoformat(ent["patent_expiry"])
            if datetime.datetime.now() < expiry:
                return 0 # Brevet actif, maintenance = 0
        except Exception:
            pass

    buildings = get_entreprise_buildings(guild_id, owner_id)
    return sum(get_building_maintenance(b["building_type"], b["level"]) for b in buildings)

def payer_employes(guild_id: str, owner_id: str, bot: commands.Bot, ctx: Optional[Context] = None):
    employes = get_employes(guild_id, owner_id)
    tresorerie = get_tresorerie_entreprise(guild_id, owner_id)
    total_salaires = sum(emp['salaire'] for emp in employes)
    if total_salaires > tresorerie:
        return False  # Pas assez d'argent
    # Verser les salaires à chaque employé

    nom_entreprise = get_name_entreprise(guild_id, owner_id)
    salaire_str = ""

    for emp in employes:
        user_id = emp['employe_id']
        salaire = emp['salaire']
        update_bank(guild_id, user_id, salaire)
        salaire_str += f"👤<@{user_id}> a été payé `{salaire}` coins. \n"

    if ctx:
        embed = discord.Embed(colour=0x000000)
        embed.add_field(name=f"💳 Salaire entreprise **{nom_entreprise}**",
                                value=salaire_str,
                                inline=False)
        message_send(ctx, embed, bot)

    # Déduire de la trésorerie
    update_tresorerie_entreprise(guild_id, owner_id, tresorerie - total_salaires)
    return True  # Succès


def verifier_cycle_et_payer(guild_id: str, owner_id: str, bot: commands.Bot, ctx: Optional[Context] = None):
    # Vérifie si le cycle est terminé
    work_restants = get_work_restants(guild_id, owner_id)
    if work_restants > 0:
        return False  # Cycle pas encore terminé

    # Calcul des revenus des bâtiments
    buildings_revenue = calculate_total_revenue(guild_id, owner_id)
    base_revenue = get_revenu_par_cycle(guild_id, owner_id)
    gain_total = base_revenue + buildings_revenue

    # Paiement des employés
    success = payer_employes(guild_id, owner_id, bot, ctx)
    if not success:
        return False  # Paiement impossible (pas assez de trésorerie)

    # Crédite la trésorerie avec le gain
    entreprise = get_entreprise(guild_id, owner_id)
    if not entreprise:
        return False

    # Déduire les coûts d'entretien des bâtiments
    maintenance_cost = calculate_total_maintenance_cost(guild_id, owner_id)
    gain_total -= maintenance_cost

    # Mise à jour de la trésorerie
    nouvelle_tresorerie = min(
        entreprise["tresorerie"] + gain_total,
        entreprise["tresorerie_max"]
    )
    set_entreprise_tresorerie(guild_id, owner_id, nouvelle_tresorerie)

    # Mine Passive Extraction
    buildings = get_entreprise_buildings(guild_id, owner_id)
    mine_building = next((b for b in buildings if b["building_type"] == "mine"), None)
    minerals_str = ""
    if mine_building:
        import random
        from database import get_inventaire, update_inventaire
        level = mine_building["level"]
        num_minerals = random.randint(1, level + 1)
        
        # Probability weights for passive mining (slightly better than normal mining)
        weights = {
            "Charbon": 40, "Fer": 30, "Or": 15, "Diamant": 10, "Rubis": 5
        }
        minerals_found = {}
        for _ in range(num_minerals):
            total_weight = sum(weights.values())
            r = random.uniform(0, total_weight)
            cumul = 0
            for min_name, w in weights.items():
                cumul += w
                if r <= cumul:
                    minerals_found[min_name] = minerals_found.get(min_name, 0) + 1
                    break
                    
        if minerals_found:
            inv = get_inventaire(guild_id, owner_id)
            if "minerals" not in inv: inv["minerals"] = {}
            for m, q in minerals_found.items():
                inv["minerals"][m] = inv["minerals"].get(m, 0) + q
            update_inventaire(guild_id, owner_id, inv)
            
            parts = [f"{q}x {m}" for m, q in minerals_found.items()]
            minerals_str = "\n".join(parts)

    # Réinitialise le compteur de work en prenant en compte les bâtiments
    base_work = get_work_requis(guild_id, owner_id)
    building_work = calculate_total_work_required(guild_id, owner_id)
    total_work = base_work + building_work
    set_work_restants(guild_id, owner_id, total_work)

    # Afficher un résumé des gains et coûts
    if ctx:
        embed = discord.Embed(
            title="📊 Résumé du cycle",
            color=0x000000
        )
        embed.add_field(
            name="Revenus",
            value=f"```\nBase: {base_revenue}💰\nBâtiments: {buildings_revenue}💰\nTotal: {base_revenue + buildings_revenue}💰\n```",
            inline=False
        )
        embed.add_field(
            name="Dépenses",
            value=f"```\nEntretien des bâtiments: {maintenance_cost}💰\n```",
            inline=False
        )
        embed.add_field(
            name="Bilan",
            value=f"```\nGain net: {gain_total}💰\nNouvelle trésorerie: {nouvelle_tresorerie}💰\n```",
            inline=False
        )
        if minerals_str:
            embed.add_field(
                name="⛏️ Extraction Minière Passive",
                value=f"La mine de l'entreprise a rapporté des ressources qui ont été placées dans l'inventaire du patron :\n```\n{minerals_str}\n```",
                inline=False
            )
        embed.add_field(
            name="Prochain cycle",
            value=f"```\nWorks requis: {total_work}\n(Base: {base_work} + Bâtiments: {building_work})\n```",
            inline=False
        )
        bot.loop.create_task(ctx.reply(embed=embed))

    return True


class EntrepriseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="entreprise", aliases=["e"], invoke_without_command=True)
    async def entreprise(self, ctx: commands.Context):
        if not ctx.guild:
            embed = discord.Embed(description="❌ Cette commande ne peut être utilisée que sur un serveur.", color=0x000000)
            await ctx.send(embed=embed)
            return

        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        # Vérifier si l'utilisateur est propriétaire d'une entreprise
        entreprise = get_entreprise(guild_id, user_id)
        if entreprise:
            owner_id = user_id
        else:
            # Si l'utilisateur n'est pas propriétaire, vérifier s'il est employé
            if is_employe(guild_id, user_id):
                owner_id = get_entreprise_owner_id(guild_id, user_id)
                if owner_id:
                    entreprise = get_entreprise(guild_id, owner_id)
                else:
                    embed = discord.Embed(description="❌ Une erreur est survenue en récupérant les informations de l'entreprise.", color=0x000000)
                    await ctx.send(embed=embed)
                    return
            else:
                embed = discord.Embed(description="❌ Tu n'as pas d'entreprise et tu n'es pas employé. Utilise `+entreprise create` pour en créer une entreprise.", color=0x000000)
                await ctx.send(embed=embed)
                return

        if not entreprise:
            embed = discord.Embed(description="❌ Une erreur est survenue en récupérant les informations de l'entreprise.", color=0x000000)
            await ctx.send(embed=embed)
            return

        # Créer l'embed de bienvenue
        embed = discord.Embed(
            title="🏢 Bienvenue !",
            description=f"Bienvenue dans l'entreprise **{entreprise['nom']}** !\nUtilise le menu ci-dessous pour gérer l'entreprise.",
            color=0x000000
        )
        embed.set_thumbnail(url="://cdn.discordapp.com/attachments/1255915156467351592/1382876347851997415/ddd.jpg?ex=684cbf75&is=684b6df5&hm=1e6f7b600356016e1d00e06a4e8b6a16eb18cc73ba0f6b2d3698e4f39d2b07f2&")

        view = MenuEntrepriseView(self.bot, guild_id, owner_id, user_id)
        await ctx.send(embed=embed, view=view)

    @entreprise.command(aliases=["dep", "deposer"])
    async def deposit(self, ctx, amount: Optional[str] = None):
        """Dépose de l'argent dans l'entreprise (propriétaire uniquement)"""
        try:
            guild_id = str(ctx.guild.id)
            user_id = str(ctx.author.id)
            
            # Vérification de permission
            if not is_entreprise_owner(guild_id, user_id):
                embed = discord.Embed(
                    title="❌ Permission refusée",
                    description="Seul le propriétaire peut déposer de l'argent dans l'entreprise.",
                    color=0x000000
                )
                return await ctx.reply(embed=embed)

            # Vérification du montant
            if amount is None:
                return await ctx.reply("❌ Veuillez entrer une somme à déposer.")

            # Vérifie l'argent de l'utilisateur
            balances = get_wallet_bank(guild_id, user_id)
            wallet = balances["wallet"]

            if amount.lower() == "all":
                deposit_amount = wallet
            else:
                if not amount.isdigit() or int(amount) <= 0:
                    return await ctx.reply("❌ Montant invalide.")
                deposit_amount = int(amount)

            if deposit_amount > wallet:
                return await ctx.reply(f"❌ Tu n'as pas assez d'argent dans ton portefeuille. (Actuel : {wallet}💰)")

            # Vérifie la capacité de la trésorerie
            entreprise = get_entreprise(guild_id, user_id)
            if not entreprise:
                return await ctx.reply("❌ Entreprise non trouvée.")

            nouvelle_treso = entreprise["tresorerie"] + deposit_amount
            if nouvelle_treso > entreprise["tresorerie_max"]:
                return await ctx.reply(f"❌ La trésorerie de ton entreprise ne peut pas dépasser {entreprise['tresorerie_max']}💰. (Actuel : {entreprise['tresorerie']}💰)")

            # Effectue le dépôt
            update_wallet(guild_id, user_id, -deposit_amount)
            update_tresorerie_entreprise(guild_id, user_id, nouvelle_treso)
            
            embed = discord.Embed(
                title="✅ Dépôt effectué",
                description=f"Tu as déposé {deposit_amount}💰 dans la trésorerie de ton entreprise.",
                color=0x00FF00
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(f"❌ Une erreur s'est produite: {str(e)}")

    @entreprise.command(aliases=["with", "retirer"])
    async def withdraw(self, ctx, amount: Optional[str] = None):
        """Retire de l'argent de l'entreprise (propriétaire uniquement)"""
        try:
            guild_id = str(ctx.guild.id)
            user_id = str(ctx.author.id)
            
            # Vérification de permission
            if not is_entreprise_owner(guild_id, user_id):
                embed = discord.Embed(
                    title="❌ Permission refusée",
                    description="Seul le propriétaire peut retirer de l'argent de l'entreprise.",
                    color=0x000000
                )
                return await ctx.reply(embed=embed)

            # Vérification du montant
            if amount is None:
                return await ctx.reply("❌ Veuillez entrer une somme à retirer.")

            # Vérifie si l'utilisateur a assez de fonds
            tresorerie_actuelle = get_tresorerie_entreprise(guild_id, user_id)

            # Vérifie si la trésorerie est vide
            if tresorerie_actuelle == 0:
                embed = discord.Embed(
                    title="❌ Trésorerie vide",
                    description="Votre trésorerie est vide. Vous ne pouvez rien retirer pour le moment.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

            withdraw_amount = 0
            if amount.lower() == "all":
                withdraw_amount = tresorerie_actuelle
            else:
                if not amount.isdigit() or int(amount) <= 0:
                    return await ctx.reply("❌ Montant invalide.")
                withdraw_amount = int(amount)

            if withdraw_amount > tresorerie_actuelle:
                return await ctx.reply(f"❌ Vous n'avez pas assez d'argent dans votre trésorerie. (Actuel : {tresorerie_actuelle}💰)")

            # Effectue le retrait
            success = withdraw_entreprise_money(guild_id, user_id, withdraw_amount)
            if success:
                embed = discord.Embed(
                    title="✅ Retrait effectué",
                    description=f"Tu as retiré {withdraw_amount}💰 de la trésorerie de ton entreprise.",
                    color=0x00FF00
                )
                await ctx.reply(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Retrait impossible",
                    description=f"Une erreur s'est produite lors du retrait.",
                    color=0xFF0000
                )
                await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(f"❌ Une erreur s'est produite: {str(e)}")

    @entreprise.command(name="list")
    async def list_entreprises(self, ctx: commands.Context):
        if not ctx.guild:
            embed = discord.Embed(description="❌ Cette commande ne peut être utilisée que sur un serveur.", color=0x000000)
            await ctx.send(embed=embed)
            return

        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        entreprises = get_all_entreprises_by_guild(guild_id) or []

        if not entreprises:
            embed = discord.Embed(description="❌ Il n'y a aucune entreprise sur ce serveur.", color=0x000000)
            await ctx.send(embed=embed)
            return

        view = EntreprisePaginator(self.bot, guild_id, user_id, user_id)
        await ctx.send(embed=view.get_embed(), view=view)

    @entreprise.command(name="info")
    async def info(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        if not ctx.guild:
            embed = discord.Embed(description="❌ Cette commande ne peut être utilisée que sur un serveur.", color=0x000000)
            await ctx.send(embed=embed)
            return

        guild_id = str(ctx.guild.id)
        target = member or ctx.author
        target_id = str(target.id)
        user_id = str(ctx.author.id)

        entreprise = get_entreprise(guild_id, target_id)
        if not entreprise:
            embed = discord.Embed(description="❌ Cette personne n'a pas d'entreprise.", color=0x000000)
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="🏢 Informations sur l'entreprise", color=0x000000)
        view = MenuEntrepriseView(self.bot, guild_id, target_id, user_id)
        await ctx.send(embed=embed, view=view)

    @entreprise.command(name="delete")
    async def delete(self, ctx: commands.Context):
        if not ctx.guild:
            embed = discord.Embed(description="❌ Cette commande ne peut être utilisée que sur un serveur.", color=0x000000)
            await ctx.send(embed=embed)
            return

        guild_id = str(ctx.guild.id)
        owner_id = str(ctx.author.id)
        user_id = str(ctx.author.id)

        if not get_entreprise(guild_id, owner_id):
            embed = discord.Embed(description="❌ Tu n'as pas d'entreprise.", color=0x000000)
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="⚠️ Confirmation de suppression",
            description="Es-tu sûr de vouloir supprimer ton entreprise ?",
            color=0x000000
        )
        view = ConfirmDeleteEntrepriseView(self.bot, guild_id, owner_id, user_id)
        await ctx.send(embed=embed, view=view)

    @entreprise.command(name="leave")
    async def leave(self, ctx):
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        try:
            if is_employe(guild_id, user_id):
                if is_entreprise_owner(guild_id, user_id):
                    embed = discord.Embed(description="❌ Tu ne peux pas quitter ta propre entreprise. (utilise +entreprise)", color=0x000000)
                    await ctx.reply(embed=embed)
                    return
                else:
                    owner_id = get_entreprise_owner_id(guild_id, user_id)
                    if owner_id:
                        remove_employe(guild_id, owner_id, user_id)
                        embed = discord.Embed(description="🚪 Tu as bien quitté l'entreprise.", color=0x000000)
                        await ctx.reply(embed=embed)
                        return
                    else:
                        embed = discord.Embed(description="❌ Une erreur est survenue en récupérant les informations de l'entreprise.", color=0x000000)
                        await ctx.reply(embed=embed)
                        return
            else:
                embed = discord.Embed(description="❌ Tu n'es pas employé dans une entreprise.", color=0x000000)
                await ctx.reply(embed=embed)
                return
        except Exception as e:
            embed = discord.Embed(description="❌ Une erreur est survenue.", color=0x000000)
            await ctx.reply(embed=embed)

    @entreprise.command(name="create")
    async def create(self, ctx: commands.Context, *, nom: str):
        if not ctx.guild:
            await ctx.send("❌ Cette commande ne peut être utilisée que sur un serveur.")
            return

        guild_id = str(ctx.guild.id)
        owner_id = str(ctx.author.id)
        user_id = str(ctx.author.id)

        # Vérifier si l'utilisateur a déjà une entreprise
        if get_entreprise(guild_id, owner_id):
            embed = discord.Embed(description="❌ Tu as déjà une entreprise.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Vérifier si l'utilisateur est déjà employé
        if is_employe(guild_id, owner_id):
            embed = discord.Embed(description="❌ Tu es déjà employé dans une entreprise.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Vérifier si le nom est déjà pris
        if get_entreprise_by_name(guild_id, nom):
            embed = discord.Embed(description="❌ Une entreprise avec ce nom existe déjà.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Créer l'entreprise
        try:
            cost = 50000
            balances = get_wallet_bank(guild_id, owner_id)
            if balances["wallet"] < cost:
                embed = discord.Embed(description=f"❌ Tu n'as pas assez d'argent dans ton portefeuille pour créer une entreprise. Il te faut **{cost:,}** coins.", color=0x000000)
                await ctx.reply(embed=embed)
                return

            user_init(guild_id, owner_id)
            update_wallet(guild_id, owner_id, -cost)
            create_entreprise(guild_id, owner_id, nom)
            embed = discord.Embed(description=f"✅ Ton entreprise **{nom}** a été créée avec succès pour **{cost:,}** coins !\nLe solde initial de ton entreprise est de **0** 💰", color=0x000000)
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(description="❌ Une erreur est survenue lors de la création de l'entreprise.", color=0x000000)
            await ctx.reply(embed=embed)

    @entreprise.command(name="invite")
    async def invite(self, ctx: commands.Context, member: discord.Member):
        if not ctx.guild:
            await ctx.send("❌ Cette commande ne peut être utilisée que sur un serveur.")
            return

        guild_id = str(ctx.guild.id)
        owner_id = str(ctx.author.id)
        user_id = str(member.id)

        # Vérifier si l'auteur a une entreprise
        entreprise = get_entreprise(guild_id, owner_id)
        if not entreprise:
            embed = discord.Embed(description="❌ Tu n'as pas d'entreprise.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Vérifier si la personne invitée n'est pas déjà employée
        if is_employe(guild_id, user_id):
            embed = discord.Embed(description="❌ Cette personne est déjà employée dans une entreprise.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Vérifier si la personne invitée n'a pas déjà une entreprise
        if is_entreprise_owner(guild_id, user_id):
            embed = discord.Embed(description="❌ Cette personne possède déjà une entreprise.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Vérifier la capacité de l'entreprise
        employes = get_employes(guild_id, owner_id)
        buildings = get_entreprise_buildings(guild_id, owner_id)
        bureau = next((b for b in buildings if b["building_type"] == "bureau"), None)
        max_employes = 10 + (5 * bureau["level"] if bureau else 0)
        
        if len(employes) >= max_employes:
            embed = discord.Embed(description=f"❌ Ton entreprise est pleine ({len(employes)}/{max_employes} employés). Améliore ton Bureau pour avoir plus de place.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Envoyer l'invitation
        view = InviteEntrepriseView(self.bot, guild_id, owner_id, user_id)
        embed = discord.Embed(
            title="📨 Invitation à rejoindre une entreprise",
            description=f"Tu as été invité à rejoindre l'entreprise **{entreprise['nom']}** !",
            color=0x000000
        )
        await ctx.send(f"{member.mention}", embed=embed, view=view)

    @entreprise.command(name="join")
    async def join(self, ctx, *, nom_entreprise: str):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        # Vérifier si l'utilisateur n'est pas déjà employé
        if is_employe(guild_id, user_id):
            embed = discord.Embed(description="❌ Tu es déjà employé dans une entreprise.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Vérifier si l'utilisateur n'a pas déjà une entreprise
        if is_entreprise_owner(guild_id, user_id):
            embed = discord.Embed(description="❌ Tu possèdes déjà une entreprise.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Chercher l'entreprise
        entreprise = get_entreprise_by_name(guild_id, nom_entreprise)
        if not entreprise:
            embed = discord.Embed(description="❌ Cette entreprise n'existe pas.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        owner_id = entreprise["owner_id"]

        # Vérifier si l'entreprise est publique
        if entreprise["visibilite"] != "publique":
            embed = discord.Embed(description="❌ Cette entreprise est privée. Tu dois être invité pour la rejoindre.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Vérifier la capacité de l'entreprise
        employes = get_employes(guild_id, owner_id)
        buildings = get_entreprise_buildings(guild_id, owner_id)
        bureau = next((b for b in buildings if b["building_type"] == "bureau"), None)
        max_employes = 10 + (5 * bureau["level"] if bureau else 0)
        
        if len(employes) >= max_employes:
            embed = discord.Embed(description=f"❌ Cette entreprise est pleine ({len(employes)}/{max_employes} employés).", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Ajouter l'employé
        try:
            user_init(guild_id, user_id)
            add_employe(guild_id, owner_id, user_id)
            embed = discord.Embed(description=f"✅ Tu as rejoint l'entreprise **{entreprise['nom']}** !", color=0x000000)
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(description="❌ Une erreur est survenue lors de ton recrutement.", color=0x000000)
            await ctx.reply(embed=embed)

    @entreprise.command(name="repair")
    @commands.cooldown(1, 43200, commands.BucketType.user)
    async def repair(self, ctx):
        """Divise un cooldown actif par 2 (Nécessite un Atelier dans l'entreprise)"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        ent_owner_id = None
        if is_entreprise_owner(guild_id, user_id):
            ent_owner_id = user_id
        else:
            ent_owner_id = get_entreprise_owner_id(guild_id, user_id)

        if not ent_owner_id:
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply("❌ Tu dois faire partie d'une entreprise pour utiliser l'atelier.")

        buildings = get_entreprise_buildings(guild_id, ent_owner_id)
        atelier = next((b for b in buildings if b["building_type"] == "atelier"), None)
        if not atelier:
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply("❌ Ton entreprise ne possède pas d'Atelier.")

        # L'idée est de réduire les cooldowns système existants.
        # Par simplicité, on va appliquer un buff général si on ne peut pas éditer les cooldowns discord.ext directs.
        # Comme `get_work_cooldown` est en DB, on peut réduire celui-ci. Ou resetter un cooldown.
        from database import get_work_cooldown, update_work_cooldown
        last_work = get_work_cooldown(guild_id, user_id)
        if last_work:
            last_time = datetime.fromisoformat(last_work)
            now = datetime.now()
            # On recule le temps de 'last_work' pour simuler une réduction de cooldown
            diff = now - last_time
            if diff.total_seconds() < 3600:
                bonus = timedelta(minutes=15 * atelier["level"])
                new_last_work = last_time - bonus
                update_work_cooldown(guild_id, user_id, new_last_work.isoformat())
                return await ctx.reply(f"🛠️ **L'Atelier (Lv.{atelier['level']})** a réparé tes outils ! Ton prochain `+work` arrivera plus vite.")

        await ctx.reply("🛠️ Tu n'as pas de cooldowns que l'Atelier peut réparer pour l'instant.")
        ctx.command.reset_cooldown(ctx)

    @entreprise.command(name="contrat")
    async def contrat(self, ctx):
        """Accepter et gérer un gros contrat (Nécessite un Entrepôt)"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        ent_owner_id = None
        if is_entreprise_owner(guild_id, user_id):
            ent_owner_id = user_id
        else:
            ent_owner_id = get_entreprise_owner_id(guild_id, user_id)

        if not ent_owner_id:
            return await ctx.reply("❌ Tu dois faire partie d'une entreprise pour gérer les contrats.")

        buildings = get_entreprise_buildings(guild_id, ent_owner_id)
        entrepot = next((b for b in buildings if b["building_type"] == "entrepot"), None)
        if not entrepot:
            return await ctx.reply("❌ L'entreprise ne possède pas d'Entrepôt (Logistique requise).")

        from database import db
        import datetime
        
        ent = db.entreprises.find_one({"guild_id": guild_id, "owner_id": ent_owner_id})
        contract = ent.get("active_contract")

        # Afficher le contrat en cours
        if contract:
            expiry = datetime.datetime.fromisoformat(contract["expires_at"])
            now = datetime.datetime.now()
            
            if now > expiry:
                # Contrat expiré, échec
                db.entreprises.update_one(
                    {"guild_id": guild_id, "owner_id": ent_owner_id},
                    {"$unset": {"active_contract": ""}}
                )
                embed = discord.Embed(
                    title="🚚 Contrat expiré",
                    description="Le temps est écoulé ! L'équipe n'a pas pu livrer la commande à temps.",
                    color=discord.Color.red()
                )
                return await ctx.reply(embed=embed)
                
            # Vérifier si l'objectif est atteint
            if contract["progress"] >= contract["goal"]:
                # Succès !
                reward = contract["reward"]
                nouvelle_treso = ent["tresorerie"] + reward
                # Limite max
                if nouvelle_treso > ent["tresorerie_max"]: nouvelle_treso = ent["tresorerie_max"]
                
                db.entreprises.update_one(
                    {"guild_id": guild_id, "owner_id": ent_owner_id},
                    {
                        "$set": {"tresorerie": nouvelle_treso},
                        "$unset": {"active_contract": ""}
                    }
                )
                embed = discord.Embed(
                    title="🎉 CONTRAT TERMINÉ !",
                    description=f"Félicitations à toute l'équipe ! L'entreprise a honoré sa commande et empoche un bonus de **{reward:,} coins** !",
                    color=0x00FF00
                )
                return await ctx.reply(embed=embed)
                
            # Afficher l'état
            progress_bar = ""
            perc = contract["progress"] / contract["goal"]
            filled = int(perc * 10)
            progress_bar = "🟩" * filled + "⬛" * (10 - filled)
            
            embed = discord.Embed(
                title="🚚 Contrat d'Exportation en cours",
                description="Toute l'équipe doit faire `+work` pour remplir cet objectif logistique commun !",
                color=0x000000
            )
            embed.add_field(name="Objectif", value=f"{progress_bar} ({contract['progress']}/{contract['goal']} Works)", inline=False)
            embed.add_field(name="Récompense", value=f"**{contract['reward']:,} coins** pour l'entreprise", inline=True)
            embed.add_field(name="Temps restant", value=f"<t:{int(expiry.timestamp())}:R>", inline=True)
            return await ctx.reply(embed=embed)

        # Créer un nouveau contrat (Seul le patron/manager)
        if not has_permission(guild_id, user_id, "gerer_employes") and ent_owner_id != user_id:
            return await ctx.reply("❌ Seul le patron ou un manager peut accepter un nouveau contrat.")

        # Calculer difficulté et récompense selon le niveau de l'entrepôt
        import random
        lvl = entrepot["level"]
        
        # Lv1: 15 works / Lv5: 55 works
        goal = 10 + (10 * lvl) + random.randint(-5, 5) 
        
        # Récompense massive (ex: 5000 pour lv1, 25000 pour lv5)
        reward = goal * (300 + (100 * lvl)) 
        
        expires_at = datetime.datetime.now() + datetime.timedelta(hours=24)
        
        new_contract = {
            "goal": goal,
            "progress": 0,
            "reward": reward,
            "expires_at": expires_at.isoformat()
        }
        
        db.entreprises.update_one(
            {"guild_id": guild_id, "owner_id": ent_owner_id},
            {"$set": {"active_contract": new_contract}}
        )
        
        embed = discord.Embed(
            title="🚚 NOUVEAU CONTRAT ACCEPTÉ !",
            description=f"Ton Entrepôt niveau {lvl} a décroché une grosse commande !",
            color=0x00BFFF
        )
        embed.add_field(name="Objectif", value=f"Toute l'équipe doit réaliser un total de **{goal} commandes `+work`** en moins de 24 heures.", inline=False)
        embed.add_field(name="Récompense", value=f"**{reward:,} coins** versés dans la trésorerie.", inline=False)
        embed.set_footer(text="Faites +entreprise contrat pour suivre la progression !")
        
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(EntrepriseCog(bot))
