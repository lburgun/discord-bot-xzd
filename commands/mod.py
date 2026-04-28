import discord
from discord.ext import commands
from database import add_warning, get_warnings, clear_warnings

class WarnDMView(discord.ui.View):
    def __init__(self, member, moderator, reason, count, guild_name):
        super().__init__(timeout=60)
        self.member = member
        self.moderator = moderator
        self.reason = reason
        self.count = count
        self.guild_name = guild_name

    @discord.ui.button(label="Envoyer en Privé", style=discord.ButtonStyle.blurple, emoji="📩")
    async def send_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=f"⚠️ Avertissement reçu",
            description=f"Tu as reçu un avertissement sur le serveur **{self.guild_name}**.",
            color=0xff4654 # Rouge Valorant/Alerte
        )
        embed.add_field(name="⚖️ Raison", value=self.reason, inline=False)
        embed.add_field(name="🛡️ Modérateur", value=self.moderator.display_name, inline=True)
        embed.add_field(name="📊 Total de warns", value=str(self.count), inline=True)
        embed.set_footer(text="Merci de respecter le règlement du serveur.")
        embed.timestamp = discord.utils.utcnow()

        try:
            await self.member.send(embed=embed)
            await interaction.response.send_message(f"✅ Sanction envoyée en privé à **{self.member.display_name}**.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Impossible d'envoyer un message privé à **{self.member.display_name}** (DMs fermés).", ephemeral=True)
        
        # Supprimer le message initial de confirmation
        await interaction.message.delete()

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
        """Expulser un membre"""
        try:
            await member.kick(reason=reason)
            await ctx.send(f"✅ **{member}** a été expulsé. Raison : {reason}")
        except Exception as e:
            await ctx.send(f"❌ Erreur : {e}")

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
        """Bannir un membre"""
        try:
            await member.ban(reason=reason)
            await ctx.send(f"✅ **{member}** a été banni. Raison : {reason}")
        except Exception as e:
            await ctx.send(f"❌ Erreur : {e}")

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        """Donner un avertissement à un membre"""
        add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        
        warns = get_warnings(ctx.guild.id, member.id)
        count = len(warns)
        
        embed = discord.Embed(
            title="🔨 Nouveau Warn", 
            description=f"**{member.mention}** a été averti.", 
            color=0x2b2d31
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
        embed.add_field(name="Total", value=f"`{count}` avertissement(s)", inline=True)
        
        view = WarnDMView(member, ctx.author, reason, count, ctx.guild.name)
        msg = await ctx.send(embed=embed, view=view)

        if count >= 3:
            alert_embed = discord.Embed(
                title="⚠️ Alerte Sanction",
                description=f"Le membre {member.mention} a atteint **{count}** avertissements.",
                color=discord.Color.red()
            )
            await ctx.send(embed=alert_embed)

    @commands.command(name="clearwarnings")
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(self, ctx, member: discord.Member):
        """Réinitialise les avertissements d'un membre"""
        clear_warnings(ctx.guild.id, member.id)
        embed = discord.Embed(
            description=f"✅ Les avertissements de **{member.display_name}** ont été réinitialisés.",
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @commands.command(name="warnings")
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx, member: discord.Member):
        """Voir les avertissements d'un membre"""
        warns = get_warnings(ctx.guild.id, member.id)
        if not warns:
            return await ctx.send(f"✅ **{member}** n'a aucun avertissement.")
        
        embed = discord.Embed(title=f"Avertissements de {member}", color=discord.Color.yellow())
        for idx, (mod_id, reason, timestamp) in enumerate(warns, 1):
            mod = ctx.guild.get_member(int(mod_id)) or f"ID: {mod_id}"
            embed.add_field(name=f"Warn #{idx} - {timestamp}", value=f"**Mod:** {mod}\n**Raison:** {reason}", inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 10):
        """Supprime un nombre précis de messages (max 100)"""
        if amount < 1 or amount > 100:
            return await ctx.send("❌ Merci de préciser un nombre entre 1 et 100.")
        
        deleted = await ctx.channel.purge(limit=amount + 1)
        
        embed = discord.Embed(
            description=f"✅ **{len(deleted)-1}** messages ont été supprimés.",
            color=0x2b2d31
        )
        msg = await ctx.send(embed=embed)
        await msg.delete(delay=5)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
