import discord
from discord.ext import commands
from discord.ui import Button, View
from database import user_init, get_investissements, get_wallet_bank, update_investissements, update_bank
from datetime import datetime, timedelta

class ClaimButton(Button):
    def __init__(self,ctx, guild_id, user_id, label, disabled, style):
        super().__init__(style=style, label=label, disabled=disabled)
        self.guild_id = guild_id
        self.user_id = user_id
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Tu ne peux pas récupérer cet investissement.", ephemeral=True)
            return
        user_init(self.ctx.guild.id, self.ctx.author.id)
        data = get_investissements(self.ctx.guild.id, self.ctx.author.id)

        now = datetime.utcnow()
        end = datetime.fromisoformat(data["end"])

        if now < end:
            await interaction.response.send_message("⏳ L'investissement n'est pas encore terminé.", ephemeral=True)
            return


        user = get_wallet_bank(self.ctx.guild.id, self.ctx.author.id)
        
        reward = data["reward"]
        user["bank"] += reward
        update_investissements(self.ctx.guild.id, self.ctx.author.id,{})
        update_bank(self.ctx.guild.id, self.ctx.author.id,reward)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="📥 Récompense récupérée !",
                description=f"Tu as reçu **{reward} coins** dans ton portefeuille.",
                color=0x000000
            ),
            view=None
        )


class Invest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.investments = {
            "stande-de-limonade": {"price": 100, "duration": 1, "reward": 350, "description": "Vente de limonade"},
            "tableaux": {"price": 500, "duration": 2, "reward": 850, "description": "Tableaux modernes"},
            "voiture": {"price": 1000, "duration": 4, "reward": 4000, "description": "Rénovation ancienne voiture"},
            "garage": {"price": 20000, "duration": 7, "reward": 30000, "description": "Louez des places pour voitures."},
            "kiosque": {"price": 10000, "duration": 5, "reward": 16000, "description": "Revenus journaliers stables."},
            "ferme": {"price": 25000, "duration": 7, "reward": 37500, "description": "Vente d'œufs bio."},
            "magasin": {"price": 50000, "duration": 10, "reward": 80000, "description": "Profits de la vente de produits."},
            "taxi": {"price": 30000, "duration": 6, "reward": 45000, "description": "Transports urbains rentables."},
            "studio": {"price": 75000, "duration": 10, "reward": 120000, "description": "Ventes de streams et albums."},
            "mine": {"price": 100000, "duration": 14, "reward": 180000, "description": "Extraction de ressources rares."},
            "centre-commerciale": {"price": 500000, "duration": 20, "reward": 890000, "description": "Construction commerces"},
            "usine-nucleaire": {"price": 2000000, "duration": 32, "reward": 10000000, "description": "Construction usine nucléaire"}
        }

    @commands.command()
    async def invest(self, ctx, *, choice=None):
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        if choice is None:
            embed = discord.Embed(
                description="❌ Veuillez choisir un investissement ou utiliser `+invest list`.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        if choice.lower() == "list":
            embed = discord.Embed(
                title="📈 Investissements disponibles",
                color=0x000000
            )
            for name, info in self.investments.items():
                embed.add_field(
                    name=f"**{name.capitalize()}** *({info['price']} coins)*",
                    value=f"⏳ {info['duration']} jours | 💵 {info['reward']} coins\n📝 {info['description']}",
                    inline=False
                )
            await ctx.reply(embed=embed)
            return
        
        user_init(ctx.guild.id, ctx.author.id)
        user = get_investissements(ctx.guild.id, ctx.author.id)
        
        if choice.lower() == "status":
            inv = user
            if not(inv.get("duration",0) > 0):
                embed = discord.Embed(
                    description="ℹ️ Aucun investissement en cours.",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
                return

            start = datetime.fromisoformat(inv["start"])
            end = datetime.fromisoformat(inv["end"])
            now = datetime.utcnow()
            progress = max(0, (now - start).days)
            finished = now >= end
            timestamp = int(end.timestamp())
            embed = discord.Embed(
                title="⏳ Progression de l'investissement",
                description=f"📦 {inv['nom_invest'].capitalize()}\n🔁 {progress}/{inv['duration']} jours écoulés\nDisponible dans : <t:{timestamp}:R>",
                color=0x000000,
                
            )
            
            label = "📥 Récupérer les gains" if finished else "⏳ Pas encore terminé"
            style = discord.ButtonStyle.green if finished else discord.ButtonStyle.gray
            view = View()
            view.add_item(ClaimButton(ctx,guild_id, user_id, label=label, disabled=not finished, style=style))

            await ctx.reply(embed=embed, view=view)
            return

        
        name = choice.lower()
        if name not in self.investments:
            embed = discord.Embed(
                description="❌ Cet investissement n'existe pas. Utilise `+invest list`.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        
        if user.get("duration") > 0:
            embed = discord.Embed(
                description="⚠️ Tu as déjà un investissement en cours. Utilise `+invest status`.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        
        inv = self.investments[name]
        wallet_user = get_wallet_bank(ctx.guild.id, ctx.author.id)
        if wallet_user["bank"] < inv["price"]:
            embed = discord.Embed(
                description="💸 Tu n'as pas assez de coins pour investir dans ça.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        
        wallet_user["bank"] -= inv["price"]
        user["invest"] = {
            "nom_invest": name,
            "duration": inv["duration"],
            "reward": inv["reward"],
            "start": datetime.utcnow().isoformat(),
            "end": (datetime.utcnow() + timedelta(days=inv["duration"])).isoformat()
        }
        update_investissements(ctx.guild.id,ctx.author.id, user["invest"])
        

        embed = discord.Embed(
            title="✅ Investissement lancé",
            description=f"Tu as investi dans un **{name.capitalize()}** pour {inv['price']} coins.\nTu recevras {inv['reward']} coins dans {inv['duration']} jours.",
            color=0x000000
        )
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(Invest(bot))
