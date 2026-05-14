import discord
from discord.ext import commands
from database import add_warning, get_warnings, clear_warnings, get_config
import datetime
import re
from datetime import timedelta

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

    def parse_duration(self, duration: str):
        """Parse une durée type 1h, 30m, 1d en objet timedelta"""
        match = re.match(r"(\d+)([smhd])", duration.lower())
        if not match:
            return None
        
        amount, unit = match.groups()
        amount = int(amount)
        
        if unit == "s": return datetime.timedelta(seconds=amount)
        if unit == "m": return datetime.timedelta(minutes=amount)
        if unit == "h": return datetime.timedelta(hours=amount)
        if unit == "d": return datetime.timedelta(days=amount)
        return None

    async def check_hierarchy(self, ctx, member: discord.Member):
        if ctx.guild.owner == member:
            await ctx.send("❌ Vous ne pouvez pas sanctionner le propriétaire du serveur.")
            return False
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ Vous ne pouvez pas sanctionner ce membre car son rôle est égal ou supérieur au vôtre.")
            return False
        if member == ctx.author:
            await ctx.send("❌ Vous ne pouvez pas vous sanctionner vous-même.")
            return False
        return True

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
        if not await self.check_hierarchy(ctx, member):
            return
        try:
            await member.kick(reason=reason)
            await ctx.send(f"✅ **{member}** a été expulsé. Raison : {reason}")
        except Exception as e:
            await ctx.send(f"❌ Erreur : {e}")

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
        if not await self.check_hierarchy(ctx, member):
            return
        try:
            await member.ban(reason=reason)
            await ctx.send(f"✅ **{member}** a été banni. Raison : {reason}")
        except Exception as e:
            await ctx.send(f"❌ Erreur : {e}")

    @commands.command(name="mute", aliases=["timeout"])
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, duration_or_reason: str = "10m", *, reason: str = None):
        """Mute (Timeout) un membre pour une durée."""
        if not await self.check_hierarchy(ctx, member):
            return
            
        import re
        
        match = re.match(r"^(\d+)([a-zA-Z]+)$", duration_or_reason.lower())
        
        actual_reason = reason or "Aucune raison fournie"
        delta = None
        duration_display = ""
        
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            if unit in ["s", "sec", "secondes"]:
                delta = timedelta(seconds=value)
                duration_display = f"{value} secondes"
            elif unit in ["m", "min", "minutes"]:
                delta = timedelta(minutes=value)
                duration_display = f"{value} minutes"
            elif unit in ["h", "hr", "heures"]:
                delta = timedelta(hours=value)
                duration_display = f"{value} heures"
            elif unit in ["j", "d", "jour", "jours"]:
                delta = timedelta(days=value)
                duration_display = f"{value} jours"
            elif unit in ["w", "semaine", "semaines"]:
                delta = timedelta(weeks=value)
                duration_display = f"{value} semaines"
            elif unit in ["mo", "mois"]:
                delta = timedelta(days=value * 30)
                duration_display = f"{value} mois"
            elif unit in ["a", "y", "an", "ans", "annee", "annees"]:
                delta = timedelta(days=value * 365)
                duration_display = f"{value} ans"
                
        elif duration_or_reason.isdigit():
            value = int(duration_or_reason)
            delta = timedelta(minutes=value)
            duration_display = f"{value} minutes"
            
        if delta is None:
            delta = timedelta(minutes=10)
            duration_display = "10 minutes"
            actual_reason = duration_or_reason + (f" {reason}" if reason else "")

        if delta > timedelta(days=28):
            return await ctx.send("❌ La durée maximale est de 28 jours.")

        try:
            time = discord.utils.utcnow() + delta
            await member.timeout(time, reason=actual_reason)
            await ctx.send(f"✅ **{member}** a été rendu muet pour {duration_display}. Raison : {actual_reason}")
        except Exception as e:
            await ctx.send(f"❌ Erreur : {e}")

    @commands.command(name="unmute")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        """Retire le timeout d'un membre"""
        try:
            await member.timeout(None)
            await ctx.send(f"✅ Le silence de **{member}** a été levé.")
        except Exception as e:
            await ctx.send(f"❌ Erreur : {e}")

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
        if not await self.check_hierarchy(ctx, member):
            return
            
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

        # Sanctions automatiques
        config = get_config(ctx.guild.id) or {}
        warn_enabled = config.get("automod_warn_enabled") == "True"

        if warn_enabled:
            if count == 3:
                try:
                    await member.timeout(datetime.timedelta(hours=2), reason="Automod: 3 avertissements")
                    await ctx.send(f"🤐 {member.mention} a reçu un **Mute automatique de 2h** pour avoir atteint 3 warns.")
                except: pass
            elif count == 5:
                try:
                    await member.kick(reason="Automod: 5 avertissements")
                    await ctx.send(f"👢 {member.mention} a été **expulsé** pour avoir atteint 5 warns.")
                except: pass
            elif count >= 10:
                try:
                    await member.ban(reason="Automod: 10 avertissements")
                    await ctx.send(f"🚫 {member.mention} a été **banni définitivement** pour avoir atteint 10 warns.")
                except: pass
        else:
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

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        """Verrouille un salon (ou le salon actuel par défaut)"""
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"🔒 Le salon {channel.mention} est maintenant verrouillé.")

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        """Déverrouille un salon (ou le salon actuel par défaut)"""
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"🔓 Le salon {channel.mention} est maintenant déverrouillé.")

    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, duration: str):
        """Définit le mode lent. Ex: +slowmode 5s ou +slowmode off"""
        if duration.lower() == "off":
            await ctx.channel.edit(slowmode_delay=0)
            return await ctx.send("✅ Mode lent désactivé.")
        
        td = self.parse_duration(duration)
        if not td:
            return await ctx.send("❌ Format invalide (ex: 5s, 10m).")
        
        seconds = int(td.total_seconds())
        if seconds > 21600:
            return await ctx.send("❌ Le maximum est de 6 heures.")
        
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(f"⏳ Mode lent activé : **{duration}** entre chaque message.")

    @commands.command(name="userinfo")
    async def userinfo(self, ctx, member: discord.Member = None):
        """Affiche les infos d'un utilisateur"""
        member = member or ctx.author
        warns = len(get_warnings(ctx.guild.id, member.id))
        
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_text = " ".join(roles) if roles else "Aucun"
        
        embed = discord.Embed(title=f"Infos sur {member}", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Pseudo", value=member.display_name, inline=True)
        embed.add_field(name="Compte créé", value=f"<t:{int(member.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="A rejoint", value=f"<t:{int(member.joined_at.timestamp())}:D>", inline=True)
        embed.add_field(name="Warnings", value=f"`{warns}`", inline=True)
        embed.add_field(name="Rôles", value=roles_text, inline=False)
        
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
        if len(recent_deleted) <= amount:
            async for msg in ctx.channel.history(limit=amount - len(recent_deleted) + 2):
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
