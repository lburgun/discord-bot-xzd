from discord.ext import commands
import discord
from discord import ui
from database import get_inventaire
from .catalogue import catalogue_items, category_emojis, rarity_indicators
from .shop import shop_items

class CategorySelect(ui.Select):
    def __init__(self, categories, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=name,
                emoji=category_emojis.get(name, "📦"),
                description=f"{len(items)} items" if items else "Vide",
                value=name
            ) for name, items in categories.items() if name != "Tout"
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
        category = self.values[0] if self.values else "Tout"
        await self.parent_view.show_category(interaction, category)

class InventoryView(ui.View):
    def __init__(self, categories, total_value, timeout=180):
        super().__init__(timeout=timeout)
        self.categories = categories
        self.total_value = total_value
        self.add_item(CategorySelect(categories, self))

    def format_number(self, number):
        return "{:,}".format(number).replace(",", " ")

    def get_category_embed(self, category_name: str):
        embed = discord.Embed(
            title=f"🎒 Inventaire",
            color=0x000000
        )
        
        if category_name == "Tout":
            # Afficher toutes les catégories
            for cat_name, items in self.categories.items():
                if cat_name != "Tout" and items:
                    items_text = "\n\n".join(items)
                    if items_text:
                        embed.add_field(
                            name=f"{category_emojis.get(cat_name, '📦')} {cat_name}",
                            value=items_text,
                            inline=False
                        )
        else:
            # Afficher une seule catégorie
            items = self.categories.get(category_name, [])
            if items:
                embed.add_field(
                    name=f"{category_emojis.get(category_name, '📦')} {category_name}",
                    value="\n\n".join(items),
                    inline=False
                )
            else:
                embed.description = f"Aucun objet dans la catégorie {category_name}"

        embed.set_footer(text=f"💰 Valeur totale : {self.format_number(self.total_value)} coins")
        return embed

    async def show_category(self, interaction: discord.Interaction, category_name: str):
        await interaction.response.edit_message(embed=self.get_category_embed(category_name))

class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def format_number(self, number):
        """Formate un nombre avec des séparateurs de milliers"""
        return "{:,}".format(number).replace(",", " ")

    @commands.command(aliases=["inv", "i"])
    async def inventory(self, ctx):
        """Affiche l'inventaire du joueur"""
        inventory = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
        
        if not inventory:
            embed = discord.Embed(
                title="🎒 Inventaire",
                description="❌ Votre inventaire est vide !",
                color=0x000000
            )
            await ctx.send(embed=embed)
            return

        # Nettoyer l'inventaire des items avec quantité 0
        cleaned_inventory = {}
        for item_name, quantity in inventory.items():
            if isinstance(quantity, dict):
                if quantity.get("quantity", 0) > 0:
                    cleaned_inventory[item_name] = quantity
            elif quantity > 0:
                cleaned_inventory[item_name] = quantity

        # Si l'inventaire est vide après nettoyage
        if not cleaned_inventory:
            embed = discord.Embed(
                title="🎒 Inventaire",
                description="❌ Votre inventaire est vide !",
                color=0x000000
            )
            await ctx.send(embed=embed)
            return

        # Mettre à jour l'inventaire si des items ont été supprimés
        if len(cleaned_inventory) != len(inventory):
            from database import update_inventaire
            update_inventaire(str(ctx.guild.id), str(ctx.author.id), cleaned_inventory)
            inventory = cleaned_inventory

        # Organiser les items par catégorie
        categories = {
            "Tout": [],
            "Véhicules": [],
            "Propriétés": [],
            "Objets Tech": [],
            "Art & Collection": [],
            "Mode & Accessoires": [],
            "Animaux": [],
            "Sports & Loisirs": [],
            "Utilitaires": []  # Pour les items du shop
        }
        total_value = 0

        # D'abord, traiter les items du shop
        for item_name, quantity in inventory.items():
            # Vérifier si c'est un item du shop
            shop_item = next((item for item in shop_items if item["name"] == item_name), None)
            if shop_item:
                # Extraire la quantité correctement
                if isinstance(quantity, dict):
                    item_quantity = quantity.get("quantity", 0)
                    if "uses_left" in quantity:  # Pour les wagons
                        item_text = f"{shop_item['emoji']} **{item_name}**\n└ × {item_quantity} (🔄 {quantity['uses_left']} utilisations restantes)"
                    else:
                        item_text = f"{shop_item['emoji']} **{item_name}**\n└ × {item_quantity}"
                else:
                    item_quantity = quantity
                    item_text = f"{shop_item['emoji']} **{item_name}**\n└ × {item_quantity}"
                
                categories["Utilitaires"].append(item_text)
                total_value += shop_item["price"] * item_quantity
                continue

            # Si ce n'est pas un item du shop, chercher dans le catalogue
            found_item = None
            item_category = None
            item_rarity = None
            
            # Essayer de trouver par nom exact ou par format "Nom Rareté"
            for category, items in catalogue_items.items():
                for item in items:
                    # Cas 1: Match direct (ex: "Smartphone")
                    if item["name"] == item_name:
                        found_item = item
                        item_category = category
                        item_rarity = "common" # Default if not specified
                        break
                    # Cas 2: Match avec rareté (ex: "Smartphone legendary")
                    for r in item["rarities"]:
                        if f"{item['name']} {r}" == item_name:
                            found_item = item
                            item_category = category
                            item_rarity = r
                            break
                    if found_item: break
                if found_item: break

            if found_item and item_category:
                # Extraire la quantité
                if isinstance(quantity, dict):
                    item_quantity = int(quantity.get("quantity", 0))
                else:
                    item_quantity = int(quantity)

                # Calculer la valeur
                item_value = found_item["price"] * item_quantity
                total_value += item_value

                # Ajouter l'item à sa catégorie
                display_name = found_item["variants"].get(item_rarity, found_item["name"])
                item_text = (
                    f"{found_item['emoji']} **{display_name}**\n"
                    f"└ {rarity_indicators.get(item_rarity, '⚪')} × {item_quantity}"
                )
                categories[item_category].append(item_text)

        # Créer la vue avec les catégories non vides
        categories = {k: v for k, v in categories.items() if v or k == "Tout"}
        view = InventoryView(categories, total_value)

        # Afficher l'embed initial avec toutes les catégories
        await ctx.send(embed=view.get_category_embed("Tout"), view=view)

async def setup(bot):
    await bot.add_cog(Inventory(bot))
