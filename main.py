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

# Check global pour les permissions personnalisées
@bot.check
async def custom_permissions_check(ctx: commands.Context):
    from database import get_command_permissions
    if ctx.guild is None:
        return True
    allowed_roles = get_command_permissions(ctx.guild.id, ctx.command.name)
    if allowed_roles:
        user_roles_ids = [str(role.id) for role in ctx.author.roles]
        if any(role_id in allowed_roles for role_id in user_roles_ids):
            return True
    return True

# Bloquer les commandes économie si désactivée
@bot.check
async def global_economy_toggle_check(ctx: commands.Context):
    from database import is_economy_enabled
    if ctx.guild is None:
        return True
    economy_commands = [
        "bal", "beg", "daily", "work", "pay", "shop", "buy", "inventory", 
        "job", "entreprise", "leaderboard", "blackjack", "roulette", 
        "rouletteRusse", "slot", "duel", "mine", "miner", "marketplace",
        "plant", "water", "harvest", "transaction", "bank", "invest"
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
        await ctx.reply("❌ Tu n'as pas les permissions nécessaires (Administrateur) pour cette commande.")
        return
    if isinstance(error, commands.CheckFailure): return 
    print(f"❌ Erreur sur la commande {ctx.command}: {error}")
    await ctx.reply(f"⚠️ Une erreur est survenue : `{error}`")

async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
