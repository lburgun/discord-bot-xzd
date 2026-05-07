import random
from discord.ext import commands
import discord
from database import update_wallet, user_init, get_inventaire
from .catalogue import catalogue_items

class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_property_bonus(self, inventory):
        if not inventory:
            return 0, None
            
        max_bonus = 0
        best_property = None
        
        # Check for properties in inventory
        for item_name, data in inventory.items():
            # Check if this item is a property variant in the catalogue
            for prop in catalogue_items.get("Propriétés", []):
                for rarity, variant_name in prop.get("variants", {}).items():
                    if item_name.lower() == variant_name.lower():
                        # Determine bonus based on rarity
                        bonus = 0
                        if rarity == "common": bonus = 200
                        elif rarity == "uncommon": bonus = 500
                        elif rarity == "rare": bonus = 1000
                        elif rarity == "epic": bonus = 3000
                        elif rarity == "legendary": bonus = 10000
                        
                        if bonus > max_bonus:
                            max_bonus = bonus
                            best_property = variant_name
                            
        return max_bonus, best_property

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)  # 86400 secondes = 24h
    async def daily(self, ctx):
        user_init(ctx.guild.id,ctx.author.id)
        
        base_amount = random.randint(100, 300)
        
        # Get property bonus
        inventory = get_inventaire(str(ctx.guild.id), str(ctx.author.id))
        bonus, property_name = self.get_property_bonus(inventory)
        
        total_amount = base_amount + bonus
        update_wallet(ctx.guild.id,ctx.author.id, total_amount)

        desc = f"Tu as reçu **{base_amount} coins** pour ta récompense quotidienne !"
        if bonus > 0:
            desc += f"\n🏠 **Bonus locatif :** +{bonus} coins (Grâce à : *{property_name}*)"
            desc += f"\n💰 **Total perçu :** {total_amount} coins"

        embed = discord.Embed(
            title="🎁 Récompense quotidienne",
            description=desc,
            color=0x000000
        )

        await ctx.reply(embed=embed)

    @daily.error
    async def daily_error(self, ctx, error):
        from time import time
        if isinstance(error, commands.CommandOnCooldown):
            retry_after = round(error.retry_after, 1)
            future_time = int(time() + retry_after)
            embed = discord.Embed(
                description=(
                    f"⏳ Patiente encore, tu pourrass relancer cette commande <t:{future_time}:R>."
                ),
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

async def setup(bot):
   await bot.add_cog(Daily(bot))
