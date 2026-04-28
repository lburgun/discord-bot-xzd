import discord
from discord.ext import commands
from database import execute_query, fetch_one, fetch_all, get_inventaire
from datetime import datetime, timedelta
from .catalogue import catalogue_items, category_emojis
import json

def format_price(price: float | int) -> str:
    """Formate un montant en texte lisible"""
    return f"{int(price):,}".replace(",", " ") + " coins"

class PlantSelect(discord.ui.Select):
    def __init__(self):
        self.plant_types = [
            {"name": "Plante qualité inférieure", "price": 1000, "water_days": 2, "total_days": 4},
            {"name": "Plante qualité classique", "price": 2500, "water_days": 3, "total_days": 5},
            {"name": "Plante qualité bonne", "price": 5000, "water_days": 4, "total_days": 6},
            {"name": "Plante qualité excellente", "price": 10000, "water_days": 5, "total_days": 7}
        ]
        options = [
            discord.SelectOption(
                label=plant["name"],
                value=plant["name"],
                emoji="🌱",
                description=f"Prix: {format_price(plant['price'])} - Entretien: {plant['water_days']} jours"
            ) for plant in self.plant_types
        ]
        super().__init__(
            placeholder="Choisissez une plante à planter",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        plant_name = self.values[0]
        plant_info = next(p for p in self.plant_types if p["name"] == plant_name)
        
        # Vérifier si l'utilisateur a des bouteilles d'eau
        water_bottles = fetch_one("""
            SELECT quantity FROM user_items 
            WHERE user_id = ? AND item_name = 'Bouteille d''eau'
        """, (interaction.user.id,))

        if not water_bottles or water_bottles[0] < 1:
            embed = discord.Embed(
                title="❌ Pas de bouteille d'eau",
                description="Vous avez besoin d'une bouteille d'eau pour planter ! Achetez-en dans le shop.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Vérifier si l'utilisateur a déjà cette plante
        existing_plant = fetch_one("""
            SELECT 1 FROM user_plants 
            WHERE user_id = ? AND plant_type = ?
        """, (interaction.user.id, plant_name))

        if existing_plant:
            embed = discord.Embed(
                title="❌ Plante existante",
                description="Vous avez déjà une plante de ce type en cours de croissance.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Vérifier si l'utilisateur a assez d'argent
        wallet = fetch_one("SELECT wallet FROM users WHERE user_id = ?", (interaction.user.id,))
        if not wallet or wallet[0] < plant_info["price"]:
            embed = discord.Embed(
                title="❌ Fonds insuffisants",
                description=f"Vous avez besoin de {format_price(plant_info['price'])} pour planter cette plante.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Déduire l'argent
        execute_query("""
            UPDATE users 
            SET wallet = wallet - ? 
            WHERE user_id = ?
        """, (plant_info["price"], interaction.user.id))

        # Planter la nouvelle plante
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        execute_query("""
            INSERT INTO user_plants (user_id, plant_type, planted_date, last_watered, growth_stage, water_days, total_days)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (interaction.user.id, plant_name, now, now, plant_info["water_days"], plant_info["total_days"]))

        # Utiliser une bouteille d'eau
        execute_query("""
            UPDATE user_items 
            SET quantity = quantity - 1 
            WHERE user_id = ? AND item_name = 'Bouteille d''eau'
        """, (interaction.user.id,))

        embed = discord.Embed(
            title="🌱 Plantation réussie",
            description=f"Vous avez planté une {plant_name} !\n\n"
                       f"• Arrosage tous les {plant_info['water_days']} jours\n"
                       f"• Récolte après {plant_info['total_days']} jours\n"
                       f"• Prix payé: {format_price(plant_info['price'])}",
            color=0x000000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GardenSelect(discord.ui.Select):
    def __init__(self, ctx):
        self.ctx = ctx
        options = [
            discord.SelectOption(
                label="Planter",
                description="Planter une nouvelle plante",
                emoji="🌱",
                value="plant"
            ),
            discord.SelectOption(
                label="Arroser",
                description="Arroser une plante existante",
                emoji="💧",
                value="water"
            ),
            discord.SelectOption(
                label="Récolter",
                description="Récolter une plante mature",
                emoji="🌾",
                value="harvest"
            ),
            discord.SelectOption(
                label="Statut",
                description="Voir l'état de vos plantes",
                emoji="📊",
                value="status"
            )
        ]
        super().__init__(
            placeholder="Choisissez une action...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "plant":
            embed = discord.Embed(
                title="🌱 Planter une plante",
                description="Choisissez le type de plante à planter :",
                color=0x000000
            )
            view = discord.ui.View()
            view.add_item(PlantSelect())
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        elif self.values[0] == "water":
            await interaction.response.send_modal(WaterModal())
        elif self.values[0] == "harvest":
            await interaction.response.send_modal(HarvestModal())
        elif self.values[0] == "status":
            # Récupérer toutes les plantes de l'utilisateur
            plants = fetch_all("""
                SELECT plant_type, planted_date, last_watered, growth_stage, water_days, total_days 
                FROM user_plants 
                WHERE user_id = ?
            """, (interaction.user.id,))

            if not plants:
                embed = discord.Embed(
                    title="❌ Pas de plantes",
                    description="Vous n'avez pas de plantes en cours de croissance.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="📊 État de vos plantes",
                description="Voici l'état de toutes vos plantes :",
                color=0x000000
            )

            for plant_type, planted_date, last_watered, growth_stage, water_days, total_days in plants:
                planted = datetime.strptime(planted_date, "%Y-%m-%d %H:%M:%S")
                last_water = datetime.strptime(last_watered, "%Y-%m-%d %H:%M:%S")
                days_growing = (datetime.now() - planted).days
                needs_water = (datetime.now() - last_water) >= timedelta(days=water_days)

                status = []
                status.append(f"Âge: {days_growing}/{total_days} jours")
                status.append(f"Stade: {growth_stage}/5")
                status.append("💧 Besoin d'eau !" if needs_water else "🌿 Bien hydratée")
                if days_growing >= total_days:
                    status.append("✨ Prête à récolter !")

                embed.add_field(
                    name=f"🌱 {plant_type}",
                    value="\n".join(status),
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

class WaterModal(discord.ui.Modal, title="Arroser une plante"):
    plant_type = discord.ui.TextInput(
        label="Type de plante",
        placeholder="Entrez le type de plante à arroser",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Vérifier si l'utilisateur a des bouteilles d'eau
        water_bottles = fetch_one("""
            SELECT quantity FROM user_items 
            WHERE user_id = ? AND item_name = 'Bouteille d''eau'
        """, (interaction.user.id,))

        if not water_bottles or water_bottles[0] < 1:
            embed = discord.Embed(
                title="❌ Pas de bouteille d'eau",
                description="Vous avez besoin d'une bouteille d'eau pour arroser ! Achetez-en dans le shop.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Vérifier si la plante existe
        plant = fetch_one("""
            SELECT planted_date, last_watered, growth_stage, water_days, total_days 
            FROM user_plants 
            WHERE user_id = ? AND plant_type = ?
        """, (interaction.user.id, self.plant_type.value))

        if not plant:
            embed = discord.Embed(
                title="❌ Plante introuvable",
                description="Vous n'avez pas de plante de ce type en cours de croissance.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        planted_date, last_watered, growth_stage, water_days, total_days = plant
        planted = datetime.strptime(planted_date, "%Y-%m-%d %H:%M:%S")
        last_water = datetime.strptime(last_watered, "%Y-%m-%d %H:%M:%S")
        days_growing = (datetime.now() - planted).days

        # Vérifier si la plante a besoin d'eau
        if (datetime.now() - last_water) < timedelta(days=water_days):
            embed = discord.Embed(
                title="❌ Arrosage non nécessaire",
                description="Cette plante n'a pas encore besoin d'être arrosée.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Vérifier si la plante est mature
        if days_growing >= total_days:
            embed = discord.Embed(
                title="❌ Plante mature",
                description="Cette plante est prête à être récoltée ! Utilisez la commande récolter.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Arroser la plante
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_growth_stage = min(5, growth_stage + 1)
        
        execute_query("""
            UPDATE user_plants 
            SET last_watered = ?, growth_stage = ? 
            WHERE user_id = ? AND plant_type = ?
        """, (now, new_growth_stage, interaction.user.id, self.plant_type.value))

        # Utiliser une bouteille d'eau
        execute_query("""
            UPDATE user_items 
            SET quantity = quantity - 1 
            WHERE user_id = ? AND item_name = 'Bouteille d''eau'
        """, (interaction.user.id,))

        embed = discord.Embed(
            title="💧 Plante arrosée",
            description=f"Vous avez arrosé votre {self.plant_type.value} !\n\n"
                       f"• Stade de croissance: {new_growth_stage}/5\n"
                       f"• Jours restants: {total_days - days_growing}\n"
                       f"• Prochain arrosage dans {water_days} jours",
            color=0x000000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class HarvestModal(discord.ui.Modal, title="Récolter une plante"):
    plant_type = discord.ui.TextInput(
        label="Type de plante",
        placeholder="Entrez le type de plante à récolter",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Vérifier si la plante existe
        plant = fetch_one("""
            SELECT planted_date, growth_stage, total_days, plant_type 
            FROM user_plants 
            WHERE user_id = ? AND plant_type = ?
        """, (interaction.user.id, self.plant_type.value))

        if not plant:
            embed = discord.Embed(
                title="❌ Plante introuvable",
                description="Vous n'avez pas de plante de ce type en cours de croissance.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        planted_date, growth_stage, total_days, plant_type = plant
        planted = datetime.strptime(planted_date, "%Y-%m-%d %H:%M:%S")
        days_growing = (datetime.now() - planted).days

        # Vérifier si la plante est mature
        if days_growing < total_days:
            embed = discord.Embed(
                title="❌ Plante immature",
                description=f"Cette plante n'est pas encore prête à être récoltée.\nJours restants: {total_days - days_growing}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Calculer la récompense basée sur le type de plante et le stade de croissance
        plant_info = next(p for p in PlantSelect().plant_types if p["name"] == plant_type)
        base_reward = plant_info["price"] * 2  # Double du prix d'achat
        growth_multiplier = growth_stage / 5  # 0.0 à 1.0 basé sur le stade de croissance
        final_reward = int(base_reward * (0.5 + growth_multiplier))  # Entre 50% et 150% du prix de base

        # Supprimer la plante
        execute_query("""
            DELETE FROM user_plants 
            WHERE user_id = ? AND plant_type = ?
        """, (interaction.user.id, self.plant_type.value))

        # Ajouter la récompense
        execute_query("""
            UPDATE users 
            SET wallet = wallet + ? 
            WHERE user_id = ?
        """, (final_reward, interaction.user.id))

        embed = discord.Embed(
            title="🌾 Récolte réussie",
            description=f"Vous avez récolté votre {plant_type} !\n\n"
                       f"• Stade de croissance: {growth_stage}/5\n"
                       f"• Temps de croissance: {days_growing} jours\n"
                       f"• Récompense: {format_price(final_reward)}",
            color=0x000000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GardenView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.add_item(GardenSelect(ctx))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

class Phone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def phone(self, ctx):
        # Vérifier si l'utilisateur a un téléphone
        inventory = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
        phone_quantity = 0
        
        if "Téléphone" in inventory:
            if isinstance(inventory["Téléphone"], dict):
                phone_quantity = inventory["Téléphone"].get("quantity", 0)
            else:
                phone_quantity = inventory["Téléphone"]
        
        if phone_quantity <= 0:
            embed = discord.Embed(
                title="❌ Pas de téléphone",
                description="Vous n'avez pas de téléphone ! Achetez-en un dans le shop.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Créer la vue du téléphone
        view = PhoneView(ctx)
        embed = discord.Embed(
            title="📱 Téléphone",
            description="Que souhaitez-vous faire ?",
            color=0x000000
        )
        embed.set_image(url="attachment://unknown.png")
        file = discord.File("commands/unknown.png", filename="unknown.png")
        await ctx.send(file=file, embed=embed, view=view)

class PhoneView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx

    @discord.ui.button(label="Applications", style=discord.ButtonStyle.primary, emoji="📱")
    async def apps_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Créer le menu de sélection
        select = discord.ui.Select(
            placeholder="Choisissez une application...",
            options=[
                discord.SelectOption(
                    label="Jardinage",
                    emoji="🌱",
                    description="Gérer vos plantes",
                    value="garden"
                )
            ]
        )

        async def select_callback(interaction: discord.Interaction):
            if select.values[0] == "garden":
                view = GardenView(self.ctx)
                embed = discord.Embed(
                    title="🌱 Jardin",
                    description="Que souhaitez-vous faire ?",
                    color=0x000000
                )
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        select.callback = select_callback
        view = discord.ui.View(timeout=180)
        view.add_item(select)
        await interaction.response.send_message("📱 Applications disponibles :", view=view, ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

class CategorySelect(discord.ui.Select):
    def __init__(self, categories, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=name,
                emoji=data["emoji"],
                description=data["description"][:100] if len(data["items"]) > 0 else "Vide",
                value=name
            ) for name, data in categories.items() if name != "Tout"
        ]
        options.insert(0, discord.SelectOption(
            label="Tout",
            emoji="📦",
            description="Voir tout l'inventaire",
            value="Tout"
        ))
        super().__init__(
            placeholder="Choisissez une catégorie...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.show_category(interaction, self.values[0])

class InventoryView(discord.ui.View):
    def __init__(self, categories, total_value, total_items, timeout=180):
        super().__init__(timeout=timeout)
        self.categories = categories
        self.total_value = total_value
        self.total_items = total_items
        self.add_item(CategorySelect(categories, self))

    def format_number(self, number):
        return "{:,}".format(number).replace(",", " ")

    def get_category_embed(self, category_name):
        embed = discord.Embed(color=0x000000)
        
        if category_name == "Tout":
            embed.title = "📦 Inventaire Complet"
            items_by_category = []
            for cat_name, cat_data in self.categories.items():
                if cat_name != "Tout" and cat_data["items"]:
                    items_by_category.append(f"{cat_data['emoji']} **{cat_name}**")
                    for item in cat_data["items"][:3]:  # Limiter à 3 items par catégorie
                        items_by_category.append(item)
                    if len(cat_data["items"]) > 3:
                        items_by_category.append(f"*... et {len(cat_data['items']) - 3} autres items*")
                    items_by_category.append("")
            embed.description = "\n".join(items_by_category) if items_by_category else "Inventaire vide"
        else:
            category = self.categories[category_name]
            embed.title = f"{category['emoji']} {category_name}"
            if category["items"]:
                embed.description = "\n".join(category["items"])
            else:
                embed.description = f"Aucun objet dans la catégorie {category_name}"

        # Ajouter le résumé
        embed.set_footer(text=f"💰 Total: {self.format_number(self.total_value)} coins • 📦 Objets: {self.format_number(self.total_items)}")
        return embed

    async def show_category(self, interaction: discord.Interaction, category_name):
        await interaction.response.edit_message(embed=self.get_category_embed(category_name))

async def setup(bot):
    await bot.add_cog(Phone(bot)) 