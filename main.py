import discord
from discord.ext import commands, tasks
from database import init_db
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from keep_alive import start_server

load_dotenv()

intents = discord.Intents.all()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="+", intents=intents, help_command=None)

    async def setup_hook(self):
        init_db()
        
        # Démarrer le serveur web pour Render
        await start_server()
        
        # Lancer le self-ping
        self.self_ping.start()
        self.update_crypto_price_task.start()
        
        # Enregistrement des vues persistantes
        from commands.security import CaptchaView
        from commands.tickets import TicketView, TicketCloseView
        self.add_view(CaptchaView())
        self.add_view(TicketView())
        self.add_view(TicketCloseView())
        
        # Charger les extensions
        for filename in os.listdir("./commands"):
            if filename.endswith(".py"):
                try:
                    await self.load_extension(f"commands.{filename[:-3]}")
                    print(f"✅ Extension chargée : {filename}")
                except Exception as e:
                    print(f"❌ Erreur lors du chargement de {filename}: {str(e)}")

    @tasks.loop(hours=1)
    async def update_crypto_price_task(self):
        """Met à jour le prix de la crypto toutes les heures"""
        try:
            from database import get_crypto_data, update_crypto_data, is_economy_enabled
            import random
            from datetime import datetime
            
            # On ne met à jour que si l'économie est activée sur au moins un serveur actif
            # Ici on simplifie en vérifiant si l'économie est activée en général
            # (Note: Comme le bot peut être sur plusieurs serveurs, on pourrait boucler,
            # mais ici on va juste vérifier si le bot doit faire tourner ses tâches éco)
            
            data = get_crypto_data()
            current_price = data["current_price"]
            history = data["history"]
            
            # Volatilité : de -15% à +20%
            change_percent = random.uniform(-0.15, 0.20)
            new_price = int(current_price * (1 + change_percent))
            
            if new_price < 10: new_price = 10 # Crash total empêché
            if new_price > 10000: new_price = 10000 # Plafond max
            
            history.append({"price": new_price, "timestamp": datetime.now().isoformat()})
            # Garder seulement les 24 dernières valeurs
            if len(history) > 24:
                history = history[-24:]
                
            update_crypto_data(new_price, history)
            print(f"📈 Crypto mise à jour : {new_price} coins")
        except Exception as e:
            print(f"⚠️ Erreur Crypto Update : {e}")

    @update_crypto_price_task.before_loop
    async def before_crypto_update(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=10)
    async def self_ping(self):
        """Ping l'URL externe de Render pour éviter la mise en veille"""
        url = os.getenv("RENDER_EXTERNAL_URL")
        if not url:
            # Si l'URL n'est pas définie, on tente en local par défaut
            url = "http://localhost:8080"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        print(f"📡 Self-Ping réussi sur {url}")
            except Exception as e:
                print(f"⚠️ Échec du Self-Ping : {e}")

    @self_ping.before_loop
    async def before_self_ping(self):
        await self.wait_until_ready()

    async def on_ready(self):
        print(f"---")
        print(f"Bot connecté en tant que : {self.user}")
        print(f"ID : {self.user.id}")
        print(f"---")

bot = MyBot()

# --- PROTECTION ANTI-SPAM COMMANDES ---
# Limite : 3 commandes par 5 secondes par utilisateur
command_cooldowns = commands.CooldownMapping.from_cooldown(3, 5, commands.BucketType.user)

@bot.check
async def global_cooldown_check(ctx: commands.Context):
    if await bot.is_owner(ctx.author):
        return True
    
    bucket = command_cooldowns.get_bucket(ctx.message)
    retry_after = bucket.update_rate_limit()
    if retry_after:
        # Optionnel : envoyer un message d'alerte une seule fois
        # await ctx.reply(f"⚠️ Doucement ! Réessaie dans {retry_after:.1f}s.", delete_after=3)
        return False
    return True

# Check global pour les permissions personnalisées
@bot.check
async def custom_permissions_check(ctx: commands.Context):
    from database import get_command_permissions, get_global_lock
    if ctx.guild is None:
        return True
    
    # 0. Emergency Lock (Seul l'owner passe)
    if get_global_lock(ctx.guild.id):
        if await bot.is_owner(ctx.author):
            return True
        return False

    # 1. Bypass Owner et Administrateur
    if ctx.author.guild_permissions.administrator or await bot.is_owner(ctx.author):
        return True

    # 2. Vérification des permissions personnalisées (command_config)
    allowed_roles = get_command_permissions(ctx.guild.id, ctx.command.name)
    user_roles_ids = [str(role.id) for role in ctx.author.roles]
    
    if allowed_roles and any(role_id in allowed_roles for role_id in user_roles_ids):
        return True

    # 3. Fallback : Vérification des permissions natives de Discord
    # On définit ici les permissions par défaut pour les commandes sensibles
    native_perms = {
        # Modération
        "kick": ctx.author.guild_permissions.kick_members,
        "ban": ctx.author.guild_permissions.ban_members,
        "warn": ctx.author.guild_permissions.manage_messages,
        "clear": ctx.author.guild_permissions.manage_messages,
        "warnings": ctx.author.guild_permissions.manage_messages,
        "clearwarnings": ctx.author.guild_permissions.manage_messages,
        
        # Administration & Finance
        "addmoney": False, # Toujours restreint (sauf admin/owner ou rôle config)
        "eco": ctx.author.guild_permissions.manage_guild,
        "nuke": ctx.author.guild_permissions.administrator,
        "backup": ctx.author.guild_permissions.administrator,
        
        # Configuration Système
        "setup_captcha": ctx.author.guild_permissions.manage_guild,
        "setup_tickets": ctx.author.guild_permissions.manage_guild,
        "ticket_roles": ctx.author.guild_permissions.manage_guild,
        "setup_voice": ctx.author.guild_permissions.manage_guild,
        "setup_welcome": ctx.author.guild_permissions.manage_guild,
        "setup_welcome_image": ctx.author.guild_permissions.manage_guild,
        "setup_leave": ctx.author.guild_permissions.manage_guild,
        
        # Panneaux & Outils Staff
        "send_captcha_panel": ctx.author.guild_permissions.manage_guild,
        "send_ticket_panel": ctx.author.guild_permissions.manage_guild,
        "lfg_create": ctx.author.guild_permissions.manage_messages,
        "delitem": ctx.author.guild_permissions.manage_messages, # Pour modérer l'inventaire des autres (si implémenté)
    }

    # Si la commande est dans la liste, on vérifie la permission native
    if ctx.command.name in native_perms:
        return native_perms[ctx.command.name]

    # Si ce n'est pas une commande sensible et qu'aucun rôle n'est configuré, on laisse passer
    if not allowed_roles:
        return True
        
    return False

# Bloquer les commandes économie si désactivée
@bot.check
async def global_economy_toggle_check(ctx: commands.Context):
    from database import is_economy_enabled
    if ctx.guild is None:
        return True
    economy_commands = [
        "bal", "beg", "daily", "work", "pay", "shop", "buy", "inventory", 
        "job", "jobs", "entreprise", "leaderboard", "blackjack", "roulette", 
        "rouletteRusse", "rlr", "slot", "duel", "mine", "miner", "marketplace",
        "transaction", "bank", "invest", "catalogue", "rob", "scout", "heist",
        "police", "bounty", "arrest", "timer", "crash", "with", "deposit",
        "phone", "sell_drugs"
    ]
    cmd_name = ctx.command.qualified_name.split()[0] if ctx.command else ""
    if cmd_name in economy_commands:
        enabled = is_economy_enabled(ctx.guild.id)
        if not enabled:
            await ctx.reply(embed=discord.Embed(description="🛑 L'économie est désactivée sur ce serveur.", color=discord.Color.red()), ephemeral=True)
            return False
    return True

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    if isinstance(error, commands.MissingPermissions):
        return
        await ctx.reply("❌ Tu n'as pas les permissions nécessaires (Administrateur) pour cette commande.")
        
    #if isinstance(error, commands.CheckFailure): return 
    #print(f"❌ Erreur sur la commande {ctx.command}: {error}")
    #await ctx.reply(f"⚠️ Une erreur est survenue : `{error}`")

async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
