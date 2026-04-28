import random
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from database import update_job, user_init , get_job_data
from .work import JOBS, unlock_cost, STARTING_JOBS_COUNT

class Jobs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_user_job_data(self, guild_id, user_id):
        user_init(guild_id, user_id)
        user = get_job_data(guild_id, user_id)
        job_data = user

        return job_data, user

    @commands.group(name = "job", invoke_without_command=True)  # Commande principale : +job
    async def job(self, ctx):
        user_id = ctx.author.id
        job_data, _ = self._get_user_job_data(ctx.guild.id, user_id)
        knowledge = job_data["knowledge"]
        current = job_data["current_job"]

        embed = discord.Embed(
            title="🔧 Gestion des métiers",
            description=(
                f"**Métier actuel :** {current.capitalize()}\n"
                f"🎓 Points de connaissance : {knowledge}\n"
            ),
            color=0x000000
        )
        await ctx.reply(embed=embed)

    @job.command(name="change")
    async def change(self, ctx, *, job_name: str = None):
        if not job_name:
            await ctx.reply(embed=discord.Embed(
                title="❌ Nom manquant",
                description="Tu dois préciser un nom de métier.",
                color=0x000000
            ))
            return

        user_id = ctx.author.id
        job_data, _ = self._get_user_job_data(ctx.guild.id, user_id)
        unlocked = job_data["unlocked_jobs"]
        job_indices = {name.lower(): i for i, (name, _) in enumerate(JOBS)}
        job_index = job_indices.get(job_name.lower())

        if job_index is None:
            await ctx.reply(embed=discord.Embed(
                title="❌ Métier inconnu",
                description="Ce métier n'existe pas.",
                color=0x000000
            ))
            return

        job_real_name = JOBS[job_index][0]

        if job_real_name.lower() not in unlocked:
            await ctx.reply(embed=discord.Embed(
                title="🔒 Métier non débloqué",
                description="Tu n'as pas débloqué ce métier.",
                color=0x000000
            ))
            return

        update_job(ctx.guild.id, user_id, "current_job", job_real_name)
        await ctx.reply(embed=discord.Embed(
            title="✅ Changement de métier",
            description=f"Tu travailles désormais en tant que **{job_real_name}**.",
            color=0x000000
        ))

    @job.command(name="buy")                                           
    async def buy(self, ctx, *, job_name: str = None):
        if not job_name:
            await ctx.reply(embed=discord.Embed(
                title="❌ Nom manquant",
                description="Tu dois préciser un nom de métier.",
                color=0x000000
            ))
            return

        user_id = ctx.author.id
        job_data, _ = self._get_user_job_data(ctx.guild.id, user_id)
        unlocked = job_data["unlocked_jobs"]
        knowledge = job_data["knowledge"]

        job_indices = {name.lower(): i for i, (name, _) in enumerate(JOBS)}
        job_index = job_indices.get(job_name.lower())

        if job_index is None:
            await ctx.reply(embed=discord.Embed(
                title="❌ Métier inconnu",
                description="Ce métier n'existe pas.",
                color=0x000000
            ))
            return

        job_real_name = JOBS[job_index][0]

        if job_real_name in unlocked:
            await ctx.reply(embed=discord.Embed(
                title="❌ Déjà débloqué",
                description="Tu as déjà débloqué ce métier.",
                color=0x000000
            ))
            return

        cost = unlock_cost(job_index)
        if knowledge < cost:
            await ctx.reply(embed=discord.Embed(
                title="❌ Pas assez de points",
                description=f"Il te faut **{cost}** points de connaissance pour débloquer ce métier.",
                color=0x000000
            ))
            return

        unlocked.append(job_real_name.lower())
        update_job(ctx.guild.id, user_id, "knowledge", max(0, knowledge - cost))
        update_job(ctx.guild.id, user_id, "unlocked_jobs", unlocked)

        await ctx.reply(embed=discord.Embed(
            title="🎉 Nouveau métier débloqué !",
            description=f"Tu as débloqué le métier **{job_real_name}**.",
            color=0x000000
        ))


    @job.command(name="list")
    async def list(self, ctx):
        user_id = ctx.author.id
        job_data, _ = self._get_user_job_data(ctx.guild.id, user_id)
        unlocked_jobs = job_data["unlocked_jobs"]
        embed = discord.Embed(
            title="📋 Liste des métiers",
            description="Voici les métiers disponibles et leur coût en points de connaissance.",
            color=0x000000
        )

        lines = []
        for i, (name, gain) in enumerate(JOBS):
            cost = unlock_cost(i) if i >= STARTING_JOBS_COUNT else 0
            locked = "🟢" if name.lower() in unlocked_jobs else "🔒"
            lines.append(f"{locked} **{name}** — Gain: {gain} coins — Déblocage: {cost} pts")

        embed.add_field(name="Métiers", value="\n".join(lines), inline=False)
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(Jobs(bot))
