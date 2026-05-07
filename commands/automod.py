import discord
from discord.ext import commands
import datetime
import re
from database import get_config, update_config, add_warning, get_warnings

DEFAULT_BANNED_WORDS = [
    "connard", "salope", "fdp", "enculé", "pute", "nègre", "bougnoule", "chinetoc", "pd", "gouine", "nazi"
]

class AutomodConfigView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @discord.ui.button(label="Anti-Spam", style=discord.ButtonStyle.secondary)
    async def toggle_spam(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id) or {}
        current = config.get("automod_spam") == "True"
        new_val = not current
        update_config(self.guild_id, automod_spam=str(new_val))
        button.style = discord.ButtonStyle.success if new_val else discord.ButtonStyle.danger
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Anti-Invite", style=discord.ButtonStyle.secondary)
    async def toggle_invite(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id) or {}
        current = config.get("automod_invite") == "True"
        new_val = not current
        update_config(self.guild_id, automod_invite=str(new_val))
        button.style = discord.ButtonStyle.success if new_val else discord.ButtonStyle.danger
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Mots Interdits", style=discord.ButtonStyle.secondary)
    async def toggle_badwords(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id) or {}
        current = config.get("automod_badwords") == "True"
        new_val = not current
        update_config(self.guild_id, automod_badwords=str(new_val))
        button.style = discord.ButtonStyle.success if new_val else discord.ButtonStyle.danger
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Warn Auto", style=discord.ButtonStyle.secondary)
    async def toggle_warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id) or {}
        current = config.get("automod_warn_enabled") == "True"
        new_val = not current
        update_config(self.guild_id, automod_warn_enabled=str(new_val))
        button.style = discord.ButtonStyle.success if new_val else discord.ButtonStyle.danger
        await interaction.response.edit_message(view=self)

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_check = {} # {user_id: [timestamps]}

    async def get_automod_settings(self, guild_id):
        config = get_config(guild_id) or {}
        import json
        banned_words_raw = config.get("banned_words")
        try:
            banned_words = json.loads(banned_words_raw) if banned_words_raw else DEFAULT_BANNED_WORDS
        except:
            banned_words = DEFAULT_BANNED_WORDS
            
        return {
            "spam": config.get("automod_spam") == "True",
            "invite": config.get("automod_invite") == "True",
            "badwords": config.get("automod_badwords") == "True",
            "warn_enabled": config.get("automod_warn_enabled") == "True",
            "banned_words": banned_words
        }

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or message.author.guild_permissions.manage_messages:
            return

        settings = await self.get_automod_settings(message.guild.id)
        
        # 1. Anti-Invite
        if settings["invite"]:
            if "discord.gg/" in message.content.lower() or "discord.com/invite/" in message.content.lower():
                await message.delete()
                return await message.channel.send(f"❌ {message.author.mention}, les invitations ne sont pas autorisées ici.", delete_after=5)

        # 2. Mots Interdits
        if settings["badwords"]:
            content = message.content.lower()
            if any(word in content for word in settings["banned_words"]):
                await message.delete()
                
                if settings["warn_enabled"]:
                    # Ajouter le warn en base
                    add_warning(message.guild.id, message.author.id, self.bot.user.id, "Automod: Mot interdit")
                    warns = get_warnings(message.guild.id, message.author.id)
                    count = len(warns)

                    await message.channel.send(f"⚠️ {message.author.mention}, ton message contenait un mot interdit. Tu as reçu un avertissement. (Total: `{count}`)", delete_after=10)

                    # Application des sanctions automatiques
                    if count == 3:
                        try:
                            await message.author.timeout(datetime.timedelta(hours=2), reason="Automod: 3 avertissements")
                            await message.channel.send(f"🤐 {message.author.mention} a été réduit au silence 2h (3 warns).")
                        except: pass
                    elif count == 5:
                        try:
                            await message.author.kick(reason="Automod: 5 avertissements")
                            await message.channel.send(f"👢 {message.author.mention} a été expulsé (5 warns).")
                        except: pass
                    elif count >= 10:
                        try:
                            await message.author.ban(reason="Automod: 10 avertissements")
                            await message.channel.send(f"🚫 {message.author.mention} a été banni (10 warns).")
                        except: pass
                else:
                    await message.channel.send(f"❌ {message.author.mention}, les mots vulgaires sont interdits ici.", delete_after=5)
                return

        # 3. Anti-Spam
        if settings["spam"]:
            user_id = message.author.id
            now = datetime.datetime.now()
            if user_id not in self.spam_check:
                self.spam_check[user_id] = []
            
            self.spam_check[user_id].append(now)
            # Garder seulement les messages des 5 dernières secondes
            self.spam_check[user_id] = [t for t in self.spam_check[user_id] if (now - t).total_seconds() < 5]
            
            if len(self.spam_check[user_id]) > 5: # Plus de 5 messages en 5 secondes
                try:
                    await message.author.timeout(datetime.timedelta(minutes=10), reason="Automod: Spam")
                    await message.channel.purge(limit=10, check=lambda m: m.author.id == user_id)
                    await message.channel.send(f"🤐 {message.author.mention} a été réduit au silence 10 minutes pour spam.", delete_after=10)
                except: pass

    @commands.command(name="config_automod")
    @commands.has_permissions(administrator=True)
    async def config_automod(self, ctx):
        """Configure l'auto-modération (Anti-spam, Anti-invite, Mots interdits)"""
        settings = await self.get_automod_settings(ctx.guild.id)
        
        embed = discord.Embed(
            title="🛡️ Configuration Auto-Modération",
            description="Cliquez sur les boutons pour activer ou désactiver les protections.",
            color=0x2b2d31
        )
        embed.add_field(name="Anti-Spam", value="✅ Activé" if settings["spam"] else "❌ Désactivé", inline=True)
        embed.add_field(name="Anti-Invite", value="✅ Activé" if settings["invite"] else "❌ Désactivé", inline=True)
        embed.add_field(name="Mots Interdits", value="✅ Activé" if settings["badwords"] else "❌ Désactivé", inline=True)
        embed.add_field(name="Warn Auto", value="✅ Activé" if settings["warn_enabled"] else "❌ Désactivé", inline=True)
        
        view = AutomodConfigView(ctx.guild.id)
        # Update button styles
        for button in view.children:
            if button.label == "Anti-Spam": button.style = discord.ButtonStyle.success if settings["spam"] else discord.ButtonStyle.danger
            if button.label == "Anti-Invite": button.style = discord.ButtonStyle.success if settings["invite"] else discord.ButtonStyle.danger
            if button.label == "Mots Interdits": button.style = discord.ButtonStyle.success if settings["badwords"] else discord.ButtonStyle.danger
            if button.label == "Warn Auto": button.style = discord.ButtonStyle.success if settings["warn_enabled"] else discord.ButtonStyle.danger
            
        await ctx.send(embed=embed, view=view)

    @commands.command(name="add_badword")
    @commands.has_permissions(administrator=True)
    async def add_badword(self, ctx, word: str):
        """Ajoute un mot à la liste des mots interdits"""
        config = get_config(ctx.guild.id) or {}
        import json
        banned_words_raw = config.get("banned_words")
        try:
            banned_words = json.loads(banned_words_raw) if banned_words_raw else DEFAULT_BANNED_WORDS.copy()
        except:
            banned_words = DEFAULT_BANNED_WORDS.copy()
            
        if word.lower() not in banned_words:
            banned_words.append(word.lower())
            update_config(ctx.guild.id, banned_words=json.dumps(banned_words))
            await ctx.send(f"✅ Mot `{word}` ajouté à la liste noire.")
        else:
            await ctx.send("ℹ️ Ce mot est déjà dans la liste noire.")

    @commands.command(name="remove_badword")
    @commands.has_permissions(administrator=True)
    async def remove_badword(self, ctx, word: str):
        """Retire un mot de la liste des mots interdits"""
        config = get_config(ctx.guild.id) or {}
        import json
        banned_words_raw = config.get("banned_words")
        try:
            banned_words = json.loads(banned_words_raw) if banned_words_raw else DEFAULT_BANNED_WORDS.copy()
        except:
            banned_words = DEFAULT_BANNED_WORDS.copy()
            
        if word.lower() in banned_words:
            banned_words.remove(word.lower())
            update_config(ctx.guild.id, banned_words=json.dumps(banned_words))
            await ctx.send(f"✅ Mot `{word}` retiré de la liste noire.")
        else:
            await ctx.send("❌ Ce mot n'est pas dans la liste noire.")

    @commands.command(name="badwords_list")
    @commands.has_permissions(manage_messages=True)
    async def badwords_list(self, ctx):
        """Affiche la liste des mots interdits"""
        config = get_config(ctx.guild.id) or {}
        import json
        banned_words_raw = config.get("banned_words")
        try:
            banned_words = json.loads(banned_words_raw) if banned_words_raw else DEFAULT_BANNED_WORDS
        except:
            banned_words = DEFAULT_BANNED_WORDS

        if not banned_words:
            return await ctx.send("Empty list.")

        # Découper en plusieurs messages si la liste est trop longue
        words_str = ", ".join([f"`{w}`" for w in banned_words])
        
        embed = discord.Embed(
            title="🚫 Liste des mots interdits",
            description=words_str,
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Automod(bot))
