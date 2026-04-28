import discord
from discord.ext import commands
import random

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Liste complète et à jour des agents Valorant (jusqu'à Tejo/Vyse)
        self.agents = [
            "Brimstone", "Viper", "Omen", "Killjoy", "Cypher", "Sova", "Sage", "Phoenix", "Jett", "Reyna",
            "Raze", "Breach", "Skye", "Yoru", "Astra", "KAY/O", "Chamber", "Neon", "Fade", "Harbor",
            "Gekko", "Deadlock", "Iso", "Clove", "Vyse","Miks"
        ]

    @commands.command(name="valorant")
    async def valorant(self, ctx):
        """Choisit un agent Valorant aléatoire avec un bel embed"""
        agent = random.choice(self.agents)
        
        embed = discord.Embed(
            title="🎮 Sélection d'Agent Valorant",
            description=f"Le destin a choisi pour toi, **{ctx.author.display_name}** !",
            color=0xff4654 # Rouge caractéristique de Valorant
        )
        
        embed.add_field(name="🎯 Ton Agent", value=f"**{agent}**", inline=False)
        
        # Ajout d'une icône Valorant générique pour le style
        embed.set_thumbnail(url="https://images-ext-1.discordapp.net/external/vLzY_oF8X8n_DToZ0X3mZ9Qp_rZ-Y4_7n9WfO8N5e2M/https/logodownload.org/wp-content/uploads/2020/06/valorant-logo-1.png")
        
        embed.set_footer(text="Bonne chance pour ta game ! 🔫", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()

        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Fun(bot))
