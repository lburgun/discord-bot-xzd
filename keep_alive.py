from aiohttp import web
import asyncio
import aiohttp
import logging

async def home(request):
    return web.Response(text="Bot is alive!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', home)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("✅ Serveur Keep-Alive démarré sur le port 8080")

async def self_ping():
    """Ping le serveur toutes les 14 minutes pour éviter la mise en veille sur Render"""
    await asyncio.sleep(30) # Attendre que le serveur démarre
    url = "http://localhost:8080" # Sur Render, localhost fonctionne en interne
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        print("📡 Self-Ping réussi (Maintien en vie)")
            except Exception as e:
                print(f"⚠️ Échec du Self-Ping : {e}")
            
            await asyncio.sleep(14 * 60) # 14 minutes
