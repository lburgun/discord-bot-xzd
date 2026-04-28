import discord
from discord.ext import commands
from database import get_config

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_channels = {} # {channel_id: owner_id}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        config = get_config(member.guild.id)
        if not config or not config.get("voice_trigger_id"):
            return

        trigger_id = int(config["voice_trigger_id"])

        if after.channel and after.channel.id == trigger_id:
            category = after.channel.category
            new_channel = await member.guild.create_voice_channel(
                name=f"🔊 Salon de {member.name}",
                category=category,
                overwrites={
                    member.guild.default_role: discord.PermissionOverwrite(connect=True),
                    member: discord.PermissionOverwrite(manage_channels=True, move_members=True, connect=True)
                }
            )
            await member.move_to(new_channel)
            self.temp_channels[new_channel.id] = member.id

        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    del self.temp_channels[before.channel.id]
                except: pass

    @commands.command(name="vc_lock")
    async def vc_lock(self, ctx):
        """Verrouille ton salon vocal"""
        if not ctx.author.voice or ctx.author.voice.channel.id not in self.temp_channels:
            return await ctx.reply("❌ Tu dois être dans ton salon vocal temporaire !")
        
        channel = ctx.author.voice.channel
        if self.temp_channels[channel.id] != ctx.author.id:
            return await ctx.reply("❌ Tu n'es pas le propriétaire de ce salon !")

        await channel.set_permissions(ctx.guild.default_role, connect=False)
        await ctx.reply("🔒 Salon verrouillé !")

    @commands.command(name="vc_unlock")
    async def vc_unlock(self, ctx):
        """Déverrouille ton salon vocal"""
        if not ctx.author.voice or ctx.author.voice.channel.id not in self.temp_channels:
            return await ctx.reply("❌ Tu dois être dans ton salon vocal temporaire !")
        
        channel = ctx.author.voice.channel
        if self.temp_channels[channel.id] != ctx.author.id:
            return await ctx.reply("❌ Tu n'es pas le propriétaire de ce salon !")

        await channel.set_permissions(ctx.guild.default_role, connect=True)
        await ctx.reply("🔓 Salon ouvert à tous !")

async def setup(bot):
    await bot.add_cog(Voice(bot))
