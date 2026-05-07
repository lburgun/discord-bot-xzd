import discord
from discord.ext import commands
from database import execute_query, fetch_one, fetch_all, get_inventaire, update_inventaire, get_user_wallet
# import json  # Inutilisé

shop_items = [
    {
        "name": "Téléphone",
        "emoji": "📱",
        "price": 30000,
        "description": "Un téléphone completement coupé du reseau mondiale.",
        "max_quantity": 1  # Limite à 1 téléphone par utilisateur
    },
    {
        "name": "Wagon",
        "emoji": "🚃",
        "price": 6500,
        "description": "Un wagon robuste pour transporter vos minerais a la mine.",
        "max_quantity": 1  # Limite à 1 wagon par utilisateur
    },
    {
        "name": "Bouteille d'eau",
        "emoji": "💧",
        "price": 1000,
        "description": "Une bouteille d'eau étrange.",
        "max_quantity": None  # Pas de limite
    }
]

class ShopSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{item['name']} - {item['price']} 💰",
                description=item['description'],
                emoji=item['emoji'],
                value=item["name"]
            ) for item in shop_items
        ]
        
        super().__init__(
            placeholder="Choisissez un objet à acheter",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await self.handle_purchase(interaction, self.values[0])

    async def handle_purchase(self, interaction: discord.Interaction, item_name: str):
        item = next((item for item in shop_items if item["name"] == item_name), None)
        if not item:
            await interaction.response.send_message("❌ Une erreur est survenue.", ephemeral=True)
            return

        # Vérifier le solde de l'utilisateur
        guild_id, user_id = str(interaction.guild_id), str(interaction.user.id)
        wallet = get_user_wallet(guild_id, user_id)

        if wallet < item["price"]:
            await interaction.response.send_message(f"❌ Vous n'avez pas assez d'argent. Il vous manque {item['price'] - wallet} coins.", ephemeral=True)
            return

        # Vérifier les limites de quantité
        inventory = get_inventaire(guild_id, user_id)
        current_quantity = 0
        if item["name"] in inventory:
            if isinstance(inventory[item["name"]], dict):
                current_quantity = inventory[item["name"]].get("quantity", 0)
            else:
                current_quantity = inventory[item["name"]]
            
        if item["max_quantity"] is not None and current_quantity >= item["max_quantity"]:
            await interaction.response.send_message(f"❌ Vous ne pouvez pas avoir plus de {item['max_quantity']} {item['name']}!", ephemeral=True)
            return

        try:
            # Différer la réponse
            await interaction.response.defer()

            # Effectuer l'achat
            execute_query("UPDATE users SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", 
                         (item["price"], guild_id, user_id))

            # Mettre à jour l'inventaire
            if item["name"] == "Wagon":
                inventory[item["name"]] = {
                    "quantity": current_quantity + 1,
                    "uses_left": 10
                }
            else:
                if item["name"] in inventory:
                    if isinstance(inventory[item["name"]], dict):
                        inventory[item["name"]]["quantity"] += 1
                    else:
                        inventory[item["name"]] = {
                            "quantity": int(inventory[item["name"]]) + 1
                        }
                else:
                    inventory[item["name"]] = {
                        "quantity": 1
                    }
            
            update_inventaire(guild_id, user_id, inventory)

            # Mettre à jour l'embed avec le nouveau solde
            embed = discord.Embed(
                title="🛍️ Magasin",
                description="Sélectionnez l'objet que vous souhaitez acheter :",
                color=0x000000
            )

            for shop_item in shop_items:
                max_qty = f" (Max: {shop_item['max_quantity']})" if shop_item['max_quantity'] is not None else ""
                embed.add_field(
                    name=f"{shop_item['emoji']} {shop_item['name']} - {shop_item['price']} 💰{max_qty}",
                    value=shop_item['description'],
                    inline=False
                )

            # Afficher le nouveau solde
            solde_restant = get_user_wallet(guild_id, user_id)
            embed.add_field(name="💰 Votre solde", value=f"{solde_restant} coins", inline=False)

            # Créer une nouvelle vue avec un nouveau menu
            view = ShopView()
            
            # Mettre à jour le message original
            await interaction.edit_original_response(embed=embed, view=view)
            
            # Envoyer un message de confirmation
            await interaction.followup.send(
                f"{item['emoji']} Vous avez acheté {item['name']} pour {item['price']} coins !\n"
                f"💰 Solde restant : {solde_restant} coins", 
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send("❌ Une erreur est survenue lors de l'achat.", ephemeral=True)

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(ShopSelect())

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        

    @commands.command(name="shop")
    async def shop_command(self, ctx):
        """Acheter un objet du magasin"""
        embed = discord.Embed(
            title="🛍️ Magasin",
            description="Sélectionnez l'objet que vous souhaitez acheter :",
            color=0x000000
        )

        # Afficher les objets disponibles
        for item in shop_items:
            max_qty = f" (Max: {item['max_quantity']})" if item['max_quantity'] is not None else ""
            embed.add_field(
                name=f"{item['emoji']} {item['name']} - {item['price']} 💰{max_qty}",
                value=item['description'],
                inline=False
            )

        # Afficher le solde actuel
        wallet = get_user_wallet(str(ctx.guild.id), str(ctx.author.id))
        embed.add_field(name="💰 Votre solde", value=f"{wallet} coins", inline=False)

        view = ShopView()
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Shop(bot))
