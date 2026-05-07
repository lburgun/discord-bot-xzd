import discord
from discord.ext import commands
import random
from datetime import datetime
from database import execute_query, fetch_one, fetch_all, get_inventaire, update_inventaire, get_user_wallet, update_wallet

# Dictionnaire des catégories avec leurs émojis
category_emojis = {
    "Véhicules": "🚗",
    "Propriétés": "🏘️",
    "Objets Tech": "📱",
    "Art & Collection": "🎨",
    "Mode & Accessoires": "👔",
    "Animaux": "🐾",
    "Sports & Loisirs": "⚽",
    "Sécurité & Armes": "🛡️"
}

# Indicateurs de rareté
rarity_indicators = {
    "common": "⚪",
    "uncommon": "🟢",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡"
}

# Probabilités d'obtention par rareté (en %)
rarity_chances = {
    "common": 50,
    "uncommon": 30,
    "rare": 15,
    "epic": 4,
    "legendary": 1
}

catalogue_items = {
    "Véhicules": [
        {
            "name": "Vélo",
            "emoji": "🚲",
            "price": 500,
            "description": "Un vélo pour se déplacer",
            "rarities": ["common", "uncommon", "rare"],
            "variants": {
                "common": "Vélo classique",
                "uncommon": "Vélo électrique",
                "rare": "Vélo en carbone"
            }
        },
        {
            "name": "Voiture",
            "emoji": "🚗",
            "price": 15000,
            "description": "Une voiture pour rouler en style",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Voiture citadine",
                "uncommon": "Berline confortable",
                "rare": "SUV luxueux",
                "epic": "Voiture de sport",
                "legendary": "Supercar exclusive"
            }
        },
        {
            "name": "Moto",
            "emoji": "🏍️",
            "price": 8000,
            "description": "Une moto puissante",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "Scooter urbain",
                "uncommon": "Moto routière",
                "rare": "Moto sportive",
                "epic": "Superbike"
            }
        },
        {
            "name": "Hélicoptère",
            "emoji": "🚁",
            "price": 100000,
            "description": "Pour voler avec style",
            "rarities": ["rare", "epic", "legendary"],
            "variants": {
                "rare": "Hélicoptère civil",
                "epic": "Hélicoptère luxe",
                "legendary": "Hélicoptère militaire"
            }
        }
    ],
    "Propriétés": [
        {
            "name": "Appartement",
            "emoji": "🏢",
            "price": 50000,
            "description": "Un appartement en ville",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "Studio simple",
                "uncommon": "2 pièces moderne",
                "rare": "Duplex spacieux",
                "epic": "Penthouse luxueux"
            }
        },
        {
            "name": "Maison",
            "emoji": "🏡",
            "price": 150000,
            "description": "Une maison avec jardin",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Petite maison",
                "uncommon": "Maison familiale",
                "rare": "Grande villa",
                "epic": "Manoir historique",
                "legendary": "Château privé"
            }
        },
        {
            "name": "Commerce",
            "emoji": "🏪",
            "price": 80000,
            "description": "Un local commercial",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "Petit commerce",
                "uncommon": "Boutique en ville",
                "rare": "Grand magasin",
                "epic": "Centre commercial"
            }
        },
        {
            "name": "Île",
            "emoji": "🏝️",
            "price": 500000,
            "description": "Votre paradis privé",
            "rarities": ["rare", "epic", "legendary"],
            "variants": {
                "rare": "Petit îlot",
                "epic": "Île tropicale",
                "legendary": "Archipel privé"
            }
        }
    ],
    "Objets Tech": [
        {
            "name": "Ordinateur",
            "emoji": "💻",
            "price": 2000,
            "description": "Un ordinateur performant",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "PC bureautique",
                "uncommon": "PC multimédia",
                "rare": "PC gaming",
                "epic": "Station de travail pro"
            }
        },
        {
            "name": "Smartphone",
            "emoji": "📱",
            "price": 1000,
            "description": "Un téléphone intelligent",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Modèle basique",
                "uncommon": "Milieu de gamme",
                "rare": "Haut de gamme",
                "epic": "Édition limitée",
                "legendary": "Prototype futuriste"
            }
        },
        {
            "name": "Drone",
            "emoji": "🛸",
            "price": 5000,
            "description": "Un drone pour filmer",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Mini drone",
                "uncommon": "Drone caméra HD",
                "rare": "Drone professionnel",
                "epic": "Drone cinéma 8K",
                "legendary": "Drone militaire"
            }
        },
        {
            "name": "Robot",
            "emoji": "🤖",
            "price": 10000,
            "description": "Un assistant robotique",
            "rarities": ["uncommon", "rare", "epic", "legendary"],
            "variants": {
                "uncommon": "Robot ménager",
                "rare": "Robot assistant",
                "epic": "Androïde avancé",
                "legendary": "IA autonome"
            }
        }
    ],
    "Art & Collection": [
        {
            "name": "Tableau",
            "emoji": "🎨",
            "price": 10000,
            "description": "Une œuvre d'art unique",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Reproduction classique",
                "uncommon": "Œuvre contemporaine",
                "rare": "Pièce de collection",
                "epic": "Chef-d'œuvre signé",
                "legendary": "Œuvre de maître"
            }
        },
        {
            "name": "Sculpture",
            "emoji": "🗿",
            "price": 15000,
            "description": "Une sculpture artistique",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Sculpture moderne",
                "uncommon": "Statue en marbre",
                "rare": "Œuvre unique",
                "epic": "Pièce historique",
                "legendary": "Trésor antique"
            }
        },
        {
            "name": "Carte",
            "emoji": "🎴",
            "price": 1000,
            "description": "Une carte de collection",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Carte commune",
                "uncommon": "Carte spéciale",
                "rare": "Carte holographique",
                "epic": "Carte ultra-rare",
                "legendary": "Carte mythique"
            }
        },
        {
            "name": "Antiquité",
            "emoji": "⚱️",
            "price": 20000,
            "description": "Un objet ancien",
            "rarities": ["rare", "epic", "legendary"],
            "variants": {
                "rare": "Objet vintage",
                "epic": "Relique ancienne",
                "legendary": "Artéfact légendaire"
            }
        }
    ],
    "Mode & Accessoires": [
        {
            "name": "Montre",
            "emoji": "⌚",
            "price": 5000,
            "description": "Une montre élégante",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Montre classique",
                "uncommon": "Montre design",
                "rare": "Montre luxe",
                "epic": "Montre précieuse",
                "legendary": "Montre unique"
            }
        },
        {
            "name": "Sac",
            "emoji": "👜",
            "price": 3000,
            "description": "Un sac à main",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "Sac basique",
                "uncommon": "Sac tendance",
                "rare": "Sac designer",
                "epic": "Sac collection limitée"
            }
        },
        {
            "name": "Bijou",
            "emoji": "💎",
            "price": 8000,
            "description": "Un bijou précieux",
            "rarities": ["uncommon", "rare", "epic", "legendary"],
            "variants": {
                "uncommon": "Bijou argent",
                "rare": "Bijou or",
                "epic": "Bijou diamant",
                "legendary": "Bijou royal"
            }
        },
        {
            "name": "Costume",
            "emoji": "🥋",
            "price": 2000,
            "description": "Une tenue élégante",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "Costume basique",
                "uncommon": "Costume tendance",
                "rare": "Costume sur mesure",
                "epic": "Costume haute couture"
            }
        }
    ],
    "Animaux": [
        {
            "name": "Chat",
            "emoji": "🐱",
            "price": 1000,
            "description": "Un ami félin",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Chat domestique",
                "uncommon": "Chat de race",
                "rare": "Chat exotique",
                "epic": "Chat rare",
                "legendary": "Chat mythique"
            }
        },
        {
            "name": "Chien",
            "emoji": "🐕",
            "price": 1500,
            "description": "Un compagnon fidèle",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Chien croisé",
                "uncommon": "Chien de race",
                "rare": "Chien champion",
                "epic": "Chien d'exception",
                "legendary": "Chien légendaire"
            }
        },
        {
            "name": "Cheval",
            "emoji": "🐎",
            "price": 10000,
            "description": "Un noble destrier",
            "rarities": ["uncommon", "rare", "epic", "legendary"],
            "variants": {
                "uncommon": "Cheval de loisir",
                "rare": "Cheval de course",
                "epic": "Pur-sang",
                "legendary": "Cheval mythique"
            }
        },
        {
            "name": "Dragon",
            "emoji": "🐉",
            "price": 100000,
            "description": "Une créature légendaire",
            "rarities": ["rare", "epic", "legendary"],
            "variants": {
                "rare": "Petit dragon",
                "epic": "Dragon adulte",
                "legendary": "Dragon ancestral"
            }
        }
    ],
    "Sports & Loisirs": [
        {
            "name": "Raquette",
            "emoji": "🎾",
            "price": 500,
            "description": "Pour le tennis",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "Raquette débutant",
                "uncommon": "Raquette club",
                "rare": "Raquette pro",
                "epic": "Raquette champion"
            }
        },
        {
            "name": "Planche",
            "emoji": "🏄",
            "price": 1000,
            "description": "Pour le surf",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "Planche débutant",
                "uncommon": "Planche sport",
                "rare": "Planche pro",
                "epic": "Planche custom"
            }
        },
        {
            "name": "Console",
            "emoji": "🎮",
            "price": 3000,
            "description": "Pour le gaming",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Console standard",
                "uncommon": "Console pro",
                "rare": "Console collector",
                "epic": "Console limitée",
                "legendary": "Console unique"
            }
        },
        {
            "name": "Instrument",
            "emoji": "🎸",
            "price": 2000,
            "description": "Pour la musique",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Instrument débutant",
                "uncommon": "Instrument qualité",
                "rare": "Instrument pro",
                "epic": "Instrument vintage",
                "legendary": "Instrument historique"
            }
        }
    ],
    "Sécurité & Armes": [
        {
            "name": "Coffre-fort",
            "emoji": "🗄️",
            "price": 25000,
            "description": "Protège une partie de votre argent des voleurs",
            "rarities": ["common", "uncommon", "rare", "epic", "legendary"],
            "variants": {
                "common": "Petit coffre",
                "uncommon": "Coffre blindé",
                "rare": "Coffre encastré",
                "epic": "Coffre de banque",
                "legendary": "Chambre forte"
            }
        },
        {
            "name": "Arme à feu",
            "emoji": "🔫",
            "price": 50000,
            "description": "Permet de se défendre contre les voleurs (Permis requis !)",
            "rarities": ["rare", "epic", "legendary"],
            "variants": {
                "rare": "Pistolet",
                "epic": "Fusil",
                "legendary": "Arme lourde"
            }
        },
        {
            "name": "Alarme",
            "emoji": "🚨",
            "price": 15000,
            "description": "Prévient la police en cas d'intrusion",
            "rarities": ["common", "uncommon", "rare", "epic"],
            "variants": {
                "common": "Alarme basique",
                "uncommon": "Alarme connectée",
                "rare": "Alarme laser",
                "epic": "Système de sécurité IA"
            }
        }
    ]
}

class PurchaseSelect(discord.ui.Select):
    def __init__(self, items, category_name, multiplier):
        self.multiplier = multiplier
        self.category_name = category_name
        
        options = []
        for item in items:
            actual_price = int(item['price'] * multiplier)
            options.append(
                discord.SelectOption(
                    label=f"{item['name']} - {actual_price:,} 💰",
                    description=item['description'],
                    emoji=item['emoji'],
                    value=item["name"]
                )
            )
        super().__init__(placeholder="Choisissez un objet à acheter...", options=options)

    async def callback(self, interaction: discord.Interaction):
        item_name = self.values[0]
        view: CatalogueView = self.view
        
        # Trouver l'item
        found_item = None
        for category_items in catalogue_items.values():
            for item in category_items:
                if item["name"] == item_name:
                    found_item = item
                    break
            if found_item: break
            
        if not found_item:
            await interaction.response.send_message("❌ Cet objet n'existe plus.", ephemeral=True)
            return

        # Vérifier le solde
        guild_id, user_id = str(interaction.guild_id), str(interaction.user.id)
        wallet = get_user_wallet(guild_id, user_id)
        
        # Appliquer la fluctuation
        actual_price = int(found_item["price"] * self.multiplier)

        if wallet < actual_price:
            await interaction.response.send_message(f"❌ Vous n'avez pas assez d'argent ! Il vous manque {actual_price - wallet:,} 💰", ephemeral=True)
            return

        # Vérification des doublons (phone/wagon)
        inventory = get_inventaire(guild_id, user_id)
        is_phone = "phone" in item_name.lower() or "téléphone" in item_name.lower() or item_name.lower() == "smartphone"
        is_wagon = "wagon" in item_name.lower()
        
        if is_phone:
            if any(("phone" in k.lower() or "téléphone" in k.lower() or k.lower() == "smartphone") for k in inventory.keys()):
                await interaction.response.send_message("❌ Vous possédez déjà un téléphone !", ephemeral=True)
                return
        if is_wagon:
            if any("wagon" in k.lower() for k in inventory.keys()):
                await interaction.response.send_message("❌ Vous possédez déjà un wagon !", ephemeral=True)
                return

        # Vérifier si l'objet est sous commande de l'état
        now = int(datetime.now().timestamp())
        names_to_check = [found_item["name"]]
        if "variants" in found_item:
            names_to_check.extend(found_item["variants"].values())
            
        is_blocked = False
        for name in names_to_check:
            if fetch_one("SELECT order_id FROM state_orders WHERE guild_id = ? AND item_name = ? AND status = 'active' AND expires_at > ?", (guild_id, name, now)):
                is_blocked = True
                break
                
        if is_blocked:
            await interaction.response.send_message("❌ Cet objet est actuellement sous embargo de l'État (forte demande). Les usines sont en rupture de stock ! Essayez de l'acheter à d'autres joueurs sur le Marketplace (`+mp`).", ephemeral=True)
            return

        # Déterminer la rareté
        rarity_list = found_item["rarities"]
        chance_list = [rarity_chances[r] for r in rarity_list]
        obtained_rarity = random.choices(rarity_list, weights=chance_list)[0]
        variant_name = found_item["variants"][obtained_rarity]

        try:
            # Effectuer l'achat
            update_wallet(guild_id, user_id, -actual_price)
            
            # Mettre à jour l'inventaire
            # On utilise le format interne "BaseName Rarity" pour que inventory.py le reconnaisse
            internal_item_name = f"{found_item['name']} {obtained_rarity}"
            
            if internal_item_name in inventory:
                if isinstance(inventory[internal_item_name], dict):
                    inventory[internal_item_name]["quantity"] = int(inventory[internal_item_name].get("quantity", 0)) + 1
                else:
                    inventory[internal_item_name] = int(inventory[internal_item_name]) + 1
            else:
                inventory[internal_item_name] = {"quantity": 1, "rarity": obtained_rarity}
            
            update_inventaire(guild_id, user_id, inventory)

            # Message de succès (Public)
            new_wallet = wallet - actual_price
            view.user_balance = new_wallet
            
            embed_success = discord.Embed(
                title="✨ Achat réussi !",
                description=f"<@{interaction.user.id}> a obtenu : {found_item['emoji']} **{variant_name}**\nRareté : {rarity_indicators[obtained_rarity]}",
                color=0x00FF00
            )
            embed_success.set_footer(text=f"Nouveau solde : {new_wallet:,} coins")
            
            # 1. On met à jour le catalogue (valide l'interaction)
            await view.update_embed(interaction)
            
            # 2. On envoie la confirmation d'achat en followup
            await interaction.followup.send(embed=embed_success)

        except Exception as e:
            print(f"Erreur achat catalogue: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Une erreur est survenue lors de l'achat.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Une erreur est survenue lors de l'achat.", ephemeral=True)

class CatalogueView(discord.ui.View):
    def __init__(self, categories, user_balance, fluctuations):
        super().__init__(timeout=180)
        self.current_category = 0
        self.categories = list(categories.items())
        self.user_balance = user_balance
        self.fluctuations = fluctuations
        self.add_purchase_select()

    def add_purchase_select(self):
        # Supprimer l'ancien select s'il existe
        for item in self.children:
            if isinstance(item, PurchaseSelect):
                self.remove_item(item)
                break
        
        # Ajouter le select pour la catégorie actuelle
        category_name, items = self.categories[self.current_category]
        multiplier = self.fluctuations.get(category_name, 1.0)
        self.add_item(PurchaseSelect(items, category_name, multiplier))

    @discord.ui.button(label="⬅️ Précédent", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = (self.current_category - 1) % len(self.categories)
        self.add_purchase_select()
        await self.update_embed(interaction)

    @discord.ui.button(label="➡️ Suivant", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = (self.current_category + 1) % len(self.categories)
        self.add_purchase_select()
        await self.update_embed(interaction)

    async def update_embed(self, interaction: discord.Interaction, from_callback=False):
        category_name, items = self.categories[self.current_category]
        multiplier = self.fluctuations.get(category_name, 1.0)
        
        fluc_str = ""
        if multiplier > 1.0:
            fluc_str = f" 📈 (+{int((multiplier - 1.0) * 100)}%)"
        elif multiplier < 1.0:
            fluc_str = f" 📉 (-{int((1.0 - multiplier) * 100)}%)"
            
        embed = discord.Embed(
            title=f"{category_emojis[category_name]} {category_name}{fluc_str}",
            description="Utilisez le menu déroulant ci-dessous pour acheter un objet.\n*Les prix varient chaque jour selon la Bourse !*",
            color=0x000000
        )

        for item in items:
            actual_price = int(item['price'] * multiplier)
            price_display = f"**{actual_price:,}** 💰"
            if multiplier != 1.0:
                price_display += f" *(Base: {item['price']:,})*"
                
            field_text = f"Prix : {price_display}\n{item['description']}\n"
            rarity_text = " ".join([f"{rarity_indicators[r]}" for r in item["rarities"]])
            embed.add_field(
                name=f"{item['emoji']} {item['name']}", 
                value=f"{field_text}Raretés : {rarity_text}", 
                inline=False
            )
        
        embed.set_footer(text=f"Page {self.current_category + 1}/{len(self.categories)} • 💰 Votre solde : {self.user_balance:,} coins")
        
        if from_callback:
            # Si on vient du callback de l'achat, on utilise edit_original_response car interaction a déjà été répondue
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

from discord.ext import tasks
from datetime import datetime, timedelta

class Catalogue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ensure_tables_exist()
        self.market_fluctuations_loop.start()

    def ensure_tables_exist(self):
        execute_query("CREATE TABLE IF NOT EXISTS market_fluctuations (guild_id TEXT, category TEXT, multiplier REAL, expires_at INTEGER, PRIMARY KEY (guild_id, category))")

    def cog_unload(self):
        self.market_fluctuations_loop.cancel()

    @tasks.loop(hours=24)
    async def market_fluctuations_loop(self):
        now = int(datetime.now().timestamp())
        # Récupérer toutes les guildes
        guild_ids = [str(g.id) for g in self.bot.guilds]
        
        for guild_id in guild_ids:
            try:
                # Nettoyer les anciennes fluctuations
                execute_query("DELETE FROM market_fluctuations WHERE guild_id = ? AND expires_at < ?", (guild_id, now))
                
                # Pour chaque catégorie, 30% de chance d'avoir une fluctuation
                for category_name in category_emojis.keys():
                    if random.random() < 0.3:
                        # Fluctuation entre -20% et +20%
                        multiplier = round(random.uniform(0.8, 1.2), 2)
                        if multiplier == 1.0: continue
                        
                        expires = int((datetime.now() + timedelta(hours=24)).timestamp())
                        
                        # Update or insert
                        existing = fetch_one("SELECT 1 FROM market_fluctuations WHERE guild_id = ? AND category = ?", (guild_id, category_name))
                        if existing:
                            execute_query("UPDATE market_fluctuations SET multiplier = ?, expires_at = ? WHERE guild_id = ? AND category = ?", (multiplier, expires, guild_id, category_name))
                        else:
                            execute_query("INSERT INTO market_fluctuations (guild_id, category, multiplier, expires_at) VALUES (?, ?, ?, ?)", (guild_id, category_name, multiplier, expires))
            except Exception as e:
                print(f"[Catalogue] Error updating fluctuations for guild {guild_id}: {e}")

    @market_fluctuations_loop.before_loop
    async def before_market_fluctuations(self):
        await self.bot.wait_until_ready()

    def get_fluctuations(self, guild_id: str) -> dict:
        now = int(datetime.now().timestamp())
        rows = fetch_all("SELECT category, multiplier FROM market_fluctuations WHERE guild_id = ? AND expires_at > ?", (guild_id, now))
        fluctuations = {}
        for r in rows:
            fluctuations[r[0]] = float(r[1])
        return fluctuations

    @commands.command(name="catalogue")
    async def catalogue(self, ctx):
        """Affiche le catalogue des objets disponibles"""
        guild_id = str(ctx.guild.id)
        user_balance = get_user_wallet(ctx.guild.id, ctx.author.id)
        fluctuations = self.get_fluctuations(guild_id)

        # Afficher la première catégorie
        category_name, items = list(catalogue_items.items())[0]
        multiplier = fluctuations.get(category_name, 1.0)
        
        fluc_str = ""
        if multiplier > 1.0:
            fluc_str = f" 📈 (+{int((multiplier - 1.0) * 100)}%)"
        elif multiplier < 1.0:
            fluc_str = f" 📉 (-{int((1.0 - multiplier) * 100)}%)"
        
        embed = discord.Embed(
            title=f"{category_emojis[category_name]} {category_name}{fluc_str}",
            description="Utilisez le menu déroulant ci-dessous pour acheter un objet.\n*Les prix varient chaque jour selon la Bourse !*",
            color=0x000000
        )

        for item in items:
            actual_price = int(item['price'] * multiplier)
            price_display = f"**{actual_price:,}** 💰"
            if multiplier != 1.0:
                price_display += f" *(Base: {item['price']:,})*"
                
            field_text = f"Prix : {price_display}\n{item['description']}\n"
            rarity_text = " ".join([f"{rarity_indicators[r]}" for r in item["rarities"]])
            embed.add_field(
                name=f"{item['emoji']} {item['name']}", 
                value=f"{field_text}Raretés : {rarity_text}", 
                inline=False
            )

        embed.set_footer(text=f"Page 1/{len(catalogue_items)} • 💰 Votre solde : {user_balance:,} coins")
        view = CatalogueView(catalogue_items, user_balance, fluctuations)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Catalogue(bot))
