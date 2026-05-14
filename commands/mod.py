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
            title="⚠️ Avertissement reçu",
            description=f"Tu as reçu un avertissement sur le serveur **{self.guild_name}**.",
            color=0xff4654
        )
        embed.add_field(name="⚖️ Raison", value=self.reason, inline=False)
        embed.add_field(name="🛡️ Modérateur", value=self.moderator.display_name, inline=True)
        embed.add_field(name="📊 Total de warns", value=str(self.count), inline=True)
        embed.set_footer(text="Merci de respecter le règlement du serveur.")
        embed.timestamp = discord.utils.utcnow()

        try:
            await self.member.send(embed=embed)
            await interaction.response.send_message(
                f"✅ Sanction envoyée en privé à **{self.member.display_name}**.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Impossible d'envoyer un message privé à **{self.member.display_name}**.",
                ephemeral=True
            )

        await interaction.message.delete()


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
        try:
            await member.kick(reason=reason)
            await ctx.send(f"✅ **{member}** a été expulsé. Raison : {reason}")
        except Exception as e:
            await ctx.send(f"❌ Erreur : {e}")

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
        try:
            await member.ban(reason=reason)
            await ctx.send(f"✅ **{member}** a été banni. Raison : {reason}")
        except Exception as e:
            await ctx.send(f"❌ Erreur : {e}")

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
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
        await ctx.send(embed=embed, view=view)

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
        clear_warnings(ctx.guild.id, member.id)
        embed = discord.Embed(
            description=f"✅ Les avertissements de **{member.display_name}** ont été réinitialisés.",
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @commands.command(name="warnings")
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx, member: discord.Member):
        warns = get_warnings(ctx.guild.id, member.id)
        if not warns:
            return await ctx.send(f"✅ **{member}** n'a aucun avertissement.")

        embed = discord.Embed(
            title=f"Avertissements de {member}",
            color=discord.Color.yellow()
        )

        for idx, (mod_id, reason, timestamp) in enumerate(warns, 1):
            mod = ctx.guild.get_member(int(mod_id)) or f"ID: {mod_id}"
            embed.add_field(
                name=f"Warn #{idx} - {timestamp}",
                value=f"**Mod:** {mod}\n**Raison:** {reason}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 10):
        if amount < 1 or amount > 100:
            return await ctx.send("❌ Merci de préciser un nombre entre 1 et 100.", delete_after=5)

        embed_loading = discord.Embed(
            description="🧹 Suppression en cours...",
            color=0x2b2d31
        )
        status_msg = await ctx.send(embed=embed_loading)

        now = discord.utils.utcnow()

        # 🔹 Étape 1 : suppression rapide (<14 jours)
        def is_recent(msg):
            return (now - msg.created_at).days < 14

        recent_deleted = await ctx.channel.purge(
            limit=amount + 1,
            check=is_recent,
            bulk=True
        )

        # 🔹 Étape 2 : suppression lente (>14 jours)
        old_deleted_count = 0
        async for msg in ctx.channel.history(limit=amount + 20):
            if (now - msg.created_at).days >= 14:
                try:
                    await msg.delete()
                    old_deleted_count += 1
                except:
                    pass

        total_deleted = (len(recent_deleted) - 1) + old_deleted_count

        embed_done = discord.Embed(
            description=f"✅ **{total_deleted}** messages supprimés.",
            color=0x2b2d31
        )

        await status_msg.edit(embed=embed_done)
        await status_msg.delete(delay=5)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
