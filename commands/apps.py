import discord
from discord.ext import commands
from database import execute_query, fetch_one, fetch_all
from datetime import datetime, timedelta
import json

# Constants
GROW_TIME = {
    "basic": 1,
    "quality": 1.5,
    "premium": 2
}

def format_price(price: float | int) -> str:
    """Formate un montant en texte lisible"""
    return f"{int(price):,}".replace(",", " ") + " coins"

class Apps(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def calc(self, ctx, montant: float, prix_achat: float, prix_vente: float):
        """Calculatrice de profit"""
        # Vérifier si l'utilisateur a un téléphone
        has_phone = fetch_one("""
            SELECT 1 FROM user_items 
            WHERE user_id = ? AND item_name = 'Telephone'
        """, (ctx.author.id,))

        if not has_phone:
            await ctx.send("❌ Vous avez besoin d'un téléphone pour utiliser la calculatrice ! Utilisez +buy pour en acheter un.")
            return

        cout_total = montant * prix_achat
        revenu_total = montant * prix_vente
        profit = revenu_total - cout_total
        roi = (profit / cout_total) * 100 if cout_total > 0 else 0

        embed = discord.Embed(
            title="🧮 Calculatrice de profit",
            description="Résultats de votre calcul",
            color=0x00FF00
        )

        embed.add_field(
            name="📊 Détails",
            value=f"Quantité: {montant}\n"
                  f"Prix d'achat: {format_price(prix_achat)}\n"
                  f"Prix de vente: {format_price(prix_vente)}",
            inline=False
        )

        embed.add_field(
            name="💰 Résultats",
            value=f"Coût total: {format_price(cout_total)}\n"
                  f"Revenu total: {format_price(revenu_total)}\n"
                  f"Profit: {'+' if profit >= 0 else ''}{format_price(profit)}\n"
                  f"ROI: {roi:.1f}%",
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command()
    async def timer(self, ctx, *, crop_name: str | None = None):
        """Voir les timers de vos cultures"""
        # Vérifier si l'utilisateur a un téléphone
        has_phone = fetch_one("""
            SELECT 1 FROM user_items 
            WHERE user_id = ? AND item_name = 'Telephone'
        """, (ctx.author.id,))

        if not has_phone:
            await ctx.send("❌ Vous avez besoin d'un téléphone pour voir les timers ! Utilisez +buy pour en acheter un.")
            return

        # Récupérer les cultures
        if crop_name:
            crops = fetch_all("""
                SELECT crop_type, planted_at, growth_stage
                FROM dealer_crops
                WHERE user_id = ? AND crop_type = ?
            """, (ctx.author.id, crop_name))
        else:
            crops = fetch_all("""
                SELECT crop_type, planted_at, growth_stage
                FROM dealer_crops
                WHERE user_id = ?
            """, (ctx.author.id,))

        if not crops:
            await ctx.send("❌ Vous n'avez pas de cultures en cours.")
            return

        embed = discord.Embed(
            title="⏲️ Timers de culture",
            description="État de vos plantations",
            color=0x00FF00
        )

        now = datetime.now()
        for crop_type, planted_at, growth_stage in crops:
            if not planted_at:
                continue

            planted_date = datetime.fromtimestamp(planted_at)
            grow_days = GROW_TIME.get(crop_type, 1)  # Default to 1 day if crop_type not found
            harvest_date = planted_date + timedelta(days=grow_days)
            remaining = harvest_date - now

            if remaining.total_seconds() > 0:
                days = remaining.days
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                
                time_text = []
                if days > 0:
                    time_text.append(f"{days}j")
                if hours > 0:
                    time_text.append(f"{hours}h")
                time_text.append(f"{minutes}m")
                
                status = " ".join(time_text)
            else:
                status = "Prêt à récolter! 🌾"

            progress = min(int((growth_stage / 3) * 10), 10)
            progress_bar = "🟩" * progress + "⬜" * (10 - progress)

            embed.add_field(
                name=f"{crop_type}",
                value=f"Temps restant: {status}\n"
                      f"Progression: {progress_bar}",
                inline=False
            )

            # Ajouter une notification si prêt à récolter
            if remaining.total_seconds() <= 0:
                notification = {
                    "type": "CROP_READY",
                    "crop_type": crop_type
                }

                execute_query("""
                    INSERT INTO user_notifications (user_id, type, data, timestamp)
                    VALUES (?, ?, ?, strftime('%s', 'now'))
                """, (ctx.author.id, "CROP_READY", json.dumps(notification)))

        await ctx.send(embed=embed)

    @commands.command()
    async def stats(self, ctx):
        """Voir vos statistiques"""
        # Vérifier si l'utilisateur a un téléphone
        has_phone = fetch_one("""
            SELECT 1 FROM user_items 
            WHERE user_id = ? AND item_name = 'Telephone'
        """, (ctx.author.id,))

        if not has_phone:
            await ctx.send("❌ Vous avez besoin d'un téléphone pour voir vos stats ! Utilisez +buy pour en acheter un.")
            return

        # Récupérer les statistiques avec des valeurs par défaut
        plants_count = fetch_one("""
            SELECT COUNT(*) FROM dealer_crops 
            WHERE user_id = ?
        """, (ctx.author.id,))
        plants = plants_count[0] if plants_count else 0

        listings_count = fetch_one("""
            SELECT COUNT(*) FROM marketplace_listings 
            WHERE seller_id = ?
        """, (ctx.author.id,))
        listings = listings_count[0] if listings_count else 0



        embed = discord.Embed(
            title=f"📊 Statistiques de {ctx.author.display_name}",
            description="Vos statistiques personnelles",
            color=0x00FF00
        )

        embed.add_field(
            name="🌱 Agriculture",
            value=f"Plantes actives: {plants}",
            inline=True
        )

        embed.add_field(
            name="📋 Activités",
            value=f"Offres en cours: {listings}",
            inline=True
        )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Apps(bot)) 