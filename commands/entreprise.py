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
    get_wallet_bank, update_bank, reorganize_building_ids
)
from utils.entreprise_views import MenuEntrepriseView, InviteEntrepriseView, EntreprisePaginator, ConfirmDeleteEntrepriseView
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union, Sequence
from discord.ext.commands import Context


def message_send(ctx: Context, embed: discord.Embed, bot: commands.Bot):
    bot.loop.create_task(ctx.reply(embed=embed))


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

        embed = discord.Embed(title="📋 Liste des entreprises", color=0x000000)
        view = EntreprisePaginator(self.bot, guild_id, user_id, user_id)
        await ctx.send(embed=embed, view=view)

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
            user_init(guild_id, owner_id)
            create_entreprise(guild_id, owner_id, nom)
            embed = discord.Embed(description=f"✅ Ton entreprise **{nom}** a été créée avec succès !", color=0x000000)
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
        guild_id = ctx.guild.id
        user_id = ctx.author.id

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

        # Vérifier si l'entreprise est publique
        if entreprise["visibilite"] != "publique":
            embed = discord.Embed(description="❌ Cette entreprise est privée. Tu dois être invité pour la rejoindre.", color=0x000000)
            await ctx.reply(embed=embed)
            return

        # Ajouter l'employé
        try:
            user_init(guild_id, user_id)
            add_employe(guild_id, entreprise["owner_id"], user_id)
            embed = discord.Embed(description=f"✅ Tu as rejoint l'entreprise **{entreprise['nom']}** !", color=0x000000)
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(description="❌ Une erreur est survenue lors de ton recrutement.", color=0x000000)
            await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(EntrepriseCog(bot))
