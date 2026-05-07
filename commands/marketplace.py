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
    cancel_marketplace_listing,
    update_marketplace_price
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
    if result and len(result) > 0 and result[0] is not None:
        return result[0]
    return 0

def update_user_wallet(guild_id: str, user_id: str, amount: int) -> None:
    """Met à jour le portefeuille d'un utilisateur"""
    user_init(guild_id, user_id)
    execute_query("""
        UPDATE users 
        SET wallet = wallet + ? 
        WHERE user_id = ? AND guild_id = ?
    """, (amount, user_id, guild_id))

def get_inventory_quantity(inventory: Optional[Dict], item_name: str) -> int:
    """Get the quantity of an item in an inventory (handles nested minerals)"""
    try:
        if not inventory or not isinstance(inventory, dict):
            return 0
            
        # Check top level
        if item_name in inventory:
            item = inventory[item_name]
            if isinstance(item, dict):
                quantity = item.get("quantity", 0)
                return safe_int_convert(quantity)
            return safe_int_convert(item)
            
        # Check minerals sub-category
        if "minerals" in inventory and isinstance(inventory["minerals"], dict):
            if item_name in inventory["minerals"]:
                return safe_int_convert(inventory["minerals"][item_name])
                
        return 0
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
            # Pour minerals, on doit chercher dans le sous-dict
            if "minerals" in inventory and isinstance(inventory["minerals"], dict) and item_name in inventory["minerals"]:
                del inventory["minerals"][item_name]
                if not inventory["minerals"]:
                    del inventory["minerals"]
            elif item_name in inventory:
                del inventory[item_name]
        else:
            # Si c'est un minéral
            if "minerals" in inventory and isinstance(inventory["minerals"], dict) and item_name in inventory["minerals"]:
                inventory["minerals"][item_name] = new_quantity
            elif item_name in inventory and isinstance(inventory[item_name], dict):
                inventory[item_name]["quantity"] = new_quantity
            else:
                inventory[item_name] = new_quantity
            
        return inventory
    except Exception:
        return {} if not inventory else inventory

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
        
        # Calculer le prix suggéré (-20% du catalogue)
        base_price = 0
        from .catalogue import catalogue_items
        
        # Recherche robuste du prix
        search_name = item_name.lower()
        for items in catalogue_items.values():
            for item in items:
                if item["name"].lower() == search_name:
                    base_price = item["price"]
                    break
                if item["name"].lower() in search_name:
                    base_price = item["price"]
                    break
                if "variants" in item:
                    for variant_name in item["variants"].values():
                        if variant_name.lower() == search_name:
                            base_price = item["price"]
                            break
            if base_price > 0: break
            
        suggested_price_val = int(base_price * 0.8) if base_price > 0 else 0
        suggested_price_str = str(suggested_price_val) if suggested_price_val > 0 else ""
        
        self.quantity = discord.ui.TextInput(
            label=f"Quantité (max: {max_quantity})",
            placeholder="Entrez la quantité à vendre...",
            default="1",
            min_length=1,
            max_length=len(str(max_quantity)),
            required=True
        )
        self.add_item(self.quantity)
        
        self.price = discord.ui.TextInput(
            label="Prix par unité",
            placeholder=f"Prix conseillé: {suggested_price_str}" if suggested_price_str else "Entrez le prix...",
            default=suggested_price_str,
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
                return await interaction.response.send_message(f"❌ Quantité invalide (1-{self.max_quantity}).", ephemeral=True)
                
            if price <= 0:
                return await interaction.response.send_message("❌ Le prix doit être positif.", ephemeral=True)

            # Vérifier si l'utilisateur a déjà une annonce active pour cet item sur ce serveur
            existing_listing = fetch_one("""
                SELECT 1 FROM marketplace_listings
                WHERE seller_id = ? AND item_name = ? AND guild_id = ? AND status = 'active'
            """, (str(interaction.user.id), self.item_name, str(interaction.guild_id)))

            if existing_listing:
                return await interaction.response.send_message("❌ Vous avez déjà une annonce active pour cet item.", ephemeral=True)

            # Vérifier l'inventaire
            inventory = get_inventaire(str(interaction.guild_id), str(interaction.user.id))
            current_quantity = get_inventory_quantity(inventory, self.item_name)
            
            if current_quantity < quantity:
                return await interaction.response.send_message(f"❌ Stock insuffisant ({current_quantity} dispo).", ephemeral=True)
                
            # Créer l'annonce avec status='active'
            execute_query("""
                INSERT INTO marketplace_listings
                (guild_id, listing_id, seller_id, item_name, quantity, price_per_unit, description, created_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(interaction.guild_id),
                None,
                str(interaction.user.id),
                self.item_name,
                quantity,
                price,
                "",
                int(datetime.now().timestamp()),
                int((datetime.now() + timedelta(weeks=1)).timestamp()),
                'active'
            ))
            
            # Retirer les items de l'inventaire
            new_inv = update_inventory_quantity(inventory, self.item_name, -quantity)
            update_inventaire(str(interaction.guild_id), str(interaction.user.id), new_inv)
            
            await interaction.response.send_message(f"✅ Annonce créée : {quantity}x {self.item_name} pour {format_price(price)}/u.", ephemeral=True)
            # Rafraîchissement automatique supprimé à la demande de l'utilisateur
            
        except ValueError:
            await interaction.response.send_message("❌ Veuillez entrer des nombres valides.", ephemeral=True)
        except Exception as e:
            print(f"Error creating listing: {e}")
            await interaction.response.send_message("❌ Une erreur est survenue.", ephemeral=True)

class SellSelect(discord.ui.Select):
    def __init__(self, view):
        self.marketplace_view = view
        options = []
        self.has_more_items = False
        
        inventory = get_inventaire(str(view.ctx.guild.id), str(view.ctx.author.id))
        if inventory:
            try:
                items_to_show = []
                def process_inventory(inv_data, prefix=""):
                    for item_name, data in inv_data.items():
                        full_name = f"{prefix}{item_name}" if prefix else item_name
                        if item_name == "minerals" and isinstance(data, dict):
                            process_inventory(data, prefix="")
                            continue
                        qty = data.get("quantity", 0) if isinstance(data, dict) else data
                        if isinstance(qty, int) and qty > 0:
                            existing_listing = fetch_one("""
                                SELECT 1 FROM marketplace_listings 
                                WHERE guild_id = ? AND seller_id = ? AND item_name = ? AND status = 'active' AND expires_at > ?
                            """, (str(view.ctx.guild.id), str(view.ctx.author.id), full_name, int(datetime.now().timestamp())))
                            
                            if not existing_listing:
                                item_emoji = "📦"
                                for cat_items in catalogue_items.values():
                                    for cat_item in cat_items:
                                        if cat_item["name"] == full_name.split()[0]:
                                            item_emoji = cat_item.get("emoji", "📦")
                                            break
                                items_to_show.append({"name": full_name, "quantity": qty, "emoji": item_emoji})

                process_inventory(inventory)
                items_to_show.sort(key=lambda x: x["name"])
                self.has_more_items = len(items_to_show) > 25
                for item in items_to_show[:25]:
                    options.append(discord.SelectOption(label=item["name"], description=f"Quantité: {item['quantity']}", value=f"shop:{item['name']}", emoji=item["emoji"]))
            except: pass
                
        super().__init__(
            placeholder="Choisissez un item à vendre...",
            min_values=1,
            max_values=1,
            options=options if options else [discord.SelectOption(label="Aucun item disponible", value="none", emoji="❌")]
        )

    async def callback(self, interaction: discord.Interaction):
        if self.has_more_items:
            await interaction.response.send_message("⚠️ Seuls les 25 premiers items sont affichés.", ephemeral=True)
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ Aucun item à vendre !", ephemeral=True)
        
        item_name = self.values[0].split(":")[1]
        inventory = get_inventaire(str(interaction.guild_id), str(interaction.user.id))
        quantity = get_inventory_quantity(inventory, item_name)
        if quantity <= 0: return await interaction.response.send_message("❌ Item non possédé !", ephemeral=True)
        await interaction.response.send_modal(ListingModal(item_name, quantity, self.marketplace_view))

class ModifyPriceModal(discord.ui.Modal):
    def __init__(self, listing_id, item_name, current_price, marketplace_view):
        super().__init__(title=f"Modifier Prix : {item_name}")
        self.listing_id, self.marketplace_view = listing_id, marketplace_view
        self.price = discord.ui.TextInput(label="Nouveau prix par unité", placeholder=f"Actuel: {current_price}", default=str(current_price), min_length=1, max_length=10, required=True)
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_price = int(self.price.value)
            success, message = update_marketplace_price(str(interaction.guild_id), self.listing_id, str(interaction.user.id), new_price)
            if success:
                await interaction.response.send_message(f"✅ {message}", ephemeral=True)
                await self.marketplace_view.refresh_marketplace(interaction)
            else:
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
        except: await interaction.response.send_message("❌ Prix invalide.", ephemeral=True)

class MyListingsSelect(discord.ui.Select):
    def __init__(self, marketplace_view):
        self.marketplace_view = marketplace_view
        listings = fetch_all("""
            SELECT listing_id, item_name, quantity, price_per_unit 
            FROM marketplace_listings
            WHERE guild_id = ? AND seller_id = ? AND status = 'active' AND expires_at > ?
            ORDER BY created_at DESC
        """, (str(marketplace_view.ctx.guild.id), str(marketplace_view.ctx.author.id), int(datetime.now().timestamp())))
        
        options = []
        for l in listings:
            item_emoji = "📦"
            for cat in catalogue_items.values():
                for it in cat:
                    if it["name"] == l[1]: item_emoji = it.get("emoji", "📦"); break
            options.append(discord.SelectOption(label=f"{l[1]} (x{l[2]})", value=f"{l[0]}|{l[1]}|{l[3]}", emoji=item_emoji, description=f"Prix: {format_price(l[3])}/u"))
            
        if not options: options = [discord.SelectOption(label="Aucune annonce", value="none", emoji="❌")]
        super().__init__(placeholder="Gérer mes annonces...", min_values=1, max_values=1, options=options[:25])
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": return
        l_id, item_name, price = self.values[0].split("|")
        view = discord.ui.View(timeout=60)
        btn_cancel = discord.ui.Button(label="Annuler", style=discord.ButtonStyle.danger, emoji="🗑️")
        async def cancel_cb(inter):
            s, m = cancel_marketplace_listing(str(inter.guild_id), int(l_id), str(inter.user.id))
            if s: await inter.response.send_message(f"✅ {m}", ephemeral=True); await self.marketplace_view.refresh_marketplace(inter)
            else: await inter.response.send_message(f"❌ {m}", ephemeral=True)
        btn_cancel.callback = cancel_cb
        btn_price = discord.ui.Button(label="Prix", style=discord.ButtonStyle.primary, emoji="🏷️")
        async def price_cb(inter): await inter.response.send_modal(ModifyPriceModal(int(l_id), item_name, int(price), self.marketplace_view))
        btn_price.callback = price_cb
        view.add_item(btn_cancel); view.add_item(btn_price)
        await interaction.response.send_message(f"Actions pour **{item_name}** :", view=view, ephemeral=True)

class CategorySelect(discord.ui.Select):
    def __init__(self, marketplace_view):
        self.marketplace_view = marketplace_view
        options = [
            discord.SelectOption(label="Tout", value="all", emoji="🏪"),
            discord.SelectOption(label="Véhicules", value="véhicules", emoji="🚗"),
            discord.SelectOption(label="Propriétés", value="immobilier", emoji="🏠"),
            discord.SelectOption(label="Tech", value="tech", emoji="📱"),
            discord.SelectOption(label="Luxe", value="luxe", emoji="💎"),
            discord.SelectOption(label="Ressources", value="ressources", emoji="📦"),
            discord.SelectOption(label="Autres", value="divers", emoji="❓")
        ]
        super().__init__(placeholder="🔍 Filtrer...", options=options, row=0)
        
    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.marketplace_view.ctx.author: return
        self.marketplace_view.current_category = self.values[0]
        self.marketplace_view.current_page = 1
        await self.marketplace_view.update_message(interaction)

class BuyModal(discord.ui.Modal, title="Acheter un item"):
    listing_id = discord.ui.TextInput(label="ID de l'annonce", placeholder="ID (#...)", min_length=1, max_length=10)
    quantity = discord.ui.TextInput(label="Quantité", placeholder="Combien ?", default="1", min_length=1, max_length=10)

    def __init__(self, marketplace_view):
        super().__init__()
        self.marketplace_view = marketplace_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            l_id, qty = int(self.listing_id.value), int(self.quantity.value)
            gid, bid = str(interaction.guild_id), str(interaction.user.id)
            
            # 1. Récupération de l'annonce
            listing = get_marketplace_listing(l_id, gid)
            if not listing: return await interaction.response.send_message("❌ Annonce introuvable.", ephemeral=True)
            if bid == listing['seller_id']: return await interaction.response.send_message("❌ Vos propres items.", ephemeral=True)
            if qty <= 0 or qty > listing['quantity']: return await interaction.response.send_message(f"❌ Stock insuffisant ({listing['quantity']}).", ephemeral=True)
            
            # 2. Vérification du solde
            total = qty * listing['price_per_unit']
            if get_user_wallet(gid, bid) < total: return await interaction.response.send_message("❌ Fonds insuffisants.", ephemeral=True)

            # 3. Transfert d'argent
            update_user_wallet(gid, bid, -total)
            update_user_wallet(gid, listing['seller_id'], total)
            
            # 4. Mise à jour Inventaire
            inv = update_inventory_quantity(get_inventaire(gid, bid), listing['item_name'], qty)
            update_inventaire(gid, bid, inv)

            # 5. Mise à jour de l'annonce
            if qty == listing['quantity']:
                execute_query("UPDATE marketplace_listings SET status = ? WHERE listing_id = ? AND guild_id = ?", ('sold', l_id, gid))
            else:
                execute_query("UPDATE marketplace_listings SET quantity = quantity - ? WHERE listing_id = ? AND guild_id = ?", (qty, l_id, gid))

            # 6. Statistiques (séparées en 2 requêtes pour la compatibilité MongoDB helper)
            # Mise à jour des compteurs (incréments)
            execute_query("UPDATE user_stats SET total_purchases = total_purchases + ? WHERE guild_id = ? AND user_id = ?", (1, gid, bid))
            execute_query("UPDATE user_stats SET items_bought = items_bought + ? WHERE guild_id = ? AND user_id = ?", (qty, gid, bid))
            execute_query("UPDATE user_stats SET money_spent = money_spent + ? WHERE guild_id = ? AND user_id = ?", (total, gid, bid))
            
            execute_query("UPDATE user_stats SET total_sales = total_sales + ? WHERE guild_id = ? AND user_id = ?", (1, gid, listing['seller_id']))
            execute_query("UPDATE user_stats SET items_sold = items_sold + ? WHERE guild_id = ? AND user_id = ?", (qty, gid, listing['seller_id']))
            execute_query("UPDATE user_stats SET money_earned = money_earned + ? WHERE guild_id = ? AND user_id = ?", (total, gid, listing['seller_id']))

            # 7. Réponse
            await interaction.response.send_message(f"✅ Achat de {qty}x {listing['item_name']} réussi !", ephemeral=True)
            
            # Mise à jour automatique de l'interface désactivée à la demande de l'utilisateur
                
        except Exception as e:
            print(f"DEBUG: Critical error in on_submit: {e}")
            import traceback
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Erreur lors de l'achat: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Erreur lors du rafraîchissement: {e}", ephemeral=True)

class SellToStateSelect(discord.ui.Select):
    def __init__(self, marketplace_view):
        self.marketplace_view = marketplace_view
        inv = get_inventaire(str(marketplace_view.ctx.guild.id), str(marketplace_view.ctx.author.id))
        options = []
        from .catalogue import catalogue_items
        def find_p(name):
            n = name.lower()
            for items in catalogue_items.values():
                for it in items:
                    if it["name"].lower() == n or it["name"].lower() in n: return it["price"]
                    if "variants" in it:
                        for vn in it["variants"].values():
                            if vn.lower() == n: return it["price"]
            return 0
        if inv:
            for iname, data in inv.items():
                if iname == "minerals": continue
                qty = data.get("quantity", 0) if isinstance(data, dict) else data
                if isinstance(qty, int) and qty > 0:
                    bp = find_p(iname)
                    if bp > 0: options.append(discord.SelectOption(label=f"{iname} (x{qty})", description=f"Prix: {format_price(bp*0.5)}/u", value=iname))
        if not options: options.append(discord.SelectOption(label="Aucun item", value="none"))
        super().__init__(placeholder="Vendre à l'État (50%)", options=options[:25])
    async def callback(self, interaction):
        if self.values[0] != "none": await interaction.response.send_modal(SellToStateModal(self.values[0], self.marketplace_view))

class SellToStateModal(discord.ui.Modal, title="Vendre à l'État"):
    quantity = discord.ui.TextInput(label="Quantité", placeholder="Combien ?", default="1")
    def __init__(self, item_name, marketplace_view):
        super().__init__()
        self.item_name, self.marketplace_view = item_name, marketplace_view
    async def on_submit(self, interaction):
        try:
            qty = int(self.quantity.value)
            gid, uid = str(interaction.guild_id), str(interaction.user.id)
            inv = get_inventaire(gid, uid)
            cur = get_inventory_quantity(inv, self.item_name)
            if qty <= 0 or qty > cur: return await interaction.response.send_message("❌ Quantité invalide.", ephemeral=True)
            bp = 0
            from .catalogue import catalogue_items
            n = self.item_name.lower()
            for items in catalogue_items.values():
                for it in items:
                    if it["name"].lower() == n or it["name"].lower() in n: bp = it["price"]; break
                    if "variants" in it:
                        for vn in it["variants"].values():
                            if vn.lower() == n: bp = it["price"]; break
                if bp > 0: break
            if bp == 0: return await interaction.response.send_message("❌ Prix non trouvé.", ephemeral=True)
            gain = int(bp * 0.5) * qty
            view = discord.ui.View()
            btn = discord.ui.Button(label="Confirmer", style=discord.ButtonStyle.danger)
            async def cb(inter):
                i2 = get_inventaire(gid, uid)
                if get_inventory_quantity(i2, self.item_name) < qty: return await inter.response.send_message("❌ Stock insuffisant.", ephemeral=True)
                update_inventaire(gid, uid, update_inventory_quantity(i2, self.item_name, -qty))
                update_user_wallet(gid, uid, gain)
                await inter.response.edit_message(content=f"✅ Vendu pour {format_price(gain)} !", view=None)
            btn.callback = cb
            view.add_item(btn)
            await interaction.response.send_message(f"Vendre {qty}x {self.item_name} pour {format_price(gain)} ?", view=view, ephemeral=True)
        except: await interaction.response.send_message("❌ Erreur.", ephemeral=True)

class StateOrdersSelect(discord.ui.Select):
    def __init__(self, marketplace_view):
        self.marketplace_view = marketplace_view
        orders = fetch_all("SELECT order_id, item_name, quantity_requested, quantity_fulfilled, price_per_unit, expires_at FROM state_orders WHERE guild_id = ? AND status = 'active' AND expires_at > ?", (str(marketplace_view.ctx.guild.id), int(datetime.now().timestamp())))
        options = []
        for o in orders:
            rem = o[2] - o[3]
            if rem > 0: options.append(discord.SelectOption(label=f"#{o[0]}: {o[1]}", description=f"Demande: {rem} | Prix: {format_price(o[4])}/u", value=f"{o[0]}|{o[1]}|{rem}|{o[4]}"))
        if not options: options.append(discord.SelectOption(label="Aucune commande", value="none"))
        super().__init__(placeholder="🚨 Commandes de l'État", options=options[:25])
    async def callback(self, interaction):
        if self.values[0] != "none":
            v = self.values[0].split("|")
            await interaction.response.send_modal(FulfillStateOrderModal(int(v[0]), v[1], int(v[2]), int(v[3]), self.marketplace_view))

class FulfillStateOrderModal(discord.ui.Modal):
    def __init__(self, order_id, item_name, max_qty, price, marketplace_view):
        super().__init__(title=f"Vendre : {item_name}")
        self.order_id, self.item_name, self.max_qty, self.price, self.marketplace_view = order_id, item_name, max_qty, price, marketplace_view
        self.quantity = discord.ui.TextInput(label=f"Quantité (Max: {max_qty})", default="1", min_length=1, max_length=10, required=True)
        self.add_item(self.quantity)
    async def on_submit(self, interaction):
        try:
            qty = int(self.quantity.value)
            if qty <= 0 or qty > self.max_qty: return await interaction.response.send_message("❌ Quantité invalide.", ephemeral=True)
            gid, uid = str(interaction.guild_id), str(interaction.user.id)
            inv = get_inventaire(gid, uid)
            if get_inventory_quantity(inv, self.item_name) < qty: return await interaction.response.send_message("❌ Stock insuffisant.", ephemeral=True)
            order = fetch_one("SELECT quantity_requested, quantity_fulfilled FROM state_orders WHERE order_id = ? AND guild_id = ? AND status = 'active'", (self.order_id, gid))
            if not order: return await interaction.response.send_message("❌ Commande inactive.", ephemeral=True)
            if order[1] + qty > order[0]: qty = order[0] - order[1]
            gain = qty * self.price
            update_inventaire(gid, uid, update_inventory_quantity(inv, self.item_name, -qty))
            update_user_wallet(gid, uid, gain)
            new_ful = order[1] + qty
            execute_query("UPDATE state_orders SET quantity_fulfilled = ?, status = ? WHERE order_id = ? AND guild_id = ?", (new_ful, 'completed' if new_ful >= order[0] else 'active', self.order_id, gid))
            await interaction.response.send_message(f"✅ Vendu {qty}x {self.item_name} pour {format_price(gain)} !", ephemeral=True)
            await self.marketplace_view.refresh_marketplace(interaction)
        except: await interaction.response.send_message("❌ Erreur.", ephemeral=True)

class MarketplaceView(discord.ui.View):
    def __init__(self, ctx, marketplace):
        super().__init__(timeout=180)
        self.ctx, self.marketplace = ctx, marketplace
        self.current_page, self.items_per_page = 1, 5
        self.current_category, self.message = "all", None
        self.add_main_components()

    def add_main_components(self):
        self.clear_items(); self.add_item(CategorySelect(self))
        for l, e, s, cb, r in [("Acheter", "🛒", discord.ButtonStyle.primary, self.buy_callback, 1), ("Vendre", "💰", discord.ButtonStyle.success, self.sell_callback, 1), ("Mes Offres", "📋", discord.ButtonStyle.secondary, self.my_listings_callback, 1), ("Commandes État", "🚨", discord.ButtonStyle.primary, self.state_orders_callback, 2), ("Vendre à l'État", "🏛️", discord.ButtonStyle.danger, self.sell_state_callback, 2), ("Stats", "📊", discord.ButtonStyle.secondary, self.stats_callback, 2)]:
            btn = discord.ui.Button(label=l, emoji=e, style=s, row=r); btn.callback = cb; self.add_item(btn)
        self.btn_prev = discord.ui.Button(label="◀️", style=discord.ButtonStyle.gray, row=3); self.btn_prev.callback = self.prev_page_callback; self.add_item(self.btn_prev)
        self.btn_next = discord.ui.Button(label="▶️", style=discord.ButtonStyle.gray, row=3); self.btn_next.callback = self.next_page_callback; self.add_item(self.btn_next)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Seul l'utilisateur ayant lancé la commande peut interagir avec ce menu.", ephemeral=True)
            return False
        return True

    async def buy_callback(self, interaction): await interaction.response.send_modal(BuyModal(self))
    async def sell_callback(self, interaction): self.clear_items(); self.add_item(SellSelect(self)); self.add_back_button(); await interaction.response.edit_message(view=self)
    async def my_listings_callback(self, interaction): self.clear_items(); self.add_item(MyListingsSelect(self)); self.add_back_button(); await interaction.response.edit_message(view=self)
    async def state_orders_callback(self, interaction): self.clear_items(); self.add_item(StateOrdersSelect(self)); self.add_back_button(); await interaction.response.edit_message(view=self)
    async def sell_state_callback(self, interaction): self.clear_items(); self.add_item(SellToStateSelect(self)); self.add_back_button(); await interaction.response.edit_message(view=self)
    async def stats_callback(self, interaction):
        s = self.marketplace.get_user_stats(str(interaction.guild_id), str(interaction.user.id))
        e = discord.Embed(title="📊 Stats Marketplace", color=0x2f3136)
        e.add_field(name="📈 Vendeur", value=f"Ventes: {s['total_sales']}\nGains: {format_price(s['money_earned'])}")
        e.add_field(name="🛍️ Acheteur", value=f"Achats: {s['total_purchases']}\nDépenses: {format_price(s['money_spent'])}")
        await interaction.response.send_message(embed=e, ephemeral=True)
    async def prev_page_callback(self, interaction):
        if self.current_page > 1: self.current_page -= 1; await self.update_message(interaction)
        else: await interaction.response.defer()
    async def next_page_callback(self, interaction): self.current_page += 1; await self.update_message(interaction)
    def add_back_button(self):
        btn = discord.ui.Button(label="Retour", emoji="⬅️", style=discord.ButtonStyle.gray, row=4); btn.callback = self.back_callback; self.add_item(btn)
    async def back_callback(self, interaction): self.add_main_components(); await self.update_message(interaction)

    async def update_message(self, interaction=None):
        try:
            gid = str(self.ctx.guild.id)
            listings = fetch_all("SELECT listing_id, item_name, quantity, price_per_unit, seller_id, expires_at, status FROM marketplace_listings WHERE guild_id = ? AND status = 'active'", (gid,))
            now = int(datetime.now().timestamp())
            listings = [l for l in listings if l[5] > now]
            if self.current_category != "all": listings = [l for l in listings if self.marketplace.get_item_category(l[1]) == self.current_category]
            listings.sort(key=lambda x: x[0] or 0, reverse=True)
            total_pages = max(1, (len(listings) + self.items_per_page - 1) // self.items_per_page)
            self.current_page = max(1, min(self.current_page, total_pages))
            current = listings[(self.current_page - 1) * self.items_per_page : self.current_page * self.items_per_page]
            embed = discord.Embed(title=f"🏪 Marketplace - {self.current_category.capitalize()}", color=0x2f3136)
            if not current: embed.description = "Aucune annonce."
            else:
                for l in current:
                    seller = self.ctx.guild.get_member(int(l[4]))
                    sname = seller.display_name if seller else f"ID: {l[4]}"
                    embed.add_field(name=f"📦 {l[1]} (ID: #{l[0]})", value=f"**Prix:** {format_price(l[3])}/u\n**Stock:** {l[2]}\n**Vendeur:** {sname}", inline=True)
            embed.set_footer(text=f"Page {self.current_page}/{total_pages}")
            self.btn_prev.disabled = self.current_page <= 1
            self.btn_next.disabled = self.current_page >= total_pages
            if interaction:
                if not interaction.response.is_done(): await interaction.response.edit_message(embed=embed, view=self)
                else: await interaction.edit_original_response(embed=embed, view=self)
            elif self.message: await self.message.edit(embed=embed, view=self)
            else: self.message = await self.ctx.send(embed=embed, view=self)
        except Exception as e: print(f"Error update_message: {e}")

    async def refresh_marketplace(self, interaction): self.add_main_components(); await self.update_message(interaction)

def safe_int_convert(value, default=0):
    try: return int(value) if value is not None else default
    except: return default

def get_marketplace_listing(listing_id, guild_id):
    try:
        r = fetch_one("SELECT listing_id, seller_id, item_name, quantity, price_per_unit, description, created_at, expires_at, status FROM marketplace_listings WHERE listing_id = ? AND guild_id = ? AND status = 'active'", (listing_id, guild_id))
        if not r: return None
        return {'listing_id': int(r[0]), 'seller_id': str(r[1]), 'item_name': str(r[2]), 'quantity': int(r[3]), 'price_per_unit': int(r[4]), 'description': str(r[5]), 'created_at': int(r[6]), 'expires_at': int(r[7]), 'status': str(r[8])}
    except: return None

class Marketplace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ensure_tables_exist()
        self.check_expired_listings.start()
        self.manage_state_orders.start()

    def ensure_tables_exist(self):
        execute_query("CREATE TABLE IF NOT EXISTS marketplace_listings (listing_id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, seller_id TEXT, item_name TEXT, quantity INTEGER, price_per_unit INTEGER, description TEXT, created_at INTEGER, expires_at INTEGER, status TEXT DEFAULT 'active')")
        execute_query("CREATE TABLE IF NOT EXISTS user_stats (guild_id TEXT, user_id TEXT, total_sales INTEGER DEFAULT 0, total_purchases INTEGER DEFAULT 0, items_sold INTEGER DEFAULT 0, items_bought INTEGER DEFAULT 0, money_earned INTEGER DEFAULT 0, money_spent INTEGER DEFAULT 0, flash_sales INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id))")
        execute_query("CREATE TABLE IF NOT EXISTS state_orders (order_id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, item_name TEXT, quantity_requested INTEGER, quantity_fulfilled INTEGER DEFAULT 0, price_per_unit INTEGER, expires_at INTEGER, status TEXT DEFAULT 'active')")

    def cog_unload(self): self.check_expired_listings.cancel(); self.manage_state_orders.cancel()

    @tasks.loop(minutes=30)
    async def manage_state_orders(self):
        now = int(datetime.now().timestamp())
        for guild in self.bot.guilds:
            gid = str(guild.id)
            execute_query("UPDATE state_orders SET status = ? WHERE expires_at < ? AND status = ? AND guild_id = ?", ('expired', now, 'active', gid))
            active = fetch_all("SELECT order_id FROM state_orders WHERE status = 'active' AND guild_id = ?", (gid,))
            if len(active) < 10:
                import random
                all_i = []
                for cat, items in catalogue_items.items():
                    for it in items:
                        all_i.append({"name": it["name"], "price": it["price"]})
                        if "variants" in it: all_i.extend([{"name": v, "price": it["price"]} for v in it["variants"].values()])
                if all_i:
                    for _ in range(10 - len(active)):
                        c = random.choice(all_i)
                        execute_query("INSERT INTO state_orders (guild_id, item_name, quantity_requested, price_per_unit, expires_at, status) VALUES (?, ?, ?, ?, ?, ?)", (gid, c["name"], random.randint(10, 50), int(c["price"] * 0.8), int((datetime.now() + timedelta(hours=12)).timestamp()), 'active'))

    @tasks.loop(minutes=30)
    async def check_expired_listings(self):
        expired = fetch_all("SELECT guild_id, seller_id, item_name, quantity FROM marketplace_listings WHERE expires_at < ? AND status = 'active'", (int(datetime.now().timestamp()),))
        for gid, sid, iname, qty in expired:
            try:
                inv = get_inventaire(gid, sid)
                update_inventaire(gid, sid, update_inventory_quantity(inv, iname, qty))
                execute_query("UPDATE marketplace_listings SET status = ? WHERE guild_id = ? AND seller_id = ? AND item_name = ?", ('expired', gid, sid, iname))
            except: pass

    @commands.command(name="marketplace", aliases=["mp", "market"])
    async def marketplace(self, ctx):
        await ctx.reply(embed=discord.Embed(title="🏪 Marketplace", description="Marché entre joueurs.", color=0x000000), view=MarketplaceView(ctx, self))

    def get_user_stats(self, guild_id, user_id):
        r = fetch_one("SELECT total_sales, total_purchases, money_earned, money_spent FROM user_stats WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        if not r:
            execute_query("INSERT INTO user_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
            return {"total_sales":0, "total_purchases":0, "money_earned":0, "money_spent":0}
        return {"total_sales":r[0], "total_purchases":r[1], "money_earned":r[2], "money_spent":r[3]}

    def get_item_category(self, name):
        category = "divers"
        n = name.lower()
        for cat, items in catalogue_items.items():
            for it in items:
                if it["name"].lower() == n or it["name"].lower() in n: category = cat; break
                if "variants" in it:
                    for v in it["variants"].values():
                        if v.lower() == n: category = cat; break
            if category != "divers": break
        mapping = {"Véhicules": "véhicules", "Propriétés": "immobilier", "Objets Tech": "tech", "Art & Collection": "luxe", "Mode & Accessoires": "luxe", "Sécurité & Armes": "ressources"}
        return mapping.get(category, "divers")

async def setup(bot): await bot.add_cog(Marketplace(bot))
