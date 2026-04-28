import discord
from discord.ext import commands
from discord import ui

class HelpSelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Accueil", description="Retour au menu principal", emoji="🏠"),
            discord.SelectOption(label="Économie", description="Gagner et dépenser des coins", emoji="💰"),
            discord.SelectOption(label="Jeux & Fun", description="Divertissement et Valorant", emoji="🎮"),
            discord.SelectOption(label="Modération", description="Commandes pour les modérateurs", emoji="🛡️"),
            discord.SelectOption(label="Configuration", description="Paramètres et Utilitaires", emoji="⚙️")
        ]
        super().__init__(placeholder="Choisissez une catégorie...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selection = self.values[0]
        embed = discord.Embed(color=0x2b2d31) # Couleur sombre moderne

        if selection == "Accueil":
            embed.title = "📜 Guide des Commandes"
            embed.description = (
                "Bienvenue dans le menu d'aide ! Utilisez le menu déroulant ci-dessous "
                "pour naviguer entre les différentes catégories de commandes."
            )
            embed.add_field(name="🌐 Categories", value="• 💰 **Économie**\n• 🎮 **Jeux & Fun**\n• 🛡️ **Modération**\n• ⚙️ **Configuration**", inline=False)
        
        elif selection == "Économie":
            embed.title = "💰 Commandes d'Économie"
            embed.description = (
                "`+bal` : Voir ton solde (Portefeuille/Banque)\n"
                "`+beg` : Mendier quelques coins\n"
                "`+daily` : Récupérer ta récompense journalière\n"
                "`+work` : Travailler pour gagner un salaire\n"
                "`+pay <@user> <somme>` : Transférer de l'argent\n"
                "`+shop` : Parcourir la boutique\n"
                "`+buy <item>` : Acheter un objet\n"
                "`+inventory` : Voir tes objets\n"
                "`+job` : Gérer ton métier (+job info, +job promote)\n"
                "`+entreprise` : Gérer ton empire commercial\n"
                "`+leaderboard` : Voir les plus riches du serveur"
            )

        elif selection == "Jeux & Fun":
            embed.title = "🎮 Jeux & Divertissement"
            embed.description = (
                "`+blackjack <somme>` : Tenter de battre la banque\n"
                "`+roulette <somme> <couleur/nombre>` : Miser à la roulette\n"
                "`+rouletteRusse` : Un jeu dangereux...\n"
                "`+slot <somme>` : Tenter le jackpot à la machine à sous\n"
                "`+duel <@user> <somme>` : Défier un autre joueur\n"
                "`+valorant` : Obtenir un agent Valorant aléatoire"
            )

        elif selection == "Modération":
            embed.title = "🛡️ Commandes de Modération"
            embed.description = (
                "`+kick <@user> [raison]` : Expulser un membre\n"
                "`+ban <@user> [raison]` : Bannir un membre\n"
                "`+warn <@user> <raison>` : Donner un avertissement\n"
                "`+warnings <@user>` : Liste des avertissements d'un membre\n"
                "`+clearwarnings <@user>` : Reset les avertissements\n"
                "`+clear [nombre]` : Supprimer les messages (Admin)\n"
                "`+addmoney <@user> <somme>` : Ajouter de l'argent (Admin)\n"
                "`+eco` : Activer/Désactiver l'économie (Admin)"
            )

        elif selection == "Configuration":
            embed.title = "⚙️ Configuration & Utilitaires"
            embed.description = (
                "`+setup_captcha <#salon> <@role>` : Configurer la sécurité\n"
                "`+send_captcha_panel` : Envoyer le bouton de vérification\n"
                "`+setup_tickets <catégorie>` : Configurer le support\n"
                "`+ticket_roles` : Gérer les rôles support (Add/Remove)\n"
                "`+send_ticket_panel` : Envoyer le panel de tickets\n"
                "`+setup_welcome <#salon> <message>` : Configurer la bienvenue\n"
                "`+setup_welcome_image <url>` : Image du message de bienvenue\n"
                "`+setup_leave <#salon> <message>` : Configurer les départs\n"
                "`+command_config` : Gérer les accès aux commandes (Interactif)\n"
                "`+backup` : Sauvegarder/Restaurer la structure du serveur\n"
                "`+setup_voice <#vocal>` : Configurer les vocaux temporaires\n"
                "`+vc_lock` / `+vc_unlock` : Verrouiller/Ouvrir ton vocal privé\n"
                "`+lfg_create` : Créer un panel de recherche de groupe"
            )

        embed.set_footer(text=f"Préfixe : + | Utilisateur : {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=120)
        self.add_item(HelpSelect(bot))

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
            color=0x2b2d31
        )
        embed.add_field(name="🌐 Catégories", value="• 💰 **Économie**\n• 🎮 **Jeux & Fun**\n• 🛡️ **Modération**\n• ⚙️ **Configuration**", inline=False)
        embed.set_footer(text=f"Utilisez le menu ci-dessous | Préfixe : +")
        
        await ctx.reply(embed=embed, view=HelpView(self.bot))

async def setup(bot):
    await bot.add_cog(Help(bot))
