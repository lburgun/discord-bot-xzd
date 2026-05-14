import discord
from discord.ext import commands
from discord import ui
from typing import Optional

class HelpSelect(ui.Select):
    def __init__(self, bot, ctx):
        self.bot = bot
        self.ctx = ctx
        options = [
            discord.SelectOption(label="Accueil", description="Retour au menu principal", emoji="🏠", value="Accueil"),
            discord.SelectOption(label="Économie", description="Gagner et dépenser des coins", emoji="💰", value="Économie"),
            discord.SelectOption(label="Entreprise", description="Gérer ton empire commercial", emoji="🏢", value="Entreprise"),
            discord.SelectOption(label="Criminel", description="Vols, braquages et police", emoji="🦹", value="Criminel"),
            discord.SelectOption(label="Jeux & Fun", description="Divertissement et Mini-jeux", emoji="🎮", value="Jeux & Fun"),
            discord.SelectOption(label="Modération", description="Commandes pour les modérateurs", emoji="🛡️", value="Modération"),
            discord.SelectOption(label="Configuration", description="Paramètres et Utilitaires", emoji="⚙️", value="Configuration")
        ]
        super().__init__(placeholder="Choisissez une catégorie...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Vérification que c'est bien l'auteur de la commande
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Tu ne peux pas utiliser ce menu.", ephemeral=True)

        selection = self.values[0]
        embed = discord.Embed(color=0x000000)

        if selection == "Accueil":
            embed.title = "📜 Guide des Commandes"
            embed.description = (
                "Bienvenue dans le menu d'aide ! Utilisez le menu déroulant ci-dessous "
                "pour naviguer entre les différentes catégories de commandes."
            )
            embed.add_field(name="🌐 Catégories", value="• 💰 **Économie**\n• 🏢 **Entreprise**\n• 🦹 **Criminel**\n• 🎮 **Jeux & Fun**\n• 🛡️ **Modération**\n• ⚙️ **Configuration**", inline=False)
        
        elif selection == "Économie":
            embed.title = "💰 Commandes d'Économie"
            embed.description = (
                "`+bal [@user]` : Voir son solde ou celui d'un autre joueur\n"
                "`+daily` : Récupérer sa récompense quotidienne\n"
                "`+work` : Travailler pour gagner de l'argent\n"
                "`+job` : Gérer ses métiers (Menu interactif)\n"
                "`+pay <@user> <somme>` : Transférer de l'argent à un joueur\n"
                "`+deposit <somme>` : Déposer de l'argent en banque\n"
                "`+with <somme>` : Retirer de l'argent de la banque\n"
                "`+shop` : Boutique d'objets utilitaires\n"
                "`+catalogue` : Catalogue pour acheter des objets (Véhicules, Propriétés...)\n"
                "`+inventory` : Voir ton inventaire complet\n"
                "`+marketplace` : Marché entre joueurs\n"
                "`+invest` : Investir son argent pour des profits à long terme\n"
                "`+miner` : Miner des ressources (nécessite un Wagon)\n"
                "`+leaderboard` : Classement des joueurs les plus riches\n"
                "`+beg` : Mendier de l'argent\n"
            )

        elif selection == "Entreprise":
            embed.title = "🏢 Commandes d'Entreprise"
            embed.description = (
                "`+entreprise` : Menu principal de ton entreprise\n"
                "`+entreprise create <nom>` : Créer une nouvelle entreprise\n"
                "`+entreprise invite <@user>` : Inviter quelqu'un dans ton entreprise\n"
                "`+entreprise join <nom>` : Rejoindre une entreprise publique\n"
                "`+entreprise leave` : Quitter ton entreprise actuelle\n"
                "`+entreprise info [@user]` : Voir les infos d'une entreprise\n"
                "`+entreprise list` : Liste des entreprises du serveur\n"
                "`+entreprise deposit <somme>` : Déposer de l'argent dans la trésorerie\n"
                "`+entreprise withdraw <somme>` : Retirer de l'argent de la trésorerie\n"
                "`+entreprise delete` : Supprimer ton entreprise (Action irréversible)"
            )

        elif selection == "Criminel":
            embed.title = "🦹 Vols, Braquages & Police"
            embed.description = (
                "**Voleur :**\n"
                "`+rob <@user>` : Tenter de voler un joueur\n"
                "`+scout <@user>` : Espionner les défenses d'un joueur (Voleur Niv.3)\n"
                "`+heist <@user>` : Braquer la banque d'un joueur (Braqueur Niv.4)\n"
                "\n**Police :**\n"
                "`+police` : Afficher le commissariat\n"
                "`+bounty add <@user> <somme>` : Placer une prime sur un joueur\n"
                "`+bounty list` : Voir les criminels recherchés\n"
                "`+arrest <@user>` : Tenter d'arrêter un criminel recherché\n"
            )

        elif selection == "Jeux & Fun":
            embed.title = "🎮 Jeux & Divertissement"
            embed.description = (
                "`+blackjack <mise>` : Jouer au Blackjack\n"
                "`+roulette <mise>` : Jouer à la Roulette\n"
                "`+slot <mise>` : Jouer à la Machine à sous\n"
                "`+rlr <mise>` : Jouer à la Roulette Russe\n"
                "`+duel <mise>` : Défier un autre joueur en duel mortel\n"
                "`+avion <mise>` : Jouer au jeu du Crash/Avion\n"
                "`+mine <mise>` : Jouer au jeu des Mines\n"
                "`+valorant` : Trouver des joueurs pour Valorant\n"
            )

        elif selection == "Modération":
            embed.title = "🛡️ Commandes de Modération"
            embed.description = (
                "`+kick <@user> [raison]` : Expulser un membre\n"
                "`+ban <@user> [raison]` : Bannir un membre\n"
                "`+mute <@user> <durée> [raison]` : Réduire au silence (ex: 1h, 1d)\n"
                "`+unmute <@user>` : Lever une sanction de silence\n"
                "`+warn <@user> <raison>` : Avertir un membre\n"
                "`+warnings <@user>` : Voir les avertissements d'un membre\n"
                "`+clearwarnings <@user>` : Effacer les avertissements d'un membre\n"
                "`+lock` / `+unlock` : Verrouiller ou déverrouiller un salon\n"
                "`+slowmode <durée>` : Activer le mode lent (ex: 5s, off)\n"
                "`+clear [nombre]` : Supprimer des messages en masse\n"
                "`+userinfo [@user]` : Voir les infos détaillées d'un membre\n"
                "`+addmoney <@user> <somme>` : Donner de l'argent à un joueur (Admin)\n"
                "`+eco` : Activer/Désactiver l'économie du serveur (Owner)\n"
                "`+nuke` : Réinitialiser le salon actuel (Admin)\n"
            )

        elif selection == "Configuration":
            embed.title = "⚙️ Configuration & Utilitaires"
            embed.description = (
                "`+config_automod` : Gérer l'anti-spam, anti-invite et mots interdits\n"
                "`+config_welcome <salon> <message>` : Configurer le message de bienvenue\n"
                "`+config_welcome_image <url>` : Définir l'image de bienvenue\n"
                "`+config_leave <salon> <message>` : Configurer le message d'au revoir\n"
                "`+badwords_list` : Voir la liste des mots interdits\n"
                "`+add_badword <mot>` : Ajouter un mot à la liste noire\n"
                "`+remove_badword <mot>` : Retirer un mot de la liste noire\n"
                "`+setup_captcha <salon> <rôle>` : Configurer la vérification Captcha\n"
                "`+setup_tickets <catégorie>` : Configurer le système de tickets\n"
                "`+setup_voice <salon>` : Configurer les salons vocaux temporaires\n"
                "`+command_config` : Gérer les permissions personnalisées des commandes\n"
                "`+send_ticket_panel` : Envoyer le panel de création de tickets\n"
                "`+send_captcha_panel` : Envoyer le panel de vérification Captcha\n"
                "`+backup` : Créer une sauvegarde complète du serveur\n"
                "`+phone` : Lancer le téléphone virtuel\n"
            )

        embed.set_footer(text=f"Préfixe : + | Utilisateur : {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(ui.View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=120)
        self.add_item(HelpSelect(bot, ctx))

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help(self, ctx):
        """Affiche le menu d'aide interactif"""
        embed = discord.Embed(
            title="📜 Guide des Commandes",
            description=(
                "Bienvenue dans le menu d'aide ! Utilisez le menu déroulant ci-dessous "
                "pour naviguer entre les différentes catégories de commandes."
            ),
            color=0x000000
        )
        embed.add_field(name="🌐 Catégories", value="• 💰 **Économie**\n• 🏢 **Entreprise**\n• 🦹 **Criminel**\n• 🎮 **Jeux & Fun**\n• 🛡️ **Modération**\n• ⚙️ **Configuration**", inline=False)
        embed.set_footer(text=f"Utilisez le menu ci-dessous | Préfixe : +")
        
        await ctx.reply(embed=embed, view=HelpView(self.bot, ctx))

async def setup(bot):
    await bot.add_cog(Help(bot))
