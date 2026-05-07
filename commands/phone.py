import discord
from discord.ext import commands
import asyncio
from database import execute_query, fetch_one, fetch_all, get_inventaire, update_inventaire, get_user_ddos, set_user_ddos, get_ddos_cooldown, set_ddos_cooldown, get_drug_plantation, update_drug_plantation, delete_drug_plantation, update_wallet, get_wallet_bank, get_crypto_data, get_user_crypto, update_user_crypto
from datetime import datetime, timedelta
import random
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# App Drogue:
# Qualités: "Basse" (1 jour), "Moyenne" (2 jours), "Haute" (3 jours)
# Process: 1. Plant -> 2. Water every day -> 3. Harvest -> 4. Dry (1 day) -> 5. Sell

class AppSelect(discord.ui.Select):
    def __init__(self, bot, ctx):
        options = [
            discord.SelectOption(label="GhostCoin (Crypto)", description="Bourse et investissement", emoji="📈", value="crypto"),
            discord.SelectOption(label="Hack.exe (DDoS)", description="Pirater un autre joueur", emoji="⌨️", value="hack"),
            discord.SelectOption(label="WeedFarm (Drogue)", description="Gérer tes plantations", emoji="🌿", value="drugs"),
            discord.SelectOption(label="SignalDealer (Vente)", description="Contacter le dealer", emoji="💬", value="dealer")
        ]
        super().__init__(placeholder="Ouvrir une application...", options=options)
        self.bot = bot
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Pas ton téléphone", ephemeral=True)

        selection = self.values[0]

        if selection == "crypto":
            view = CryptoView(self.ctx, self.bot)
            await view.send_ui(interaction)

        elif selection == "hack":
            class DDoSModal(discord.ui.Modal, title="Lancer une attaque DDoS"):
                target_id = discord.ui.TextInput(label="ID Discord de la cible", min_length=17, max_length=20)
                
                async def on_submit(self, minteraction: discord.Interaction):
                    guild_id = str(minteraction.guild.id)
                    user_id = str(minteraction.user.id)
                    target = self.target_id.value
                    
                    if target == user_id:
                        return await minteraction.response.send_message("❌ Tu ne peux pas te cibler toi-même.", ephemeral=True)
                        
                    wallet = get_wallet_bank(guild_id, user_id)["wallet"]
                    if wallet < 5000:
                        return await minteraction.response.send_message("❌ Une attaque coûte 5 000 coins (pour les serveurs).", ephemeral=True)
                        
                    last_ddos = get_ddos_cooldown(guild_id, user_id)
                    if last_ddos:
                        expiry = datetime.fromisoformat(last_ddos) + timedelta(days=1)
                        if datetime.now() < expiry:
                            return await minteraction.response.send_message("❌ Les serveurs de hack surchauffent. Tu dois attendre demain.", ephemeral=True)
                            
                    update_wallet(guild_id, user_id, -5000)
                    set_ddos_cooldown(guild_id, user_id, datetime.now().isoformat())
                    
                    if random.random() < 0.30:
                        ddos_expiry = datetime.now() + timedelta(hours=1)
                        set_user_ddos(guild_id, target, ddos_expiry.isoformat())
                        await minteraction.response.send_message("✅ **HACK RÉUSSI !** La connexion bancaire de la cible est coupée pendant 1 heure.", ephemeral=True)
                    else:
                        await minteraction.response.send_message("❌ **ÉCHEC DU HACK.** Pare-feu bloqué. Tu as perdu 5 000 coins.", ephemeral=True)
            
            await interaction.response.send_modal(DDoSModal())

        elif selection == "drugs":
            view = WeedFarmView(self.ctx, self.bot)
            embed = view.build_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif selection == "dealer":
            seed = int(datetime.now().strftime("%Y%m%d")) + interaction.guild.id
            random.seed(seed)
            password = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
            
            # Horaire de nuit : entre 17h00 et 05h59
            hour = random.randint(17, 29) # 24+5 = 29 pour finir à 5h
            display_hour = hour if hour < 24 else hour - 24
            minute = random.randint(0, 59)
            random.seed()
            
            embed = discord.Embed(
                title="💬 Message crypté",
                description=f"Yo. Le point de rendez-vous est ultra-précis. Sois là à **{display_hour:02d}h{minute:02d} pile**.\n\n"
                            f"Quand tu as la came séchée, utilise cette commande exacte :\n"
                            f"`+sell_drugs {password}`\n\n"
                            f"⚠️ Tu n'as que **60 secondes** pour valider la vente. Si tu rates la minute ou le code, les flics t'embarquent.",
                color=0x2f3136
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class PhoneView(discord.ui.View):
    def __init__(self, ctx, bot):
        super().__init__(timeout=180)
        self.add_item(AppSelect(bot, ctx))

class CryptoModal(discord.ui.Modal):
    def __init__(self, action: str, price: int, user_crypto: int, wallet: int, view: 'CryptoView'):
        super().__init__(title=f"{'Achat' if action == 'buy' else 'Vente'} de GhostCoins")
        self.action = action
        self.price = price
        self.user_crypto = user_crypto
        self.wallet = wallet
        self.view = view
        
        self.amount = discord.ui.TextInput(
            label="Quantité à " + ("acheter" if action == "buy" else "vendre"),
            placeholder="Ex: 5",
            min_length=1,
            max_length=6
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.amount.value)
            if qty <= 0: raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Quantité invalide.", ephemeral=True)

        guild_id, user_id = self.view.guild_id, self.view.user_id

        if self.action == "buy":
            total_cost = qty * self.price
            if self.wallet < total_cost:
                return await interaction.response.send_message(f"❌ Tu n'as pas assez d'argent. Il te faut {total_cost:,} coins pour {qty} GHC.", ephemeral=True)
            
            update_wallet(guild_id, user_id, -total_cost)
            update_user_crypto(guild_id, user_id, qty)
            await interaction.response.send_message(f"✅ Tu as acheté **{qty} GHC** pour **{total_cost:,} coins** !", ephemeral=True)
        else:
            if self.user_crypto < qty:
                return await interaction.response.send_message(f"❌ Tu ne possèdes pas assez de GHC (Solde: {self.user_crypto}).", ephemeral=True)
            
            total_gain = qty * self.price
            update_user_crypto(guild_id, user_id, -qty)
            update_wallet(guild_id, user_id, total_gain)
            await interaction.response.send_message(f"✅ Tu as vendu **{qty} GHC** pour **{total_gain:,} coins** !", ephemeral=True)

        # Mettre à jour l'UI d'origine (on doit re-générer l'embed car les soldes ont changé)
        await self.view.update_ui(interaction)

class CryptoView(discord.ui.View):
    def __init__(self, ctx, bot):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot = bot
        self.guild_id = str(ctx.guild.id)
        self.user_id = str(ctx.author.id)

    def generate_graph(self, history):
        prices = [h["price"] for h in history]
        if len(prices) < 2: prices = [100, 100]

        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(prices, color='#00ff00', marker='o', linewidth=2, markersize=4)
        ax.set_facecolor('#1e1e24')
        fig.patch.set_facecolor('#1e1e24')

        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('white')
        ax.set_title("Cours du GhostCoin (GHC)", color='white')

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        return buf

    async def build_embed_and_file(self):
        data = get_crypto_data()
        price = data["current_price"]
        user_crypto = get_user_crypto(self.guild_id, self.user_id)
        wallet = get_wallet_bank(self.guild_id, self.user_id)["wallet"]

        buf = self.generate_graph(data["history"])
        file = discord.File(buf, filename="crypto_graph.png")

        embed = discord.Embed(
            title="📈 GhostCoin Exchange",
            description=f"**Prix Actuel:** `{price:,} coins` / GHC\n\n"
                        f"**Ton Portefeuille:** `{user_crypto} GHC` (Valeur: {user_crypto * price:,} coins)\n"
                        f"**Ton Solde (Wallet):** `{wallet:,} coins`",
            color=0x2ecc71
        )
        embed.set_image(url="attachment://crypto_graph.png")
        return embed, file

    async def send_ui(self, interaction: discord.Interaction):
        embed, file = await self.build_embed_and_file()
        await interaction.response.send_message(file=file, embed=embed, view=self, ephemeral=True)

    async def update_ui(self, interaction: discord.Interaction):
        # Cette méthode met à jour le message d'origine avec les nouvelles données
        embed, file = await self.build_embed_and_file()
        # Note: Dans un Modal on ne peut pas utiliser edit_original_response directement sur l'interaction du modal 
        # pour changer un fichier attaché facilement, on va donc utiliser le webhook de l'interaction initiale si possible
        # ou simplement demander à l'utilisateur de réouvrir s'il y a un souci, mais ici on va tenter l'edit.
        try:
            await interaction.edit_original_response(embed=embed, attachments=[file], view=self)
        except:
            # Fallback si l'interaction a expiré ou autre
            pass

    @discord.ui.button(label="Acheter", style=discord.ButtonStyle.success, emoji="💰")
    async def buy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Pas ton téléphone", ephemeral=True)
        data = get_crypto_data()
        wallet = get_wallet_bank(self.guild_id, self.user_id)["wallet"]
        user_crypto = get_user_crypto(self.guild_id, self.user_id)
        
        modal = CryptoModal("buy", data["current_price"], user_crypto, wallet, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Vendre", style=discord.ButtonStyle.danger, emoji="🪙")
    async def sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Pas ton téléphone", ephemeral=True)
        data = get_crypto_data()
        wallet = get_wallet_bank(self.guild_id, self.user_id)["wallet"]
        user_crypto = get_user_crypto(self.guild_id, self.user_id)
        
        modal = CryptoModal("sell", data["current_price"], user_crypto, wallet, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Actualiser", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: 
            return await interaction.response.send_message("❌ Pas ton téléphone", ephemeral=True)
        
        # 1. Désactiver le bouton immédiatement
        button.disabled = True
        button.label = "Attente..."
        await interaction.response.edit_message(view=self)
        
        # 2. Actualiser les données et le graphique
        await self.update_ui(interaction)
        
        # 3. Attendre 5 secondes
        await asyncio.sleep(5)
        
        # 4. Réactiver le bouton
        button.disabled = False
        button.label = "Actualiser"
        
        # 5. Mettre à jour le message pour réactiver le bouton visuellement
        try:
            # On récupère le message d'origine via l'interaction pour renvoyer la vue mise à jour
            await interaction.edit_original_response(view=self)
        except Exception:
            pass

class WeedFarmView(discord.ui.View):
    def __init__(self, ctx, bot):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot = bot
        self.guild_id = str(ctx.guild.id)
        self.user_id = str(ctx.author.id)
        self.plantation = get_drug_plantation(self.guild_id, self.user_id)
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if not self.plantation:
            self.add_item(WeedActionBtn("Planter Basse (500💰)", "plant_basse", discord.ButtonStyle.primary))
            self.add_item(WeedActionBtn("Planter Moyenne (2k💰)", "plant_moyenne", discord.ButtonStyle.primary))
            self.add_item(WeedActionBtn("Planter Haute (5k💰)", "plant_haute", discord.ButtonStyle.primary))
            return
        stage = self.plantation["stage"]
        if stage == "growing":
            self.add_item(WeedActionBtn("💧 Arroser", "water", discord.ButtonStyle.primary))
        elif stage == "ready_harvest":
            self.add_item(WeedActionBtn("✂️ Récolter", "harvest", discord.ButtonStyle.success))
        elif stage == "drying":
            self.add_item(WeedActionBtn("🔥 Vérifier Séchage", "dry", discord.ButtonStyle.secondary))
        self.add_item(WeedActionBtn("🗑️ Détruire", "destroy", discord.ButtonStyle.danger))

    def build_embed(self):
        if not self.plantation:
            return discord.Embed(title="🌿 WeedFarm", description="**Tarifs des graines :**\n• Basse Qualité : 500 coins\n• Moyenne Qualité : 2 000 coins\n• Haute Qualité : 5 000 coins\n\nQue veux-tu planter ?", color=0x2ecc71)
        stage = self.plantation["stage"]
        qualite = self.plantation["quality"]
        if stage == "growing":
            req_water = {"Basse": 1, "Moyenne": 2, "Haute": 3}[qualite]
            water_count = self.plantation["water_count"]
            desc = f"🌱 **Culture en cours** ({qualite} Qualité)\nArrosages : {water_count}/{req_water}\n"
            if self.plantation["last_watered"]:
                last_w = datetime.fromisoformat(self.plantation["last_watered"])
                if datetime.now() < last_w + timedelta(days=1):
                    desc += f"*(Déjà arrosé aujourd'hui. Reviens <t:{int((last_w + timedelta(days=1)).timestamp())}:R>)*"
                else: desc += "**Ta plante a soif !** 💧"
            else: desc += "**Ta plante a soif !** 💧"
        elif stage == "ready_harvest": desc = "🌿 **Prêt à récolter !** Coupe ça vite."
        elif stage == "drying":
            harvest_time = datetime.fromisoformat(self.plantation["harvest_date"])
            if datetime.now() >= harvest_time + timedelta(days=1): desc = "🔥 **Séchage terminé !** Prêt à être empaqueté."
            else: desc = f"💨 **En cours de séchage...** Fini <t:{int((harvest_time + timedelta(days=1)).timestamp())}:R>."
        return discord.Embed(title="🌿 WeedFarm", description=desc, color=0x2ecc71)

class WeedActionBtn(discord.ui.Button):
    def __init__(self, label, action, style):
        super().__init__(label=label, style=style)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        view: WeedFarmView = self.view
        guild_id, user_id = view.guild_id, view.user_id
        if self.action.startswith("plant_"):
            qualite = self.action.split("_")[1].capitalize()
            cost = {"Basse": 500, "Moyenne": 2000, "Haute": 5000}[qualite]
            wallet = get_wallet_bank(guild_id, user_id)["wallet"]
            if wallet < cost: return await interaction.response.send_message(f"❌ Les graines {qualite} coûtent {cost} coins.", ephemeral=True)
            update_wallet(guild_id, user_id, -cost)
            new_plant = {"quality": qualite, "stage": "growing", "water_count": 0, "last_watered": None, "plant_date": datetime.now().isoformat()}
            update_drug_plantation(guild_id, user_id, new_plant)
            await interaction.response.send_message(f"✅ Plantation {qualite} lancée (-{cost}💰) !", ephemeral=True)
        elif self.action == "water":
            plant = view.plantation
            if plant["last_watered"]:
                last_w = datetime.fromisoformat(plant["last_watered"])
                if datetime.now() < last_w + timedelta(days=1): return await interaction.response.send_message("❌ Tu as déjà arrosé aujourd'hui !", ephemeral=True)
            
            # Check for water bottle
            inv = get_inventaire(guild_id, user_id)
            has_water = False
            water_item = "Bouteille d'eau"
            if water_item in inv:
                if isinstance(inv[water_item], dict) and inv[water_item].get("quantity", 0) > 0:
                    inv[water_item]["quantity"] -= 1
                    if inv[water_item]["quantity"] <= 0: del inv[water_item]
                    has_water = True
                elif isinstance(inv[water_item], int) and inv[water_item] > 0:
                    inv[water_item] -= 1
                    if inv[water_item] <= 0: del inv[water_item]
                    has_water = True
            
            if not has_water:
                return await interaction.response.send_message("❌ Il te faut une **Bouteille d'eau** pour arroser ta plante ! Achètes-en au shop.", ephemeral=True)

            update_inventaire(guild_id, user_id, inv)
            plant["water_count"] += 1
            plant["last_watered"] = datetime.now().isoformat()
            req_water = {"Basse": 1, "Moyenne": 2, "Haute": 3}[plant["quality"]]
            if plant["water_count"] >= req_water: plant["stage"] = "ready_harvest"
            update_drug_plantation(guild_id, user_id, plant)
            await interaction.response.send_message("💧 Tu as utilisé une bouteille d'eau. La plante est arrosée !", ephemeral=True)
        elif self.action == "harvest":
            plant = view.plantation
            plant["stage"] = "drying"
            plant["harvest_date"] = datetime.now().isoformat()
            update_drug_plantation(guild_id, user_id, plant)
            await interaction.response.send_message("✂️ Récolte terminée. Séchage : 24h.", ephemeral=True)
        elif self.action == "dry":
            plant = view.plantation
            if datetime.now() < datetime.fromisoformat(plant["harvest_date"]) + timedelta(days=1): return await interaction.response.send_message("❌ Pas encore sec !", ephemeral=True)
            qty = {"Basse": 5, "Moyenne": 15, "Haute": 30}[plant["quality"]]
            inv = get_inventaire(guild_id, user_id)
            drug_name = f"Weed ({plant['quality']})"
            if "drugs" not in inv: inv["drugs"] = {}
            inv["drugs"][drug_name] = inv["drugs"].get(drug_name, 0) + qty
            update_inventaire(guild_id, user_id, inv)
            delete_drug_plantation(guild_id, user_id)
            await interaction.response.send_message(f"📦 Reçu **{qty}x {drug_name}** !", ephemeral=True)
        elif self.action == "destroy":
            delete_drug_plantation(guild_id, user_id)
            await interaction.response.send_message("🔥 Brûlée.", ephemeral=True)
        view.plantation = get_drug_plantation(guild_id, user_id)
        view.update_buttons()
        await interaction.message.edit(embed=view.build_embed(), view=view)

class Phone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def phone(self, ctx):
        inventory = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
        phone_quantity = 0
        if "Téléphone" in inventory:
            if isinstance(inventory["Téléphone"], dict): phone_quantity = inventory["Téléphone"].get("quantity", 0)
            else: phone_quantity = inventory["Téléphone"]
        if phone_quantity <= 0: return await ctx.send(embed=discord.Embed(description="❌ Pas de téléphone !", color=discord.Color.red()))
        view = PhoneView(ctx, self.bot)
        embed = discord.Embed(title="📱 Accueil Smartphone", description="Connexion sécurisée.\nOuvre le menu pour choisir une application :", color=0x2f3136)
        try:
            file = discord.File("commands/unknown.png", filename="unknown.png")
            embed.set_image(url="attachment://unknown.png")
            await ctx.send(file=file, embed=embed, view=view)
        except: await ctx.send(embed=embed, view=view)

    @commands.command()
    async def sell_drugs(self, ctx, password: str = None):
        guild_id, user_id = str(ctx.guild.id), str(ctx.author.id)
        
        # Generer le bon mot de passe, heure et minute (doit matcher le dealer)
        seed = int(datetime.now().strftime("%Y%m%d")) + ctx.guild.id
        random.seed(seed)
        correct_password = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
        hour_raw = random.randint(17, 29)
        correct_hour = hour_raw if hour_raw < 24 else hour_raw - 24
        correct_minute = random.randint(0, 59)
        random.seed()
        
        now = datetime.now()
        
        # Vérification d'inventaire AVANT toute chose
        inv = get_inventaire(guild_id, user_id)
        if "drugs" not in inv or not any(qty > 0 for qty in inv.get("drugs", {}).values()):
            return await ctx.reply("❌ Le dealer te regarde bizarrement : 'T'as rien à me vendre mon gars.'")

        # S'il se trompe de mdp ou d'heure/minute -> POLICE
        if now.hour != correct_hour or now.minute != correct_minute or password != correct_password:
            # Confisque toutes les drogues et met une amende
            if "drugs" in inv:
                del inv["drugs"]
                update_inventaire(guild_id, user_id, inv)
            
            update_wallet(guild_id, user_id, -10000)
            
            embed = discord.Embed(
                title="🚨 DESCENTE DE POLICE !",
                description=f"Le dealer t'a balancé ! Tu devais être là à **{correct_hour:02d}h{correct_minute:02d}** avec le bon code.\n\n"
                            f"La police a confisqué **toute ta marchandise** et t'a mis une amende de **10 000 coins**.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)
            
        # Succes ! Vendre les drogues
        total_gains = 0
        prices = {"Weed (Basse)": 1500, "Weed (Moyenne)": 3000, "Weed (Haute)": 6000}
        
        sold_text = ""
        for drug_name, qty in list(inv["drugs"].items()):
            if qty > 0:
                price = prices.get(drug_name, 1000) * qty
                total_gains += price
                sold_text += f"{qty}x {drug_name} -> {price:,} coins\n"
                
        del inv["drugs"]
        update_inventaire(guild_id, user_id, inv)
        update_wallet(guild_id, user_id, total_gains)
        
        embed = discord.Embed(
            title="💼 Transaction terminée",
            description=f"Le dealer prend les sacs et te file une enveloppe de billets.\n\n**Gains :**\n{sold_text}\n**Total : +{total_gains:,} coins**",
            color=0x00FF00
        )
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Phone(bot))
