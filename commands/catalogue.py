import discord
from discord.ext import commands
import random
from database import execute_query, fetch_one, fetch_all, get_inventaire, update_inventaire

# Dictionnaire des catégories avec leurs émojis
category_emojis = {
    "Véhicules": "🚗",
    "Propriétés": "🏘️",
    "Objets Tech": "📱",
    "Art & Collection": "🎨",
    "Mode & Accessoires": "👔",
    "Animaux": "🐾",
    "Sports & Loisirs": "⚽"
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
    ]
}

class CatalogueView(discord.ui.View):
    def __init__(self, categories, user_balance):
        super().__init__(timeout=180)
        self.current_category = 0
        self.categories = list(categories.items())
        self.user_balance = user_balance

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = (self.current_category - 1) % len(self.categories)
        await self.update_embed(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = (self.current_category + 1) % len(self.categories)
        await self.update_embed(interaction)

    async def update_embed(self, interaction: discord.Interaction):
        category_name, items = self.categories[self.current_category]
        
        embed = discord.Embed(
            title=f"{category_emojis[category_name]} {category_name}",
            description="💡 `+buy nom_de_l'objet` pour acheter • ⬅️ ➡️ pour naviguer",
            color=0x000000
        )

        for item in items:
            field_text = f"Prix: {item['price']:,} coins\n{item['description']}\n\n"
            for rarity in item["rarities"]:
                field_text += f"{rarity_indicators[rarity]} {item['variants'][rarity]} ({rarity_chances[rarity]}%)\n"
            
            embed.add_field(
                name=f"{item['emoji']} {item['name']}", 
                value=field_text, 
                inline=False
            )
        
        embed.set_footer(text=f"Page {self.current_category + 1}/{len(self.categories)} • 💰 Votre solde: {self.user_balance:,} coins")
        await interaction.response.edit_message(embed=embed, view=self)

class Catalogue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="catalogue")
    async def catalogue(self, ctx):
        """Affiche le catalogue des objets disponibles"""
        balance = fetch_one("SELECT wallet FROM users WHERE guild_id = ? AND user_id = ?",
                          (str(ctx.guild.id), str(ctx.author.id)))
        
        user_balance = balance[0] if balance else 0

        # Afficher la première catégorie
        category_name, items = list(catalogue_items.items())[0]
        
        embed = discord.Embed(
            title=f"{category_emojis[category_name]} {category_name}",
            description="💡 `+buy nom_de_l'objet` pour acheter • ⬅️ ➡️ pour naviguer",
            color=0x000000
        )

        for item in items:
            field_text = f"Prix: {item['price']:,} coins\n{item['description']}\n\n"
            for rarity in item["rarities"]:
                field_text += f"{rarity_indicators[rarity]} {item['variants'][rarity]} ({rarity_chances[rarity]}%)\n"
            
            embed.add_field(
                name=f"{item['emoji']} {item['name']}", 
                value=field_text, 
                inline=False
            )

        embed.set_footer(text=f"Page 1/{len(catalogue_items)} • 💰 Votre solde: {user_balance:,} coins")
        view = CatalogueView(catalogue_items, user_balance)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="buy")
    async def buy(self, ctx, *, item_name: str):
        """Acheter un item du catalogue"""
        # Vérifier si l'utilisateur a déjà un téléphone ou un wagon
        inventory = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
        
        # Vérifier si l'item est un téléphone ou un wagon
        is_phone = "phone" in item_name.lower() or "téléphone" in item_name.lower() or item_name.lower() == "smartphone"
        is_wagon = "wagon" in item_name.lower()
        
        if is_phone:
            has_phone = any(("phone" in item.lower() or "téléphone" in item.lower() or item.lower() == "smartphone") for item in inventory.keys())
            if has_phone:
                embed = discord.Embed(title="❌ Achat impossible", description="Vous possédez déjà un téléphone ! Vendez-le d'abord si vous souhaitez en acheter un nouveau.", color=discord.Color.red())
                await ctx.send(embed=embed)
                return
                
        if is_wagon:
            has_wagon = any("wagon" in item.lower() for item in inventory.keys())
            if has_wagon:
                embed = discord.Embed(title="❌ Achat impossible", description="Vous possédez déjà un wagon ! Vendez-le d'abord si vous souhaitez en acheter un nouveau.", color=discord.Color.red())
                await ctx.send(embed=embed)
                return

        # Chercher l'item dans toutes les catégories
        found_item = None
        for category, items in catalogue_items.items():
            for item in items:
                if item['name'].lower() == item_name.lower():
                    found_item = item
                    break
            if found_item:
                break

        if not found_item:
            await ctx.send("❌ Cet item n'existe pas dans le catalogue!")
            return

        # Vérifier le solde de l'utilisateur
        balance = fetch_one("SELECT wallet FROM users WHERE guild_id = ? AND user_id = ?",
                          (str(ctx.guild.id), str(ctx.author.id)))
        
        if not balance:
            await ctx.send("❌ Vous n'avez pas de compte!")
            return
        
        current_balance = balance[0]

        if current_balance < found_item['price']:
            await ctx.send(f"❌ Vous n'avez pas assez d'argent! Il vous manque {found_item['price'] - current_balance:,} 💰")
            return

        # Déterminer la rareté obtenue selon les probabilités
        rarity_list = []
        chance_list = []
        for rarity in found_item["rarities"]:
            rarity_list.append(rarity)
            chance_list.append(rarity_chances[rarity])
        
        obtained_rarity = random.choices(rarity_list, weights=chance_list)[0]

        # Mettre à jour le solde
        execute_query("UPDATE users SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?",
                     (found_item['price'], str(ctx.guild.id), str(ctx.author.id)))

        # Mettre à jour l'inventaire avec la variante obtenue
        variant_name = f"{found_item['name']} {obtained_rarity}"  # Nom unique pour la variante
        inventaire = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
        if variant_name in inventaire:
            inventaire[variant_name] += 1
        else:
            inventaire[variant_name] = 1
        
        update_inventaire(str(ctx.guild.id), str(ctx.author.id), inventaire)

        # Message de confirmation
        embed = discord.Embed(
            title="✨ Achat réussi!",
            description=f"Vous avez obtenu : {found_item['emoji']} **{found_item['variants'][obtained_rarity]}**\n"
                       f"Rareté : {rarity_indicators[obtained_rarity]}\n"
                       f"Prix payé : {found_item['price']:,} 💰",
            color=0x000000
        )
        embed.add_field(name="💰 Nouveau solde", value=f"{current_balance - found_item['price']:,} coins")

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Catalogue(bot)) 