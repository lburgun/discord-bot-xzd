import random
import discord
from discord.ext import commands
from database import user_init, get_wallet_bank, update_wallet

class Rob(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    
    @commands.command(name = "rob")
    @commands.cooldown(1, 1800, commands.BucketType.user)  
    async def rob(self, ctx, member: commands.MemberConverter):
        attacker = ctx.author.id
        victim = member.id

        if attacker == victim : 
            embed = discord.Embed(
                description="❌ Tu ne peux pas t'auto voler.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return
        

        user_init(ctx.guild.id,ctx.author.id)
        user_init(ctx.guild.id,member.id)

        
        data1 = get_wallet_bank(ctx.guild.id,ctx.author.id)
        data2 = get_wallet_bank(ctx.guild.id,member.id)
        
        attacker_wallet = data1["wallet"]
        victim_wallet = data2["wallet"]
        


        if attacker_wallet < 500:
            embed = discord.Embed(
                description="❌ Tu as besoin d'au moins 500 coins sur ton wallet pour tenter un vol.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        if victim_wallet < 500:
            embed = discord.Embed(
                description="❌ La cible n'a pas assez d'argent (500 coins minimum dans son wallet) pour être volée.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        success = random.choice([True, False])
        if success:
            amount = random.randint(victim_wallet // 2, victim_wallet)
            update_wallet(ctx.guild.id,ctx.author.id, amount)
            update_wallet(ctx.guild.id,member.id,-amount)
            
            embed = discord.Embed(
                description=f"🕵️ Tu as volé **{amount} coins** à {member.display_name} !",
                color=0x000000
            )
            await ctx.reply(embed=embed)
        else:
            fine = random.randint(200, 500)
            update_wallet(ctx.guild.id,ctx.author.id,-fine) 
            embed = discord.Embed(
                description=f"🚨 Tu as échoué et perdu **{fine} coins** !",
                color=0x000000
            )
            await ctx.reply(embed=embed)
            



    @rob.error
    async def rob_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = int(error.retry_after)
            minutes, sec = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)

            time_str = ""
            if hours > 0:
                time_str += f"{hours}h "
            if minutes > 0:
                time_str += f"{minutes}m "
            time_str += f"{sec}s"

            embed = discord.Embed(
                description=f"⏳ Patiente encore {time_str.strip()} avant d'essayer de voler quelqu'un.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
        else:
            raise error




async def setup(bot):
    await bot.add_cog(Rob(bot))
