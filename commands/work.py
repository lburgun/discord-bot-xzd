import random
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from database import user_init, update_bank, get_job_data, update_job, is_employe, is_entreprise_owner, increment_work_effectue, get_entreprise_owner_id, set_work_restants, get_work_restants, get_work_cooldown, update_work_cooldown
from .entreprise import verifier_cycle_et_payer

JOBS = [
    ("Livreur", 50), ("Agent de nettoyage", 70), ("Caissier", 90), ("Serveur", 110),
    ("Assistant", 130), ("Technicien", 150), ("Professeur", 180), ("Développeur", 220),
    ("Ingénieur", 270), ("Consultant", 320), ("Chef de projet", 380), ("Manager", 450),
    ("Directeur", 520), ("Pompier", 600), ("Pilote", 700),
]

STARTING_JOBS_COUNT = 0
WORK_COOLDOWN = 3600  # 1 heure en secondes

def unlock_cost(index):
    return 5 * (index - STARTING_JOBS_COUNT)

class Work(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_user_job_data(self, guild_id, user_id):
        user_init(guild_id, user_id)
        user = get_job_data(guild_id, user_id)
        job_data = user
        return job_data, user

    @commands.command()
    async def work(self, ctx):
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        # Vérifier le cooldown
        last_work = get_work_cooldown(guild_id, user_id)
        if last_work:
            last_work_time = datetime.fromisoformat(last_work)
            time_since_last_work = (datetime.now() - last_work_time).total_seconds()
            if time_since_last_work < WORK_COOLDOWN:
                remaining_time = int(WORK_COOLDOWN - time_since_last_work)
                future_time = int(datetime.now().timestamp() + remaining_time)
                embed = discord.Embed(
                    description=f"⏳ Patiente encore, tu pourras relancer cette commande <t:{future_time}:R>.",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
                return

        job_data, _ = self._get_user_job_data(guild_id, user_id)
        update_job(guild_id, user_id, "work_count", job_data["work_count"] + 1)
        
        # Mettre à jour le timestamp du dernier work
        update_work_cooldown(guild_id, user_id, datetime.now().isoformat())

        check1 = is_employe(guild_id, user_id)
        check2 = is_entreprise_owner(guild_id, user_id)
        if check1 or check2:
            if check1:
                increment_work_effectue(guild_id, user_id)
                owner_id = get_entreprise_owner_id(guild_id, user_id)
                if owner_id:
                    verifier_cycle_et_payer(guild_id, owner_id, self.bot, ctx)
            else:
                set_work_restants(guild_id, user_id, get_work_restants(guild_id, user_id) - 1)
                verifier_cycle_et_payer(guild_id, user_id, self.bot, ctx)

        if (job_data["work_count"] + 1) % 20 == 0 and job_data["work_count"] != 0:
            update_job(guild_id, user_id, "knowledge", job_data["knowledge"] + 1)

        current_job_name = job_data["current_job"]
        job_index = next((i for i, (name, _) in enumerate(JOBS) if name == current_job_name), 0)
        job_name, base_amount = JOBS[job_index]

        amount = random.randint(int(base_amount * 0.9), int(base_amount * 1.1))
        update_bank(guild_id, user_id, amount)

        embed = discord.Embed(
            title=f"💼 Travail : {job_name}",
            description=f"Tu as gagné **{amount} coins**.",
            color=0x000000
        )
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Work(bot))
