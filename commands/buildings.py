import discord
from discord.ext import commands
from datetime import datetime, timedelta
from database import (
    get_entreprise_buildings, add_building, upgrade_building,
    get_building_cost, get_building_revenue, get_building_maintenance,
    get_building_work_required, get_building_upgrade_cost,
    BUILDING_TYPES, execute_query, fetch_one
)

class Buildings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def plant(self, ctx, plant_type: str):
        """Planter une nouvelle plante"""
        water_bottles = fetch_one("SELECT quantity FROM user_items WHERE user_id = ? AND item_name = 'Bouteille d''eau'", (ctx.author.id,))
        if not water_bottles or water_bottles[0] < 1:
            return await ctx.send("❌ Bouteille d'eau requise.")
        
        if fetch_one("SELECT 1 FROM user_plants WHERE user_id = ? AND plant_type = ?", (ctx.author.id, plant_type)):
            return await ctx.send("❌ Plante déjà en cours.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        execute_query("INSERT INTO user_plants (user_id, plant_type, planted_date, last_watered, growth_stage, water_days, total_days) VALUES (?, ?, ?, ?, 0, 1, 15)", (ctx.author.id, plant_type, now, now))
        execute_query("UPDATE user_items SET quantity = quantity - 1 WHERE user_id = ? AND item_name = 'Bouteille d''eau'", (ctx.author.id,))
        await ctx.send(f"🌱 {plant_type} planté(e) !")

async def setup(bot):
    await bot.add_cog(Buildings(bot))
