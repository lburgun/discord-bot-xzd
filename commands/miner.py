import discord
from discord.ext import commands
from database import execute_query, fetch_one, fetch_all, get_inventaire, update_inventaire
import random
from typing import Dict, List, Tuple
from datetime import datetime
import json

# Configuration des minerais et leurs prix
MINERALS = {
    "Charbon": {"price": 100, "weight": 45, "emoji": "⚫"},  # 45% de chance
    "Fer": {"price": 250, "weight": 30, "emoji": "⚪"},      # 30% de chance
    "Or": {"price": 500, "weight": 15, "emoji": "🟡"},       # 15% de chance
    "Diamant": {"price": 1000, "weight": 7, "emoji": "💎"},  # 7% de chance
    "Rubis": {"price": 2000, "weight": 3, "emoji": "❤️"}     # 3% de chance
}

# Images pour les différents moments de la journée
MINING_DAY_IMAGE = "https://media.discordapp.net/attachments/1295827543563309177/1389000348328263741/istockphoto-1455958810-170667a.jpg?ex=686306e1&is=6861b561&hm=a72822190678186a3eb2999d2adb7e695690193f264bd7c2755acbcb41f6d441&=&format=webp&width=776&height=349"
MINING_NIGHT_IMAGE = "https://cdn.discordapp.com/attachments/1295827543563309177/1389000348592509139/mine-or-chariot-plein-lingots-or-rails_107791-15715.png?ex=686306e1&is=6861b561&hm=2354ef4a0c4b6c42feaae1dbfff3ed8f3a76202309e21586db808ae290b554f4&"
WAGON_IMAGE = "https://cdn.discordapp.com/attachments/1295827543563309177/1389000347934265495/7183992.webp?ex=686306e1&is=6861b561&hm=97989c61716bf4e090101a91808b6aaa2460c7b4ca02e3bf6a8873b0af4a25c5&"

def is_daytime() -> bool:
    """Retourne True si c'est le jour (entre 6h et 20h), False sinon"""
    current_hour = datetime.now().hour
    return 6 <= current_hour < 20

class MineralSelect(discord.ui.Select):
    def __init__(self, minerals: Dict[str, int], view: 'WagonView'):
        self.wagon_view = view
        options = []
        for mineral, quantity in minerals.items():
            if quantity > 0:
                options.append(
                    discord.SelectOption(
                        label=f"{mineral} (x{quantity})",
                        value=mineral,
                        description=f"Prix unitaire: {MINERALS[mineral]['price']} coins",
                        emoji=MINERALS[mineral]["emoji"]
                    )
                )
        
        super().__init__(
            placeholder="Choisissez un minerai à vendre",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        mineral = self.values[0]
        await self.wagon_view.show_quantity_modal(interaction, mineral)

class QuantityModal(discord.ui.Modal):
    def __init__(self, mineral: str, max_quantity: int, view: 'WagonView'):
        super().__init__(title="Vendre des minerais")
        self.mineral = mineral
        self.max_quantity = max_quantity
        self.wagon_view = view

        self.quantity = discord.ui.TextInput(
            label=f"Quantité de {mineral} à vendre (max: {max_quantity})",
            placeholder="Entrez un nombre",
            min_length=1,
            max_length=len(str(max_quantity)),
            required=True
        )
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity.value)
            if quantity <= 0 or quantity > self.max_quantity:
                await interaction.response.send_message(
                    f"❌ La quantité doit être entre 1 et {self.max_quantity}.",
                    ephemeral=True
                )
                return

            # Mettre à jour l'inventaire
            inventory = get_inventaire(str(interaction.guild_id), str(interaction.user.id))
            if "minerals" not in inventory:
                inventory["minerals"] = {}
            
            if self.mineral not in inventory["minerals"]:
                await interaction.response.send_message(
                    "❌ Vous n'avez plus ce minerai dans votre wagon.",
                    ephemeral=True
                )
                return

            if inventory["minerals"][self.mineral] < quantity:
                await interaction.response.send_message(
                    f"❌ Vous n'avez que {inventory['minerals'][self.mineral]} {self.mineral}.",
                    ephemeral=True
                )
                return

            inventory["minerals"][self.mineral] -= quantity
            if inventory["minerals"][self.mineral] <= 0:
                del inventory["minerals"][self.mineral]
            
            update_inventaire(str(interaction.guild_id), str(interaction.user.id), inventory)

            # Calculer et ajouter l'argent
            total_price = quantity * MINERALS[self.mineral]["price"]
            execute_query("""
                UPDATE users 
                SET wallet = wallet + ? 
                WHERE guild_id = ? AND user_id = ?
            """, (total_price, str(interaction.guild_id), str(interaction.user.id)))

            # Créer un embed pour le résultat de la vente
            embed = discord.Embed(
                title="💰 Vente de minerais",
                description=f"Vous avez vendu {quantity} {MINERALS[self.mineral]['emoji']} {self.mineral} !",
                color=0x000000
            )
            embed.add_field(
                name="Prix unitaire",
                value=f"{MINERALS[self.mineral]['price']} coins",
                inline=True
            )
            embed.add_field(
                name="Quantité vendue",
                value=str(quantity),
                inline=True
            )
            embed.add_field(
                name="Total reçu",
                value=f"{total_price} coins",
                inline=True
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.wagon_view.update_view(interaction)

        except ValueError:
            await interaction.response.send_message(
                "❌ Veuillez entrer un nombre valide.",
                ephemeral=True
            )

class WagonView(discord.ui.View):
    def __init__(self, minerals: Dict[str, int], ctx):
        super().__init__()
        self.minerals = minerals
        self.ctx = ctx
        self.message = None
        self.add_item(MineralSelect(minerals, self))

    async def show_quantity_modal(self, interaction: discord.Interaction, mineral: str):
        inventory = get_inventaire(str(interaction.guild_id), str(interaction.user.id))
        if "minerals" not in inventory or mineral not in inventory["minerals"]:
            await interaction.response.send_message(
                "❌ Vous n'avez plus ce minerai dans votre wagon.",
                ephemeral=True
            )
            return

        modal = QuantityModal(mineral, inventory["minerals"][mineral], self)
        await interaction.response.send_modal(modal)

    async def update_view(self, interaction: discord.Interaction):
        # Récupérer les minerais mis à jour
        inventory = get_inventaire(str(interaction.guild_id), str(interaction.user.id))
        self.minerals = inventory.get("minerals", {})

        # Créer le nouvel embed
        embed = discord.Embed(
            title="🚂 Contenu de votre wagon",
            description="Voici les minerais stockés dans votre wagon :",
            color=0x000000
        )
        embed.set_image(url=WAGON_IMAGE)

        total_value = 0
        for mineral, quantity in self.minerals.items():
            value = quantity * MINERALS[mineral]["price"]
            total_value += value
            embed.add_field(
                name=f"{MINERALS[mineral]['emoji']} {mineral} (x{quantity})",
                value=f"Valeur: {value} coins",
                inline=True
            )

        if not self.minerals:
            embed.add_field(
                name="Wagon vide",
                value="Utilisez +miner pour obtenir des minerais !",
                inline=False
            )

        embed.add_field(
            name="💰 Valeur totale",
            value=f"{total_value} coins",
            inline=False
        )

        wagon = inventory.get("Wagon", {})
        uses_left = wagon.get("uses_left", 0) if isinstance(wagon, dict) else 0
        embed.set_footer(text=f"Utilisations restantes : {uses_left}/10")

        # Créer une nouvelle vue avec les minerais mis à jour
        new_view = WagonView(self.minerals, self.ctx)
        
        # Si le message existe déjà, le mettre à jour
        if self.message:
            await self.message.edit(embed=embed, view=new_view)
        else:
            self.message = await interaction.response.send_message(embed=embed, view=new_view)

class BuyWagonView(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="🚂 Acheter un wagon (5000 coins)", style=discord.ButtonStyle.green)
    async def buy_wagon(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Vérifier le solde de l'utilisateur
        balance = fetch_one("SELECT wallet FROM users WHERE user_id = ?", (interaction.user.id,))
        if not balance:
            await interaction.response.send_message("❌ Vous n'avez pas de compte. Utilisez +daily pour commencer.", ephemeral=True)
            return

        wallet = balance[0] if balance else 0
        if wallet < 5000:
            await interaction.response.send_message("❌ Vous n'avez pas assez d'argent pour acheter un wagon.", ephemeral=True)
            return

        # Effectuer l'achat
        execute_query("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", 
                     (5000, interaction.user.id))

        # Ajouter le wagon à l'inventaire
        execute_query("""
            INSERT INTO user_items (user_id, item_name, quantity, uses_left)
            VALUES (?, 'Wagon', 1, 10)
        """, (interaction.user.id,))

        await interaction.response.send_message("✅ Vous avez acheté un wagon pour 5000 coins !", ephemeral=True)
        self.stop()

class MinerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Créer les tables nécessaires
        execute_query("""
            CREATE TABLE IF NOT EXISTS wagon_minerals (
                user_id INTEGER,
                mineral TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, mineral)
            )
        """)

    def get_random_minerals(self) -> List[str]:
        """Retourne une liste de minerais aléatoires basée sur leur rareté"""
        minerals = []
        for _ in range(random.randint(1, 3)):  # 1 à 3 minerais par minage
            total_weight = sum(m["weight"] for m in MINERALS.values())
            r = random.uniform(0, total_weight)
            cumulative_weight = 0
            for mineral, data in MINERALS.items():
                cumulative_weight += data["weight"]
                if r <= cumulative_weight:
                    minerals.append(mineral)
                    break
        return minerals

    @commands.command()
    async def miner(self, ctx):
        """Miner des minerais avec votre wagon"""
        # Vérifier si l'utilisateur a un wagon
        inventory = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
        if "Wagon" not in inventory:
            await ctx.send("❌ Vous n'avez pas de wagon ! Utilisez +buy pour en acheter un.")
            return

        wagon = inventory["Wagon"]
        if not isinstance(wagon, dict) or wagon.get("uses_left", 0) <= 0:
            await ctx.send("❌ Votre wagon n'a plus d'utilisations ! Achetez-en un nouveau.")
            return

        # Obtenir des minerais aléatoires
        new_minerals = self.get_random_minerals()
        
        # Mettre à jour l'inventaire
        if "minerals" not in inventory:
            inventory["minerals"] = {}
        
        for mineral in new_minerals:
            if mineral in inventory["minerals"]:
                inventory["minerals"][mineral] += 1
            else:
                inventory["minerals"][mineral] = 1

        # Réduire les utilisations du wagon
        wagon["uses_left"] -= 1
        inventory["Wagon"] = wagon
        
        update_inventaire(str(ctx.guild.id), str(ctx.author.id), inventory)

        # Créer l'embed de résultat
        embed = discord.Embed(
            title="⛏️ Résultats du minage",
            description="Voici ce que vous avez trouvé :",
            color=0x000000
        )
        embed.set_image(url=MINING_DAY_IMAGE if is_daytime() else MINING_NIGHT_IMAGE)

        for mineral in new_minerals:
            embed.add_field(
                name=f"{MINERALS[mineral]['emoji']} {mineral}",
                value=f"Prix: {MINERALS[mineral]['price']} coins",
                inline=True
            )

        embed.set_footer(text=f"Utilisations restantes du wagon : {wagon['uses_left']}/10")
        await ctx.send(embed=embed)

    @commands.command()
    async def wagon(self, ctx):
        """Voir le contenu de votre wagon et vendre des minerais"""
        # Vérifier si l'utilisateur a un wagon
        inventory = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
        if "Wagon" not in inventory:
            await ctx.send("❌ Vous n'avez pas de wagon ! Utilisez +buy pour en acheter un.")
            return

        minerals = inventory.get("minerals", {})
        view = WagonView(minerals, ctx)
        
        embed = discord.Embed(
            title="🚂 Contenu de votre wagon",
            description="Voici les minerais stockés dans votre wagon :",
            color=0x000000
        )
        embed.set_image(url=WAGON_IMAGE)

        total_value = 0
        for mineral, quantity in minerals.items():
            value = quantity * MINERALS[mineral]["price"]
            total_value += value
            embed.add_field(
                name=f"{MINERALS[mineral]['emoji']} {mineral} (x{quantity})",
                value=f"Valeur: {value} coins",
                inline=True
            )

        if not minerals:
            embed.add_field(
                name="Wagon vide",
                value="Utilisez +miner pour obtenir des minerais !",
                inline=False
            )

        embed.add_field(
            name="💰 Valeur totale",
            value=f"{total_value} coins",
            inline=False
        )

        wagon = inventory.get("Wagon", {})
        uses_left = wagon.get("uses_left", 0) if isinstance(wagon, dict) else 0
        embed.set_footer(text=f"Utilisations restantes : {uses_left}/10")

        message = await ctx.send(embed=embed, view=view)
        view.message = message

async def setup(bot):
    await bot.add_cog(MinerCog(bot)) 