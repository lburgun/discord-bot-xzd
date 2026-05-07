import discord
from discord.ext import commands
from discord import ui
from database import user_init, get_investissements, get_wallet_bank, update_investissements, update_bank, get_user_wallet
from datetime import datetime, timedelta

INVESTMENTS_DATA = {
    "stande-de-limonade": {"price": 100, "duration": 1, "reward": 350, "description": "Vente de limonade", "emoji": "🍋"},
    "tableaux": {"price": 500, "duration": 2, "reward": 850, "description": "Tableaux modernes", "emoji": "🖼️"},
    "voiture": {"price": 1000, "duration": 4, "reward": 4000, "description": "Rénovation ancienne voiture", "emoji": "🚗"},
    "garage": {"price": 20000, "duration": 7, "reward": 30000, "description": "Louez des places pour voitures.", "emoji": "🅿️"},
    "kiosque": {"price": 10000, "duration": 5, "reward": 16000, "description": "Revenus journaliers stables.", "emoji": "🏪"},
    "ferme": {"price": 25000, "duration": 7, "reward": 37500, "description": "Vente d'œufs bio.", "emoji": "🥚"},
    "taxi": {"price": 30000, "duration": 6, "reward": 45000, "description": "Transports urbains rentables.", "emoji": "🚕"},
    "magasin": {"price": 50000, "duration": 10, "reward": 80000, "description": "Profits de la vente de produits.", "emoji": "🛍️"},
    "studio": {"price": 75000, "duration": 10, "reward": 120000, "description": "Ventes de streams et albums.", "emoji": "🎙️"},
    "mine": {"price": 100000, "duration": 14, "reward": 180000, "description": "Extraction de ressources rares.", "emoji": "⛏️"},
    "centre-commerciale": {"price": 500000, "duration": 20, "reward": 890000, "description": "Construction commerces", "emoji": "🏢"},
    "usine-nucleaire": {"price": 2000000, "duration": 32, "reward": 10000000, "description": "Construction usine nucléaire", "emoji": "☢️"}
}

class InvestSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{name.replace('-', ' ').capitalize()}",
                description=f"{info['price']:,} coins - Durée: {info['duration']}j",
                emoji=info['emoji'],
                value=name
            ) for name, info in INVESTMENTS_DATA.items()
        ]
        super().__init__(placeholder="Choisissez un investissement...", options=options)

    async def callback(self, interaction: discord.Interaction):
        guild_id, user_id = str(interaction.guild_id), str(interaction.user.id)
        choice = self.values[0]
        inv_info = INVESTMENTS_DATA[choice]
        
        # Vérifier si l'utilisateur a déjà un investissement
        current_inv = get_investissements(guild_id, user_id)
        if current_inv and current_inv.get("duration", 0) > 0:
            await interaction.response.send_message("⚠️ Tu as déjà un investissement en cours !", ephemeral=True)
            return

        # Vérifier le solde (On prend dans la banque pour l'investissement)
        balances = get_wallet_bank(guild_id, user_id)
        bank_balance = int(balances.get("bank", 0))

        if bank_balance < inv_info["price"]:
            await interaction.response.send_message(f"💸 Tu n'as pas assez d'argent en banque ! Il te manque {inv_info['price'] - bank_balance:,} coins.", ephemeral=True)
            return

        # Lancer l'investissement
        update_bank(guild_id, user_id, -inv_info["price"])
        
        new_inv = {
            "nom_invest": choice,
            "duration": inv_info["duration"],
            "reward": inv_info["reward"],
            "start": datetime.utcnow().isoformat(),
            "end": (datetime.utcnow() + timedelta(days=inv_info["duration"])).isoformat()
        }
        update_investissements(guild_id, user_id, new_inv)

        embed_success = discord.Embed(
            title="✅ Investissement lancé !",
            description=f"Tu as investi dans **{choice.replace('-', ' ').capitalize()}**.\n"
                        f"💰 Coût : {inv_info['price']:,} coins (prélevés de ta banque)\n"
                        f"🎁 Gain prévu : **{inv_info['reward']:,} coins**\n"
                        f"⏳ Durée : {inv_info['duration']} jours",
            color=0x00FF00
        )
        # 1. On envoie la confirmation (Public)
        await interaction.response.send_message(embed=embed_success)
        
        # 2. On met à jour le message d'origine (le centre d'investissement)
        await self.view.update_main_message(interaction, from_callback=True)

class ClaimButton(ui.Button):
    def __init__(self, label, style, disabled=False):
        super().__init__(label=label, style=style, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        guild_id, user_id = str(interaction.guild_id), str(interaction.user.id)
        data = get_investissements(guild_id, user_id)

        if not data or not data.get("end"):
            await interaction.response.send_message("❌ Aucun investissement trouvé.", ephemeral=True)
            return

        now = datetime.utcnow()
        end = datetime.fromisoformat(data["end"])

        if now < end:
            await interaction.response.send_message("⏳ L'investissement n'est pas encore terminé.", ephemeral=True)
            return

        reward = int(data["reward"])
        update_bank(guild_id, user_id, reward)
        update_investissements(guild_id, user_id, {})
        
        embed_claim = discord.Embed(
            title="📥 Gains récupérés !",
            description=f"Félicitations ! Tu as reçu **{reward:,} coins** sur ton compte bancaire.",
            color=0x00FF00
        )
        # On envoie la confirmation
        await interaction.response.send_message(embed=embed_claim)
        # On met à jour le centre
        await self.view.update_main_message(interaction, from_callback=True)

class StatusButton(ui.Button):
    def __init__(self):
        super().__init__(label="📊 Mon Statut", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await self.view.update_main_message(interaction, show_status=True)

class InvestView(ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.add_item(InvestSelect())
        self.add_item(StatusButton())

    async def update_main_message(self, interaction: discord.Interaction, show_status=False):
        guild_id, user_id = str(interaction.guild_id), str(self.user_id)
        data = get_investissements(guild_id, user_id)
        
        embed = discord.Embed(title="📈 Centre d'Investissement", color=0x000000)
        
        if show_status and data and data.get("duration", 0) > 0:
            start = datetime.fromisoformat(data["start"])
            end = datetime.fromisoformat(data["end"])
            now = datetime.utcnow()
            
            finished = now >= end
            timestamp = int(end.timestamp())
            
            # Calcul jours restants
            days_passed = (now - start).days
            total_days = data["duration"]
            
            embed.description = (
                f"👤 **Investissement en cours :** {data['nom_invest'].replace('-', ' ').capitalize()}\n"
                f"📊 Progression : {min(days_passed, total_days)}/{total_days} jours\n"
                f"🎁 Récompense : **{data['reward']:,} coins**\n"
                f"{'✅ **Prêt à être récupéré !**' if finished else f'⏳ Disponible <t:{timestamp}:R>'}"
            )
            
            # Ajouter bouton claim si fini
            new_view = ui.View(timeout=180)
            new_view.add_item(InvestSelect())
            new_view.add_item(ClaimButton(
                label="📥 Récupérer les gains" if finished else "⏳ En cours...", 
                style=discord.ButtonStyle.green if finished else discord.ButtonStyle.gray,
                disabled=not finished
            ))
            # On remplace l'affichage
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=new_view)
            else:
                await interaction.response.edit_message(embed=embed, view=new_view)
            return

        # Affichage par défaut (Liste)
        embed.description = "Sélectionnez un projet dans le menu pour investir vos coins."
        for name, info in list(INVESTMENTS_DATA.items())[:5]: # Top 5 pour l'exemple
            embed.add_field(
                name=f"{info['emoji']} {name.replace('-', ' ').capitalize()}",
                value=f"💰 Prix: {info['price']:,}\n🎁 Gain: {info['reward']:,}\n⏳ Durée: {info['duration']}j",
                inline=True
            )
        embed.set_footer(text="Utilisez le menu déroulant pour voir tous les projets.")
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

class Invest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="invest")
    async def invest(self, ctx):
        """Ouvre le menu d'investissement interactif"""
        user_init(ctx.guild.id, ctx.author.id)
        
        embed = discord.Embed(
            title="📈 Centre d'Investissement",
            description="Bienvenue au centre d'investissement ! Sélectionnez un projet ci-dessous pour faire fructifier votre argent.\n\n"
                        "💡 *L'argent est prélevé directement de votre compte bancaire.*",
            color=0x000000
        )
        
        # Liste simplifiée dans l'embed initial
        for name, info in list(INVESTMENTS_DATA.items())[:6]:
            embed.add_field(
                name=f"{info['emoji']} {name.replace('-', ' ').capitalize()}",
                value=f"💰 {info['price']:,} 💰\n🎁 {info['reward']:,} 💰\n⏳ {info['duration']}j",
                inline=True
            )
            
        view = InvestView(self.bot, ctx.author.id)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Invest(bot))
