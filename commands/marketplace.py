import discord
from discord.ext import commands
from datetime import datetime, timedelta
import json
from database import (
    execute_query,
    fetch_one,
    fetch_all,
    get_inventaire,
    update_inventaire,
    user_init,
    cancel_marketplace_listing
)
from .catalogue import catalogue_items
from discord.ext import tasks
from typing import Optional, Dict, List, Union, Tuple, cast, TypedDict, Literal, Any

class MarketplaceListing(TypedDict):
    """Type definition for a marketplace listing"""
    listing_id: int
    seller_id: str
    item_name: str
    quantity: int
    price_per_unit: int
    description: str
    created_at: int
    expires_at: int
    status: Literal['active', 'sold', 'cancelled', 'expired']

def format_price(price: float | int) -> str:
    """Formate un montant en texte lisible"""
    return f"{int(price):,}".replace(",", " ") + " coins"

def get_user_wallet(guild_id: str, user_id: str) -> int:
    """Récupère le montant du portefeuille d'un utilisateur"""
    user_init(guild_id, user_id)
    result = fetch_one("SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    return result[0] if result and result[0] is not None else 0

def update_user_wallet(guild_id: str, user_id: str, amount: int) -> None:
    """Met à jour le portefeuille d'un utilisateur"""
    user_init(guild_id, user_id)
    execute_query("""
        UPDATE users 
        SET wallet = wallet + ? 
        WHERE user_id = ? AND guild_id = ?
    """, (amount, user_id, guild_id))

def get_inventory_quantity(inventory: Optional[Dict], item_name: str) -> int:
    """Get the quantity of an item in an inventory"""
    try:
        if not inventory or not isinstance(inventory, dict) or item_name not in inventory:
            return 0
            
        item = inventory[item_name]
        if isinstance(item, dict):
            quantity = item.get("quantity", 0)
            return safe_int_convert(quantity)
        return safe_int_convert(item)
    except (ValueError, TypeError, AttributeError):
        return 0

def update_inventory_quantity(inventory: Optional[Dict], item_name: str, quantity: int) -> Dict:
    """Update the quantity of an item in an inventory"""
    try:
        if not inventory or not isinstance(inventory, dict):
            inventory = {}
            
        current_quantity = get_inventory_quantity(inventory, item_name)
        new_quantity = current_quantity + quantity
        
        if new_quantity <= 0:
            if item_name in inventory:
                del inventory[item_name]
        else:
            if item_name in inventory and isinstance(inventory[item_name], dict):
                inventory[item_name]["quantity"] = new_quantity
            else:
                inventory[item_name] = new_quantity
            
        return inventory
    except Exception:
        return {} if not inventory else inventory

# Définition des collections d'items et leurs bonus
item_collections = {
    "Set Gaming": {
        "items": ["Ordinateur", "Console", "Smartphone"],
        "emoji": "🎮",
        "bonus": "Augmente les gains de mini-jeux de 5%",
        "bonus_type": "minigames",
        "bonus_value": 0.05
    },
    "Set Luxe": {
        "items": ["Voiture legendary", "Maison epic", "Montre rare"],
        "emoji": "💎",
        "bonus": "Augmente les gains quotidiens de 10%",
        "bonus_type": "daily",
        "bonus_value": 0.10
    },
    "Set Business": {
        "items": ["Commerce", "Ordinateur", "Smartphone"],
        "emoji": "💼",
        "bonus": "Réduit les coûts d'entreprise de 15%",
        "bonus_type": "business",
        "bonus_value": 0.15
    }
}

# Définition des niveaux vendeur
seller_levels = {
    0: {"name": "Débutant", "emoji": "🌱", "bonus": 0, "required_sales": 0},
    1: {"name": "Marchand", "emoji": "💰", "bonus": 0.02, "required_sales": 5},
    2: {"name": "Négociant", "emoji": "💎", "bonus": 0.05, "required_sales": 15},
    3: {"name": "Expert", "emoji": "👑", "bonus": 0.08, "required_sales": 30},
    4: {"name": "Maître", "emoji": "🌟", "bonus": 0.10, "required_sales": 50}
}

# Définition des niveaux acheteur
buyer_levels = {
    0: {"name": "Client", "emoji": "🛍️", "cashback": 0.01, "required_purchases": 0},
    1: {"name": "Habitué", "emoji": "📦", "cashback": 0.02, "required_purchases": 5},
    2: {"name": "VIP", "emoji": "💫", "cashback": 0.03, "required_purchases": 15},
    3: {"name": "Elite", "emoji": "🎭", "cashback": 0.05, "required_purchases": 30}
}

# Définition des missions du marketplace
marketplace_missions = [
    {
        "id": "collector_1",
        "name": "Collectionneur Débutant",
        "description": "Acheter 3 items différents",
        "requirement": 3,
        "type": "unique_items",
        "reward": 1000
    },
    {
        "id": "flash_buyer",
        "name": "Chasseur de Bonnes Affaires",
        "description": "Acheter un item en vente flash",
        "requirement": 1,
        "type": "flash_sale",
        "reward": 2000
    },
    {
        "id": "big_spender",
        "name": "Gros Acheteur",
        "description": "Dépenser 10000 coins sur le marketplace",
        "requirement": 10000,
        "type": "total_spent",
        "reward": 3000
    }
]

class ItemSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption], marketplace_view):
        super().__init__(
            placeholder="Choisissez un item à vendre...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.marketplace_view = marketplace_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.marketplace_view.ctx.author:
            return
            
        item_name, max_quantity = self.values[0].split("|")
        max_quantity = int(max_quantity)
        
        # Créer et envoyer le modal
        modal = ListingModal(item_name, max_quantity, self.marketplace_view)
        await interaction.response.send_modal(modal)

class ListingModal(discord.ui.Modal, title="Créer une annonce"):
    def __init__(self, item_name: str, max_quantity: int, marketplace_view):
        super().__init__()
        self.item_name = item_name
        self.max_quantity = max_quantity
        self.marketplace_view = marketplace_view
        
        self.quantity = discord.ui.TextInput(
            label=f"Quantité (max: {max_quantity})",
            placeholder="Entrez la quantité à vendre...",
            min_length=1,
            max_length=len(str(max_quantity)),
            required=True
        )
        self.add_item(self.quantity)
        
        self.price = discord.ui.TextInput(
            label="Prix par unité",
            placeholder="Entrez le prix par unité...",
            min_length=1,
            max_length=10,
            required=True
        )
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity.value)
            price = int(self.price.value)
            
            if quantity <= 0 or quantity > self.max_quantity:
                embed = discord.Embed(
                    title="❌ Quantité invalide",
                    description=f"La quantité doit être entre 1 et {self.max_quantity}.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            if price <= 0:
                embed = discord.Embed(
                    title="❌ Prix invalide",
                    description="Le prix doit être positif.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Vérifier si l'utilisateur a déjà une annonce pour cet item
            existing_listing = fetch_one("""
                SELECT 1 FROM marketplace_listings
                WHERE seller_id = ? AND item_name = ? AND guild_id = ?
            """, (str(interaction.user.id), self.item_name, str(interaction.guild_id)))

            if existing_listing:
                embed = discord.Embed(
                    title="❌ Annonce existante",
                    description="Vous avez déjà une annonce en cours pour cet item. Annulez-la d'abord.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Vérifier si l'utilisateur a toujours les items
            inventory = get_inventaire(str(interaction.guild_id), str(interaction.user.id))
            if not inventory or self.item_name not in inventory:
                embed = discord.Embed(
                    title="❌ Item introuvable",
                    description="Vous ne possédez plus cet item.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            current_quantity = (
                inventory[self.item_name]["quantity"] 
                if isinstance(inventory[self.item_name], dict) 
                else inventory[self.item_name]
            )
            
            if current_quantity < quantity:
                embed = discord.Embed(
                    title="❌ Quantité insuffisante",
                    description=f"Vous ne possédez que {current_quantity}x {self.item_name}.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            # Créer l'annonce
            execute_query("""
                INSERT INTO marketplace_listings
                (guild_id, seller_id, item_name, quantity, price_per_unit, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(interaction.guild_id),
                str(interaction.user.id),
                self.item_name,
                quantity,
                price,
                int(datetime.now().timestamp()),
                int((datetime.now() + timedelta(days=7)).timestamp())
            ))
            
            # Retirer les items de l'inventaire
            if isinstance(inventory[self.item_name], dict):
                inventory[self.item_name]["quantity"] -= quantity
            else:
                inventory[self.item_name] = inventory[self.item_name] - quantity
            update_inventaire(str(interaction.guild_id), str(interaction.user.id), inventory)
            
            embed = discord.Embed(
                title="✅ Annonce créée",
                description=f"Votre annonce a été créée avec succès !\n\n"
                           f"• Item: {self.item_name}\n"
                           f"• Quantité: {quantity}\n"
                           f"• Prix unitaire: {format_price(price)}\n"
                           f"• Total: {format_price(price * quantity)}",
                color=0x000000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Mettre à jour l'affichage
            await self.marketplace_view.update_message(interaction)
            
        except ValueError:
            embed = discord.Embed(
                title="❌ Valeurs invalides",
                description="Les valeurs entrées ne sont pas des nombres valides.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de la création de l'annonce.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class SellSelect(discord.ui.Select):
    def __init__(self, view):
        self.marketplace_view = view
        options = []
        self.has_more_items = False  # Pour stocker l'info pour le callback
        
        # Récupérer l'inventaire
        inventory = get_inventaire(str(view.ctx.guild.id), str(view.ctx.author.id))

        if inventory:
            try:
                # Parcourir les items de l'inventaire
                items_to_show = []
                for item_name, quantity in inventory.items():
                    # Vérifier si l'item a une quantité
                    if isinstance(quantity, dict):
                        available_quantity = quantity.get("quantity", 0)
                    else:
                        available_quantity = quantity

                    if available_quantity > 0:
                        # Vérifier si l'item est déjà en vente
                        existing_listing = fetch_one("""
                            SELECT * FROM marketplace_listings 
                            WHERE guild_id = ? AND seller_id = ? AND item_name = ? AND expires_at > ?
                        """, (
                            str(view.ctx.guild.id),
                            str(view.ctx.author.id),
                            item_name,
                            int(datetime.now().timestamp())
                        ))
                        
                        if not existing_listing:
                            # Chercher l'emoji dans le catalogue
                            item_emoji = "📦"
                            base_name = item_name.split()[0] if " " in item_name else item_name
                            
                            for cat_items in catalogue_items.values():
                                for cat_item in cat_items:
                                    if cat_item["name"] == base_name:
                                        item_emoji = cat_item.get("emoji", "📦")
                                        break
                            
                            items_to_show.append({
                                "name": item_name,
                                "quantity": available_quantity,
                                "emoji": item_emoji
                            })

                # Trier les items par nom pour avoir un ordre cohérent
                items_to_show.sort(key=lambda x: x["name"])
                
                # Limiter à 25 items (limite Discord) et créer les options
                self.has_more_items = len(items_to_show) > 25
                for item in items_to_show[:25]:
                    options.append(
                        discord.SelectOption(
                            label=item["name"],
                            description=f"Quantité: {item['quantity']}",
                            value=f"shop:{item['name']}",
                            emoji=item["emoji"]
                        )
                    )
                                            
            except Exception as e:
                pass
                
        super().__init__(
            placeholder="Choisissez un item à vendre...",
            min_values=1,
            max_values=1,
            options=options if options else [
                discord.SelectOption(
                    label="Aucun item disponible",
                    description="Vous n'avez aucun item à vendre",
                    value="none",
                    emoji="❌"
                )
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        if self.has_more_items:
            await interaction.response.send_message("⚠️ Vous avez plus de 25 items différents ! Seuls les 25 premiers sont affichés, triés par ordre alphabétique.", ephemeral=True)
            return
            
        if self.values[0] == "none":
            await interaction.response.send_message("❌ Vous n'avez aucun item à vendre !", ephemeral=True)
            return
            
        category, item_name = self.values[0].split(":")
        
        # Récupérer l'inventaire
        inventory = get_inventaire(str(interaction.guild_id), str(interaction.user.id))
        if not inventory or item_name not in inventory:
            await interaction.response.send_message("❌ Vous ne possédez plus cet item !", ephemeral=True)
            return
            
        quantity = inventory[item_name]
        if isinstance(quantity, dict):
            quantity = quantity.get("quantity", 0)
            
        if quantity <= 0:
            await interaction.response.send_message("❌ Vous ne possédez plus cet item !", ephemeral=True)
            return
            
        # Ouvrir le modal de vente
        modal = ListingModal(item_name, quantity, self.marketplace_view)
        await interaction.response.send_modal(modal)

class MyListingsSelect(discord.ui.Select):
    def __init__(self, marketplace_view):
        self.marketplace_view = marketplace_view
        
        # Récupérer les annonces du joueur
        listings = fetch_all("""
            SELECT * FROM marketplace_listings
            WHERE guild_id = ? AND seller_id = ? AND expires_at > ?
            ORDER BY created_at DESC
        """, (
            str(marketplace_view.ctx.guild.id),
            str(marketplace_view.ctx.author.id),
            int(datetime.now().timestamp())
        ))
        
        options = []
        for listing in listings:
            listing_id = listing[0]  # L'ID est à l'index 0
            item_name = listing[3]
            quantity = listing[4]
            price = listing[5]
            
            # Trouver l'emoji de l'item
            item_emoji = "📦"
            for category in catalogue_items.values():
                for item in category:
                    if item["name"] == item_name:
                        item_emoji = item["emoji"]
                        break
            
            options.append(
                discord.SelectOption(
                    label=f"{item_name} (x{quantity})",
                    value=str(listing_id),  # Utiliser l'ID correct
                    emoji=item_emoji,
                    description=f"Prix: {format_price(price)} par unité"
                )
            )
            
        if not options:
            options = [discord.SelectOption(
                label="Aucune annonce active",
                value="none",
                emoji="❌",
                description="Vous n'avez aucune annonce en cours"
            )]
            
        super().__init__(
            placeholder="Sélectionnez une annonce à annuler...",
            min_values=1,
            max_values=1,
            options=options[:25]  # Discord limite à 25 options
        )
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Vous n'avez aucune annonce à annuler !", ephemeral=True)
            return
            
        listing_id = int(self.values[0])
        success, message = cancel_marketplace_listing(listing_id, str(interaction.user.id))
        
        if success:
            await interaction.response.send_message("✅ Votre annonce a été annulée !", ephemeral=True)
            await self.marketplace_view.refresh_marketplace(interaction)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

class CategorySelect(discord.ui.Select):
    def __init__(self, marketplace_view):
        self.marketplace_view = marketplace_view
        options = [
            discord.SelectOption(
                label="Tout",
                value="all",
                emoji="🏪",
                description="Voir toutes les annonces"
            ),
            discord.SelectOption(
                label="Véhicules",
                value="vehicles",
                emoji="🚗",
                description="Voitures, motos, bateaux..."
            ),
            discord.SelectOption(
                label="Propriétés",
                value="properties",
                emoji="🏠",
                description="Maisons, appartements..."
            ),
            discord.SelectOption(
                label="Tech",
                value="tech",
                emoji="📱",
                description="Téléphones, ordinateurs..."
            ),
            discord.SelectOption(
                label="Collections",
                value="collectibles",
                emoji="🎨",
                description="Cartes, tableaux..."
            ),
            discord.SelectOption(
                label="Ressources",
                value="resources",
                emoji="📦",
                description="Matériaux, nourriture..."
            ),
            discord.SelectOption(
                label="Autres",
                value="other",
                emoji="❓",
                description="Tout le reste"
            )
        ]
        
        super().__init__(
            placeholder="🔍 Filtrer par catégorie...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )
        
    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.marketplace_view.ctx.author:
            return
            
        self.marketplace_view.current_category = self.values[0]
        self.marketplace_view.current_page = 1
        await self.marketplace_view.update_message(interaction)

class MarketplaceView(discord.ui.View):
    def __init__(self, ctx, marketplace):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.marketplace = marketplace
        self.current_page = 1
        self.items_per_page = 5
        self.current_category = "Tout"
        self.add_item(CategorySelect(self))

    @discord.ui.button(label="📝 Vendre", style=discord.ButtonStyle.primary, custom_id="sell", row=1)
    async def sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return
        view = discord.ui.View()
        view.add_item(SellSelect(self))
        await interaction.response.send_message("📝 Que souhaitez-vous vendre ?", view=view, ephemeral=True)

    @discord.ui.button(label="📋 Mes annonces", style=discord.ButtonStyle.secondary, custom_id="my_listings", row=1)
    async def my_listings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return
        view = discord.ui.View()
        view.add_item(MyListingsSelect(self))
        await interaction.response.send_message("📋 Gérer vos annonces :", view=view, ephemeral=True)

    @discord.ui.button(label="📊 Mes stats", style=discord.ButtonStyle.secondary, custom_id="stats", row=1)
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return
            
        # Récupérer les stats de l'utilisateur
        stats = self.marketplace.get_user_stats(str(interaction.guild_id), str(interaction.user.id))
        if not stats:
            await interaction.response.send_message("❌ Une erreur est survenue lors de la récupération de vos statistiques.", ephemeral=True)
            return
            
        # Déterminer le niveau vendeur
        seller_level = 0
        for level, data in seller_levels.items():
            if stats.get("total_sales", 0) >= data["required_sales"]:
                seller_level = level
                
        # Déterminer le niveau acheteur
        buyer_level = 0
        for level, data in buyer_levels.items():
            if stats.get("total_purchases", 0) >= data["required_purchases"]:
                buyer_level = level
                
        # Créer l'embed
        embed = discord.Embed(title="📊 Vos statistiques du marketplace", color=discord.Color.blue())
        
        # Section Vendeur
        seller_info = seller_levels[seller_level]
        next_seller_level = seller_levels.get(seller_level + 1)
        seller_progress = ""
        if next_seller_level:
            remaining_sales = next_seller_level["required_sales"] - stats.get("total_sales", 0)
            seller_progress = f"\nEncore {remaining_sales} ventes pour le niveau suivant !"
            
        embed.add_field(
            name="🏷️ Profil Vendeur",
            value=f"Niveau: {seller_info['emoji']} {seller_info['name']}\n"
                  f"Bonus de vente: +{seller_info['bonus']*100}%\n"
                  f"Ventes totales: {stats.get('total_sales', 0)}{seller_progress}",
            inline=False
        )
        
        # Section Acheteur
        buyer_info = buyer_levels[buyer_level]
        next_buyer_level = buyer_levels.get(buyer_level + 1)
        buyer_progress = ""
        if next_buyer_level:
            remaining_purchases = next_buyer_level["required_purchases"] - stats.get("total_purchases", 0)
            buyer_progress = f"\nEncore {remaining_purchases} achats pour le niveau suivant !"
            
        embed.add_field(
            name="🛍️ Profil Acheteur",
            value=f"Niveau: {buyer_info['emoji']} {buyer_info['name']}\n"
                  f"Cashback: {buyer_info['cashback']*100}%\n"
                  f"Achats totaux: {stats.get('total_purchases', 0)}{buyer_progress}",
            inline=False
        )
        
        # Statistiques générales
        embed.add_field(
            name="📈 Statistiques générales",
            value=f"Argent dépensé: {stats.get('money_spent', 0):,}$\n"
                  f"Argent gagné: {stats.get('money_earned', 0):,}$\n"
                  f"Objets vendus: {stats.get('items_sold', 0)}\n"
                  f"Objets achetés: {stats.get('items_bought', 0)}\n"
                  f"Ventes flash réalisées: {stats.get('flash_sales', 0)}",
            inline=False
        )
        
        # Ajouter une explication du système
        embed.add_field(
            name="ℹ️ Système de niveaux",
            value="**Vendeur:**\n"
                  "Plus vous vendez, plus votre niveau augmente, vous donnant un bonus sur vos ventes !\n"
                  "Débutant (0%) → Marchand (+2%) → Négociant (+5%) → Expert (+8%) → Maître (+10%)\n\n"
                  "**Acheteur:**\n"
                  "Plus vous achetez, plus votre niveau augmente, vous donnant un meilleur cashback !\n"
                  "Client (1%) → Habitué (2%) → VIP (3%) → Elite (5%)",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, custom_id="previous_page", row=2)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, custom_id="next_page", row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return
        self.current_page += 1
        await self.update_message(interaction)

    def get_item_category(self, item_name: str) -> str:
        """Détermine la catégorie d'un item"""
        # Liste des mots-clés par catégorie
        categories = {
            "vehicles": ["voiture", "moto", "vélo", "bateau", "avion"],
            "properties": ["maison", "appartement", "garage", "bureau", "entrepôt"],
            "tech": ["téléphone", "ordinateur", "console", "tv", "tablette"],
            "collectibles": ["carte", "tableau", "statue", "montre", "bijou"],
            "resources": ["bois", "pierre", "métal", "tissu", "nourriture"]
        }
        
        item_lower = item_name.lower()
        for category, keywords in categories.items():
            if any(keyword in item_lower for keyword in keywords):
                return category
        return "other"

    async def update_message(self, interaction: discord.Interaction | None = None):
        try:
            # Récupérer les annonces actives
            listings = fetch_all("""
                SELECT * FROM marketplace_listings
                WHERE expires_at > ?
                ORDER BY created_at DESC
            """, (int(datetime.now().timestamp()),))
            
            if not listings:
                listings = []
            
            # Calculer la pagination
            total_pages = (len(listings) + self.items_per_page - 1) // self.items_per_page
            start_idx = (self.current_page - 1) * self.items_per_page
            end_idx = start_idx + self.items_per_page
            current_listings = listings[start_idx:end_idx]
            
            # Créer l'embed
            embed = discord.Embed(
                title=f"🏪 Marketplace",
                description="Achetez et vendez des items avec d'autres joueurs !\n"
                           "Utilisez `+mpbuy <id> <quantité>` pour acheter un item.",
                color=0x2f3136
            )
            
            # Afficher les ventes flash actuelles
            flash_sale = self.marketplace.get_flash_sales()
            if flash_sale and isinstance(flash_sale, dict):
                category = flash_sale.get('category')
                discount = flash_sale.get('discount')
                if category and discount is not None:
                    embed.add_field(
                        name="⚡ Vente Flash !",
                        value=f"Catégorie: {category}\n"
                              f"Réduction: -{discount*100}%\n"
                              f"Durée: {4 - datetime.now().hour % 4}h restantes",
                        inline=False
                    )
            
            # Afficher les annonces
            if not current_listings:
                embed.add_field(
                    name="Aucune annonce",
                    value="Il n'y a aucune annonce active dans cette catégorie.",
                    inline=False
                )
            else:
                for listing in current_listings:
                    try:
                        # Récupérer le nom du vendeur
                        seller_id = listing[2] if listing[2] else "0"  # seller_id
                        seller = self.ctx.guild.get_member(int(seller_id))
                        seller_name = seller.name if seller else "Inconnu"
                        
                        # Récupérer les informations de l'item
                        item_name = listing[3] if listing[3] else "Item inconnu"  # item_name
                        quantity = int(listing[4]) if listing[4] else 0  # quantity
                        price_per_unit = int(listing[5]) if listing[5] else 0  # price_per_unit
                        listing_id = int(listing[0]) if listing[0] else 0  # listing_id
                        
                        # Calculer la tendance du prix
                        price_trend = self.marketplace.calculate_market_price(item_name)
                        
                        # Vérifier si l'item est en vente flash
                        if flash_sale and isinstance(flash_sale, dict):
                            category = flash_sale.get('category')
                            discount = flash_sale.get('discount')
                            if category and discount is not None and price_per_unit > 0:
                                # Appliquer la réduction si l'item correspond à la catégorie
                                if self.get_item_category(item_name) == category.lower():
                                    price_per_unit = int(price_per_unit * (1 - discount))
                        
                        # Ajouter l'emoji de la catégorie
                        category = self.get_item_category(item_name)
                        category_emoji = "📦"  # Emoji par défaut
                        
                        embed.add_field(
                            name=f"{category_emoji} {item_name} (x{quantity})",
                            value=f"Prix: {format_price(price_per_unit)} par unité\n"
                                  f"Vendeur: {seller_name}\n"
                                  f"Tendance: {price_trend}\n"
                                  f"ID: {listing_id}",
                            inline=False
                        )
                    except (ValueError, TypeError, IndexError) as e:
                        continue
            
            # Ajouter la pagination
            embed.set_footer(text=f"Page {self.current_page}/{total_pages if total_pages > 0 else 1}")
            
            # Mettre à jour les boutons
            self.update_buttons(total_pages)
            
            # Envoyer ou mettre à jour le message
            if interaction and hasattr(interaction, 'response'):
                try:
                    if interaction.response.is_done():
                        if hasattr(interaction, 'message') and interaction.message:
                            await interaction.message.edit(embed=embed, view=self)
                    else:
                        await interaction.response.edit_message(embed=embed, view=self)
                except discord.NotFound:
                    pass
            else:
                return embed
                
        except Exception as e:
            return None

    def update_buttons(self, total_pages: int):
        """Met à jour l'état des boutons de pagination"""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "previous_page":
                    child.disabled = self.current_page <= 1
                elif child.custom_id == "next_page":
                    child.disabled = self.current_page >= total_pages

class MarketplaceError(Exception):
    """Base exception class for marketplace errors"""
    def __init__(self, message: str, title: str = "❌ Erreur"):
        self.message = message
        self.title = title
        super().__init__(message)

def create_error_embed(error: MarketplaceError) -> discord.Embed:
    """Create an error embed from a MarketplaceError"""
    return discord.Embed(
        title=error.title,
        description=error.message,
        color=discord.Color.red()
    )

def create_success_embed(title: str, description: str) -> discord.Embed:
    """Create a success embed with consistent styling"""
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green()
    )

def safe_int_convert(value: Any, default: int = 0) -> int:
    """Safely convert a value to int, returning default if conversion fails"""
    try:
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_str_convert(value: Any, default: str = "") -> str:
    """Safely convert a value to str, returning default if value is None"""
    return str(value) if value is not None else default

def validate_listing_data(
    guild_id: str,
    user_id: str,
    item_name: str,
    quantity: int,
    price: int
) -> None:
    """Validate listing data and raise appropriate errors"""
    if not guild_id or not user_id:
        raise MarketplaceError("Les IDs de serveur et d'utilisateur sont requis.")
        
    if not item_name:
        raise MarketplaceError("Le nom de l'item est requis.")
        
    if quantity <= 0:
        raise MarketplaceError(
            "La quantité doit être positive.",
            "❌ Quantité invalide"
        )
        
    if price <= 0:
        raise MarketplaceError(
            "Le prix doit être positif.",
            "❌ Prix invalide"
        )

    # Check if item exists in user's inventory
    inventory = get_inventaire(guild_id, user_id)
    if not inventory or item_name not in inventory:
        raise MarketplaceError(
            "Vous ne possédez pas cet item.",
            "❌ Item introuvable"
        )

    item_quantity = get_inventory_quantity(inventory, item_name)
    if item_quantity < quantity:
        raise MarketplaceError(
            f"Vous n'avez que {item_quantity}x {item_name}.",
            "❌ Quantité insuffisante"
        )

def validate_guild_context(ctx: commands.Context) -> tuple[str, str]:
    """Validate that command is used in a guild and return IDs"""
    if not ctx.guild:
        raise MarketplaceError(
            "Cette commande ne peut être utilisée que dans un serveur.",
            "❌ Erreur"
        )
    return str(ctx.guild.id), str(ctx.author.id)

def get_marketplace_listing(listing_id: int, guild_id: str) -> Optional[MarketplaceListing]:
    """Get a marketplace listing by ID"""
    try:
        result = fetch_one("""
            SELECT listing_id, seller_id, item_name, quantity, price_per_unit, 
                   description, created_at, expires_at, status
            FROM marketplace_listings 
            WHERE listing_id = ? AND guild_id = ? AND status = 'active'
        """, (listing_id, guild_id))
        
        if not result or len(result) != 9:
            return None
            
        # Convert all values to their proper types
        listing_id, seller_id, item_name, quantity, price_per_unit, description, created_at, expires_at, status = result
        
        return {
            'listing_id': safe_int_convert(listing_id),
            'seller_id': safe_str_convert(seller_id),
            'item_name': safe_str_convert(item_name),
            'quantity': safe_int_convert(quantity),
            'price_per_unit': safe_int_convert(price_per_unit),
            'description': safe_str_convert(description),
            'created_at': safe_int_convert(created_at),
            'expires_at': safe_int_convert(expires_at),
            'status': cast(Literal['active', 'sold', 'cancelled', 'expired'], safe_str_convert(status))
        }
    except Exception:
        return None

def validate_listing_access(listing: Optional[MarketplaceListing], user_id: str, for_purchase: bool = False) -> MarketplaceListing:
    """Validate listing exists and user has access to it"""
    if not listing:
        raise MarketplaceError(
            "Cette annonce n'existe pas ou a expiré.",
            "❌ Annonce introuvable"
        )

    if for_purchase:
        if user_id == listing['seller_id']:
            raise MarketplaceError(
                "Vous ne pouvez pas acheter vos propres items.",
                "❌ Action impossible"
            )
    else:
        if user_id != listing['seller_id']:
            raise MarketplaceError(
                "Vous ne pouvez pas modifier l'annonce d'un autre utilisateur.",
                "❌ Action impossible"
            )

    return listing

def validate_purchase_quantity(listing: MarketplaceListing, quantity: int) -> None:
    """Validate purchase quantity is valid"""
    if quantity <= 0:
        raise MarketplaceError(
            "La quantité doit être positive.",
            "❌ Quantité invalide"
        )

    if quantity > listing['quantity']:
        raise MarketplaceError(
            f"Il n'y a que {listing['quantity']} unités disponibles.",
            "❌ Stock insuffisant"
        )

def validate_buyer_funds(guild_id: str, buyer_id: str, total_cost: int) -> None:
    """Validate buyer has sufficient funds"""
    buyer_wallet = get_user_wallet(guild_id, buyer_id)
    if buyer_wallet < total_cost:
        raise MarketplaceError(
            f"Il vous manque {format_price(total_cost - buyer_wallet)}.",
            "❌ Fonds insuffisants"
        )

async def notify_seller(ctx: commands.Context, listing: MarketplaceListing, quantity: int, total_cost: int) -> None:
    """Notify seller about a successful sale"""
    try:
        if not ctx.guild:
            return

        seller = await ctx.guild.fetch_member(int(listing['seller_id']))
        if seller:
            seller_embed = create_success_embed(
                "💰 Vente effectuée",
                f"{ctx.author.name} a acheté {quantity}x {listing['item_name']} pour {format_price(total_cost)}."
            )
            await seller.send(embed=seller_embed)
    except Exception:
        pass  # Ignore errors when trying to notify seller

class Marketplace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.categories = {
            "Tous": "🏪",
            "Outils": "🛠️",
            "Ressources": "📦",
            "Véhicules": "🚗",
            "Immobilier": "🏠",
            "Luxe": "💎",
            "Divers": "��"
        }
        self.ensure_tables_exist()
        self.check_expired_listings.start()

    def ensure_tables_exist(self) -> None:
        """Crée les tables nécessaires si elles n'existent pas"""
        execute_query("""
            CREATE TABLE IF NOT EXISTS marketplace_listings (
                guild_id TEXT,
                seller_id TEXT,
                item_name TEXT,
                quantity INTEGER,
                price_per_unit INTEGER,
                created_at INTEGER,
                expires_at INTEGER,
                PRIMARY KEY (guild_id, seller_id, item_name)
            )
        """)

        execute_query("""
            CREATE TABLE IF NOT EXISTS user_stats (
                guild_id TEXT,
                user_id TEXT,
                total_sales INTEGER DEFAULT 0,
                total_purchases INTEGER DEFAULT 0,
                items_sold INTEGER DEFAULT 0,
                items_bought INTEGER DEFAULT 0,
                money_earned INTEGER DEFAULT 0,
                money_spent INTEGER DEFAULT 0,
                flash_sales INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        execute_query("""
            CREATE TABLE IF NOT EXISTS completed_missions (
                guild_id TEXT,
                user_id TEXT,
                mission_id TEXT,
                completed_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (guild_id, user_id, mission_id)
            )
        """)

        execute_query("""
            CREATE TABLE IF NOT EXISTS flash_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                discount REAL,
                start_time INTEGER,
                duration INTEGER
            )
        """)
        
    def cog_unload(self):
        self.check_expired_listings.cancel()

    @tasks.loop(minutes=30)
    async def check_expired_listings(self):
        # Récupérer les annonces expirées
        expired_listings = fetch_all("""
            SELECT guild_id, seller_id, item_name, quantity 
            FROM marketplace_listings 
            WHERE expires_at < ?
        """, (int(datetime.now().timestamp()),))

        if not expired_listings:
            return

        for guild_id, seller_id, item_name, quantity in expired_listings:
            try:
                # Récupérer l'inventaire du vendeur
                inventory = get_inventaire(guild_id, seller_id)
                if inventory is not None:
                    inventory = update_inventory_quantity(inventory, item_name, quantity)
                    update_inventaire(guild_id, seller_id, inventory)

                # Supprimer l'annonce
                execute_query("""
                    DELETE FROM marketplace_listings 
                    WHERE guild_id = ? AND seller_id = ? AND item_name = ?
                """, (guild_id, seller_id, item_name))

                # Notifier le vendeur si possible
                try:
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        member = guild.get_member(int(seller_id))
                        if member:
                            embed = discord.Embed(
                                title="📦 Annonce expirée",
                                description=f"Votre annonce pour {quantity}x {item_name} a expiré.\nLes items ont été remis dans votre inventaire.",
                                color=discord.Color.red()
                            )
                            await member.send(embed=embed)
                except Exception as e:
                    pass

            except Exception as e:
                pass

    @commands.command(name="marketplace", aliases=["mp", "market"])
    async def marketplace(self, ctx):
        embed = discord.Embed(
            title="🏪 Marketplace",
            description="Bienvenue sur le marketplace ! Utilisez les boutons ci-dessous pour naviguer.",
            color=0x000000
        )
        view = MarketplaceView(ctx, self)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="mpbuy", aliases=["mpacheter"])
    async def buy_item(self, ctx: commands.Context, listing_id: int, quantity: int = 1):
        """Buy an item from the marketplace"""
        try:
            # Validate context and get IDs
            guild_id, buyer_id = validate_guild_context(ctx)

            # Get and validate listing
            listing = validate_listing_access(
                get_marketplace_listing(listing_id, guild_id),
                buyer_id,
                for_purchase=True
            )

            # Validate purchase
            validate_purchase_quantity(listing, quantity)
            total_cost = quantity * listing['price_per_unit']
            validate_buyer_funds(guild_id, buyer_id, total_cost)

            # Update buyer's wallet and inventory
            update_user_wallet(guild_id, buyer_id, -total_cost)
            buyer_inventory = get_inventaire(guild_id, buyer_id)
            if buyer_inventory is not None:
                buyer_inventory = update_inventory_quantity(buyer_inventory, listing['item_name'], quantity)
                update_inventaire(guild_id, buyer_id, buyer_inventory)

            # Update seller's wallet
            update_user_wallet(guild_id, listing['seller_id'], total_cost)

            # Update listing
            if quantity == listing['quantity']:
                execute_query("""
                    UPDATE marketplace_listings 
                    SET status = 'sold' 
                    WHERE listing_id = ? AND guild_id = ?
                """, (listing_id, guild_id))
            else:
                execute_query("""
                    UPDATE marketplace_listings 
                    SET quantity = quantity - ? 
                    WHERE listing_id = ? AND guild_id = ?
                """, (quantity, listing_id, guild_id))

            # Send confirmations
            await ctx.reply(embed=create_success_embed(
                "✅ Achat effectué",
                f"Vous avez acheté {quantity}x {listing['item_name']} pour {format_price(total_cost)}."
            ))
            await notify_seller(ctx, listing, quantity, total_cost)

        except MarketplaceError as e:
            await ctx.reply(embed=create_error_embed(e))
        except Exception as e:
            await ctx.reply(embed=discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de l'achat.",
                color=discord.Color.red()
            ))

    @commands.command(name="mpsell", aliases=["mpvendre"])
    async def sell_item(self, ctx, item_name: str, quantity: int, price: int):
        """Vendre un item sur le marketplace"""
        try:
            # Validate context and get IDs
            guild_id, user_id = validate_guild_context(ctx)

            # Validate input data
            validate_listing_data(guild_id, user_id, item_name, quantity, price)

            # Check for existing listing
            existing = fetch_one("""
                SELECT 1 FROM marketplace_listings
                WHERE seller_id = ? AND item_name = ? AND guild_id = ? AND status = 'active'
            """, (user_id, item_name, guild_id))

            if existing:
                raise MarketplaceError(
                    "Vous avez déjà une annonce en cours pour cet item. Annulez-la d'abord.",
                    "❌ Annonce existante"
                )

            # Create the listing
            execute_query("""
                INSERT INTO marketplace_listings (
                    guild_id, seller_id, item_name, quantity, price_per_unit,
                    description, created_at, expires_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                guild_id, user_id, item_name, quantity, price,
                "", int(datetime.now().timestamp()),
                int((datetime.now() + timedelta(days=1)).timestamp()),
                'active'
            ))

            # Update seller's inventory
            inventory = get_inventaire(guild_id, user_id)
            inventory = update_inventory_quantity(inventory, item_name, -quantity)
            update_inventaire(guild_id, user_id, inventory)

            # Send confirmation
            embed = discord.Embed(
                title="✅ Annonce créée",
                description=f"Vous avez mis en vente {quantity}x {item_name} pour {format_price(price)} par unité.",
                color=discord.Color.green()
            )
            await ctx.reply(embed=embed)

        except MarketplaceError as e:
            await ctx.reply(embed=create_error_embed(e))
        except Exception as e:
            await ctx.reply(embed=discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de la création de l'annonce.",
                color=discord.Color.red()
            ))

    @commands.command(name="mpcancel", aliases=["mpannuler"])
    async def cancel_listing(self, ctx: commands.Context, listing_id: int):
        """Cancel a marketplace listing"""
        try:
            # Validate context and get IDs
            guild_id, user_id = validate_guild_context(ctx)

            # Get and validate listing
            listing = validate_listing_access(
                get_marketplace_listing(listing_id, guild_id),
                user_id
            )

            # Cancel the listing
            execute_query("""
                UPDATE marketplace_listings 
                SET status = 'cancelled' 
                WHERE listing_id = ? AND guild_id = ? AND seller_id = ?
            """, (listing_id, guild_id, user_id))

            # Return items to inventory
            inventory = get_inventaire(guild_id, user_id)
            if inventory is not None:
                inventory = update_inventory_quantity(inventory, listing['item_name'], listing['quantity'])
                update_inventaire(guild_id, user_id, inventory)

            # Send confirmation
            await ctx.reply(embed=create_success_embed(
                "✅ Annonce annulée",
                f"Votre annonce pour {listing['quantity']}x {listing['item_name']} a été annulée."
            ))

        except MarketplaceError as e:
            await ctx.reply(embed=create_error_embed(e))
        except Exception as e:
            print(f"Error in cancel_listing: {e}")
            await ctx.reply(embed=discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de l'annulation de l'annonce.",
                color=discord.Color.red()
            ))

    @commands.command(name="mplist", aliases=["mpannonces"])
    async def list_items(self, ctx):
        """Voir toutes les annonces actives"""
        embed = discord.Embed(
            title="🏪 Marketplace",
            description="Achetez et vendez des items avec d'autres joueurs !",
            color=0x000000
        )
        view = MarketplaceView(ctx, self)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="mpinfo")
    async def item_info(self, ctx, listing_id: int):
        """Voir les détails d'une annonce"""
        try:
            # Récupérer l'annonce
            listing = fetch_one("""
                SELECT * FROM marketplace_listings
                WHERE listing_id = ? AND expires_at > ?
            """, (listing_id, int(datetime.now().timestamp())))

            if not listing:
                embed = discord.Embed(
                    title="❌ Annonce introuvable",
                    description="Cette annonce n'existe pas ou a expiré.",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
                return

            # Récupérer les informations du vendeur
            seller = await self.bot.fetch_user(int(listing[2]))
            seller_name = seller.name if seller else "Vendeur inconnu"

            # Vérifier si l'item est en vente flash
            flash_sale = self.get_flash_sales()
            is_flash_sale = False
            if flash_sale and isinstance(flash_sale, dict):
                category = flash_sale.get('category')
                if category and self.get_item_category(listing[3]) == category.lower():
                    is_flash_sale = True

            # Créer l'embed
            embed = discord.Embed(
                title=f"📦 {listing[3]}",
                description=f"Informations sur l'annonce #{listing_id}",
                color=0x000000
            )
            embed.add_field(name="Vendeur", value=seller_name, inline=True)
            embed.add_field(name="Quantité", value=listing[4], inline=True)
            embed.add_field(name="Prix unitaire", value=format_price(listing[5]), inline=True)
            embed.add_field(name="Prix total", value=format_price(listing[4] * listing[5]), inline=True)
            
            if is_flash_sale:
                embed.add_field(name="⚡ Vente Flash", value=f"Réduction de {int(flash_sale['discount']*100)}%", inline=True)

            # Ajouter le temps restant
            expires_at = datetime.fromtimestamp(listing[7])
            time_left = expires_at - datetime.now()
            days_left = time_left.days
            hours_left = time_left.seconds // 3600
            embed.add_field(name="Expire dans", value=f"{days_left}j {hours_left}h", inline=True)

            await ctx.reply(embed=embed)

        except Exception as e:
            print(f"Erreur lors de la récupération des informations: {e}")
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de la récupération des informations.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

    @commands.command(name="mpmy", aliases=["mpmes"])
    async def my_listings(self, ctx):
        """Voir vos annonces actives"""
        try:
            # Récupérer les annonces de l'utilisateur
            listings = fetch_all("""
                SELECT * FROM marketplace_listings
                WHERE seller_id = ? AND expires_at > ?
                ORDER BY created_at DESC
            """, (str(ctx.author.id), int(datetime.now().timestamp())))

            if not listings:
                embed = discord.Embed(
                    title="📋 Mes annonces",
                    description="Vous n'avez aucune annonce active.",
                    color=0x000000
                )
                await ctx.reply(embed=embed)
                return

            embed = discord.Embed(
                title="📋 Mes annonces",
                description="Vos annonces actives sur le marketplace",
                color=0x000000
            )

            for listing in listings:
                # Vérifier si l'item est en vente flash
                flash_sale = self.get_flash_sales()
                is_flash_sale = False
                if flash_sale and isinstance(flash_sale, dict):
                    category = flash_sale.get('category')
                    if category and self.get_item_category(listing[3]) == category.lower():
                        is_flash_sale = True

                # Calculer le temps restant
                expires_at = datetime.fromtimestamp(listing[7])
                time_left = expires_at - datetime.now()
                days_left = time_left.days
                hours_left = time_left.seconds // 3600

                # Ajouter les informations de l'annonce
                description = [
                    f"Quantité : {listing[4]}",
                    f"Prix unitaire : {format_price(listing[5])}",
                    f"Prix total : {format_price(listing[4] * listing[5])}",
                    f"Expire dans : {days_left}j {hours_left}h"
                ]

                if is_flash_sale:
                    description.append(f"⚡ En vente flash ! (-{int(flash_sale['discount']*100)}%)")

                embed.add_field(
                    name=f"#{listing[0]} - {listing[3]}",
                    value="\n".join(description),
                    inline=False
                )

            await ctx.reply(embed=embed)

        except Exception as e:
            print(f"Erreur lors de la récupération des annonces: {e}")
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de la récupération de vos annonces.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

    @commands.command(name="delitem", aliases=["deleteitem", "removeitem"])
    async def delete_item(self, ctx, item_name: str, quantity: int = None):
        """Supprime définitivement un item de votre inventaire"""
        try:
            # Vérifier si l'utilisateur a l'item
            inventory = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
            if not inventory or item_name not in inventory:
                error_embed = discord.Embed(
                    title="❌ Erreur",
                    description="Vous ne possédez pas cet item.",
                    color=0xff0000
                )
                await ctx.reply(embed=error_embed)
                return

            item = inventory[item_name]
            available_quantity = item.get("quantity", item) if isinstance(item, dict) else item

            # Si la quantité n'est pas spécifiée, supprimer tout
            delete_quantity = available_quantity if quantity is None else quantity
            if delete_quantity > available_quantity:
                error_embed = discord.Embed(
                    title="❌ Erreur",
                    description="Vous n'avez pas autant d'exemplaires de cet item.",
                    color=0xff0000
                )
                await ctx.reply(embed=error_embed)
                return

            # Créer l'embed de confirmation
            confirm_embed = discord.Embed(
                title="⚠️ Confirmation de suppression",
                description=f"Êtes-vous sûr de vouloir supprimer {delete_quantity}x {item_name} ?\n"
                          f"Cette action est irréversible !",
                color=0xff9900
            )

            # Créer les boutons de confirmation
            class ConfirmationView(discord.ui.View):
                def __init__(self, user):
                    super().__init__(timeout=30)
                    self.value = None
                    self.user = user

                @discord.ui.button(label="✅ Confirmer", style=discord.ButtonStyle.danger)
                async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != self.user:
                        await interaction.response.send_message("❌ Vous n'êtes pas le propriétaire de cette annonce.", ephemeral=True)
                        return
                    self.value = True
                    self.stop()

                @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
                async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user != self.user:
                        await interaction.response.send_message("❌ Vous n'êtes pas le propriétaire de cette annonce.", ephemeral=True)
                        return
                    self.value = False
                    self.stop()

            view = ConfirmationView(ctx.author)
            message = await ctx.reply(embed=confirm_embed, view=view)
            
            # Attendre la réponse
            await view.wait()
            
            if view.value is None:
                timeout_embed = discord.Embed(
                    title="⏰ Temps écoulé",
                    description="La suppression a été annulée.",
                    color=0xff0000
                )
                await message.edit(embed=timeout_embed, view=None)
            elif view.value:
                # Supprimer les items
                if isinstance(item, dict):
                    item["quantity"] = available_quantity - delete_quantity
                    if item["quantity"] <= 0:
                        del inventory[item_name]
                else:
                    inventory[item_name] = available_quantity - delete_quantity
                    if inventory[item_name] <= 0:
                        del inventory[item_name]

                update_inventaire(str(ctx.guild.id), str(ctx.author.id), inventory)

                success_embed = discord.Embed(
                    title="✅ Items supprimés",
                    description=f"{delete_quantity}x {item_name} ont été supprimés de votre inventaire.",
                    color=0x2ecc71
                )
                await message.edit(embed=success_embed, view=None)
            else:
                cancel_embed = discord.Embed(
                    title="❌ Suppression annulée",
                    description="Les items n'ont pas été supprimés.",
                    color=0xff0000
                )
                await message.edit(embed=cancel_embed, view=None)

        except Exception as e:
            print(f"Erreur lors de la suppression: {e}")
            error_embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de la suppression des items.",
                color=0xff0000
            )
            await ctx.reply(embed=error_embed)

    def get_wallet_bank(self, guild_id: str, user_id: str) -> tuple[int, int]:
        """Récupère le portefeuille et la banque d'un utilisateur"""
        result = fetch_one("""
            SELECT wallet, bank FROM users 
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        
        if not result:
            # Initialiser l'utilisateur avec des valeurs par défaut
            execute_query("""
                INSERT INTO users (guild_id, user_id, wallet, bank)
                VALUES (?, ?, 0, 0)
            """, (guild_id, user_id))
            return (0, 0)
        
        return result

    def get_user_stats(self, guild_id: str, user_id: str) -> dict:
        """Récupère les statistiques d'un utilisateur"""
        result = fetch_one("""
            SELECT total_sales, total_purchases, items_sold, items_bought, 
                   money_earned, money_spent, flash_sales 
            FROM user_stats 
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        
        if not result:
            # Initialiser les stats avec des valeurs par défaut
            default_stats = {
                "total_sales": 0,
                "total_purchases": 0,
                "items_sold": 0,
                "items_bought": 0,
                "money_earned": 0,
                "money_spent": 0,
                "flash_sales": 0
            }
            execute_query("""
                INSERT INTO user_stats 
                (guild_id, user_id, total_sales, total_purchases, items_sold, 
                 items_bought, money_earned, money_spent, flash_sales)
                VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0)
            """, (guild_id, user_id))
            return default_stats
        
        return {
            "total_sales": result[0],
            "total_purchases": result[1],
            "items_sold": result[2],
            "items_bought": result[3],
            "money_earned": result[4],
            "money_spent": result[5],
            "flash_sales": result[6]
        }

    def update_user_stats(self, guild_id: str, user_id: str, stats: dict) -> None:
        """Met à jour les statistiques d'un utilisateur"""
        execute_query("""
            UPDATE user_stats 
            SET total_sales = ?, total_purchases = ?, items_sold = ?, 
                items_bought = ?, money_earned = ?, money_spent = ?, 
                flash_sales = ?
            WHERE guild_id = ? AND user_id = ?
        """, (
            stats["total_sales"],
            stats["total_purchases"],
            stats["items_sold"],
            stats["items_bought"],
            stats["money_earned"],
            stats["money_spent"],
            stats["flash_sales"],
            guild_id,
            user_id
        ))

    def check_and_complete_missions(self, guild_id: str, user_id: str, stats: dict) -> None:
        """Vérifie et complète les missions du marketplace"""
        # Récupérer les missions complétées
        completed_missions = fetch_all("""
            SELECT mission_id FROM completed_missions 
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        
        completed_ids = [mission[0] for mission in completed_missions] if completed_missions else []
        
        for mission in marketplace_missions:
            if mission["id"] in completed_ids:
                continue
                
            # Vérifier si la mission est complétée
            is_completed = False
            if mission["type"] == "unique_items":
                is_completed = stats["items_bought"] >= mission["requirement"]
            elif mission["type"] == "flash_sale":
                is_completed = stats["flash_sales"] >= mission["requirement"]
            elif mission["type"] == "total_spent":
                is_completed = stats["money_spent"] >= mission["requirement"]
                
            if is_completed:
                # Marquer la mission comme complétée
                execute_query("""
                    INSERT INTO completed_missions (guild_id, user_id, mission_id)
                    VALUES (?, ?, ?)
                """, (guild_id, user_id, mission["id"]))
                
                # Donner la récompense
                execute_query("""
                    UPDATE users 
                    SET wallet = wallet + ? 
                    WHERE guild_id = ? AND user_id = ?
                """, (mission["reward"], guild_id, user_id))

    def get_flash_sales(self) -> dict | None:
        """Récupère les ventes flash en cours"""
        result = fetch_one("""
            SELECT category, discount, start_time, duration 
            FROM flash_sales 
            WHERE start_time + duration > ?
        """, (int(datetime.now().timestamp()),))
        
        if not result:
            return None
            
        return {
            "category": result[0],
            "discount": result[1],
            "start_time": result[2],
            "duration": result[3]
        }

    def get_item_category(self, item_name: str) -> str:
        """Récupère la catégorie d'un item"""
        for category, items in catalogue_items.items():
            if item_name in items:
                return category.lower()
        return "divers"

    def calculate_market_price(self, item_name: str) -> int:
        """Calcule le prix moyen du marché pour un item"""
        result = fetch_one("""
            SELECT AVG(price_per_unit) 
            FROM marketplace_listings 
            WHERE item_name = ? AND created_at > ?
        """, (item_name, int((datetime.now() - timedelta(days=7)).timestamp())))
        
        if not result or not result[0]:
            # Si pas de prix récent, utiliser le prix catalogue
            for category, items in catalogue_items.items():
                if item_name in items:
                    return items[item_name]["price"]
            return 0
        
        return int(result[0])

    def get_user_collections(self, guild_id: str, user_id: str) -> list[dict]:
        """Récupère les collections complétées d'un utilisateur"""
        inventory = get_inventaire(guild_id, user_id)
        if not inventory:
            return []
            
        completed_collections = []
        for collection_name, collection_data in item_collections.items():
            has_all_items = True
            for item_name in collection_data["items"]:
                if item_name not in inventory:
                    has_all_items = False
                    break
                if isinstance(inventory[item_name], dict):
                    if inventory[item_name].get("quantity", 0) < 1:
                        has_all_items = False
                        break
                elif inventory[item_name] < 1:
                    has_all_items = False
                    break
                    
            if has_all_items:
                completed_collections.append({
                    "name": collection_name,
                    "emoji": collection_data["emoji"],
                    "bonus": collection_data["bonus"],
                    "bonus_type": collection_data["bonus_type"],
                    "bonus_value": collection_data["bonus_value"]
                })
            
        return completed_collections

    @commands.command(name="marketstats", aliases=["mpstats"])
    async def marketstats(self, ctx):
        """Voir vos statistiques du marketplace"""
        try:
            # Récupérer les stats
            stats = self.get_user_stats(str(ctx.guild.id), str(ctx.author.id))

            # Déterminer le niveau vendeur
            seller_level = 0
            for level, data in seller_levels.items():
                if stats["total_sales"] >= data["required_sales"]:
                    seller_level = level

            # Déterminer le niveau acheteur
            buyer_level = 0
            for level, data in buyer_levels.items():
                if stats["total_purchases"] >= data["required_purchases"]:
                    buyer_level = level

            # Créer l'embed
            embed = discord.Embed(
                title="📊 Statistiques Marketplace",
                description=f"Statistiques de {ctx.author.name}",
                color=0x000000
            )

            # Section vendeur
            seller_data = seller_levels[seller_level]
            next_seller_level = seller_level + 1 if seller_level < max(seller_levels.keys()) else None

            seller_info = [
                f"**Niveau actuel :** {seller_data['emoji']} {seller_data['name']}",
                f"**Bonus de vente :** +{int(seller_data['bonus']*100)}%",
                f"**Ventes totales :** {stats['total_sales']}",
                f"**Items vendus :** {stats['items_sold']}",
                f"**Gains totaux :** {format_price(stats['money_earned'])}"
            ]

            if next_seller_level:
                next_data = seller_levels[next_seller_level]
                remaining_sales = next_data["required_sales"] - stats["total_sales"]
                seller_info.append(f"\n**Prochain niveau :** {next_data['emoji']} {next_data['name']}")
                seller_info.append(f"**Ventes restantes :** {remaining_sales}")

            embed.add_field(
                name="📈 Profil Vendeur",
                value="\n".join(seller_info),
                inline=False
            )

            # Section acheteur
            buyer_data = buyer_levels[buyer_level]
            next_buyer_level = buyer_level + 1 if buyer_level < max(buyer_levels.keys()) else None

            buyer_info = [
                f"**Niveau actuel :** {buyer_data['emoji']} {buyer_data['name']}",
                f"**Cashback :** {int(buyer_data['cashback']*100)}%",
                f"**Achats totaux :** {stats['total_purchases']}",
                f"**Items achetés :** {stats['items_bought']}",
                f"**Dépenses totales :** {format_price(stats['money_spent'])}",
                f"**Ventes flash :** {stats['flash_sales']}"
            ]

            if next_buyer_level:
                next_data = buyer_levels[next_buyer_level]
                remaining_purchases = next_data["required_purchases"] - stats["total_purchases"]
                buyer_info.append(f"\n**Prochain niveau :** {next_data['emoji']} {next_data['name']}")
                buyer_info.append(f"**Achats restants :** {remaining_purchases}")

            embed.add_field(
                name="🛍️ Profil Acheteur",
                value="\n".join(buyer_info),
                inline=False
            )

            # Section collections
            collections = self.get_user_collections(str(ctx.guild.id), str(ctx.author.id))
            if collections:
                collections_info = []
                for collection in collections:
                    collections_info.append(
                        f"{collection['emoji']} **{collection['name']}**\n"
                        f"• {collection['bonus']}"
                    )
                embed.add_field(
                    name="🎭 Collections complétées",
                    value="\n\n".join(collections_info),
                    inline=False
                )

            await ctx.reply(embed=embed)

        except Exception as e:
            print(f"Erreur lors de l'affichage des statistiques: {e}")
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de l'affichage de vos statistiques.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

    @commands.command(name="recreate_marketplace", hidden=True)
    @commands.is_owner()
    async def recreate_marketplace(self, ctx):
        """Recrée la table marketplace_listings (Admin uniquement)"""
        try:
            # Sauvegarder les données existantes
            old_listings = fetch_all("SELECT * FROM marketplace_listings", ())
            
            # Supprimer l'ancienne table
            execute_query("DROP TABLE IF EXISTS marketplace_listings")
            
            # Créer la nouvelle table
            execute_query("""
                CREATE TABLE marketplace_listings (
                    listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT,
                    seller_id TEXT,
                    item_name TEXT,
                    quantity INTEGER,
                    price_per_unit INTEGER,
                    created_at INTEGER,
                    expires_at INTEGER
                )
            """)
            
            # Restaurer les données
            if old_listings:
                for listing in old_listings:
                    execute_query("""
                        INSERT INTO marketplace_listings
                        (guild_id, seller_id, item_name, quantity, price_per_unit, created_at, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, listing[1:])  # Skip the old id column
            
            await ctx.reply("✅ Table marketplace_listings recréée avec succès !")
            
        except Exception as e:
            print(f"Erreur lors de la recréation de la table: {e}")
            error_embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur est survenue lors de la recréation de la table.",
                color=0xff0000
            )
            await ctx.reply(embed=error_embed)

async def setup(bot):
    await bot.add_cog(Marketplace(bot)) 