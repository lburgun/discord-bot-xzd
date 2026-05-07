import random
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from database import user_init, update_bank, get_job_data, update_job, is_employe, is_entreprise_owner, increment_work_effectue, get_entreprise_owner_id, set_work_restants, get_work_restants, get_work_cooldown, update_work_cooldown, get_inventaire
from .entreprise import verifier_cycle_et_payer
from .catalogue import catalogue_items

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

    def get_clothing_bonus(self, inventory):
        if not inventory:
            return 0.0, None
            
        max_bonus = 0.0
        best_clothing = None
        
        for item_name, data in inventory.items():
            for prop in catalogue_items.get("Mode & Accessoires", []):
                for rarity, variant_name in prop.get("variants", {}).items():
                    if item_name.lower() == variant_name.lower():
                        bonus = 0.0
                        if rarity == "common": bonus = 0.05
                        elif rarity == "uncommon": bonus = 0.10
                        elif rarity == "rare": bonus = 0.15
                        elif rarity == "epic": bonus = 0.20
                        elif rarity == "legendary": bonus = 0.30
                        
                        if bonus > max_bonus:
                            max_bonus = bonus
                            best_clothing = variant_name
                            
        return max_bonus, best_clothing

    @commands.command()
    async def work(self, ctx):
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        # Vérifier si l'utilisateur est dans une entreprise avec une Usine pour réduire le cooldown
        current_cooldown = WORK_COOLDOWN
        from database import get_entreprise_owner_id, is_entreprise_owner, get_entreprise_buildings
        ent_owner_id = None
        if is_entreprise_owner(guild_id, user_id):
            ent_owner_id = str(user_id)
        else:
            ent_owner_id = get_entreprise_owner_id(guild_id, user_id)
            
        if ent_owner_id:
            buildings = get_entreprise_buildings(guild_id, ent_owner_id)
            usine = next((b for b in buildings if b["building_type"] == "usine"), None)
            if usine:
                # -15 min (900 sec) par niveau de l'usine
                reduction = 900 * usine["level"]
                # Max réduction: 45 min (2700 sec), minimum cooldown = 15 min (900 sec)
                if reduction > 2700: reduction = 2700
                current_cooldown -= reduction

        # Vérifier le cooldown
        last_work = get_work_cooldown(guild_id, user_id)
        if last_work:
            last_work_time = datetime.fromisoformat(last_work)
            time_since_last_work = (datetime.now() - last_work_time).total_seconds()
            if time_since_last_work < current_cooldown:
                remaining_time = int(current_cooldown - time_since_last_work)
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
        
        inventory = get_inventaire(str(guild_id), str(user_id))
        bonus_multiplier, clothing_name = self.get_clothing_bonus(inventory)
        
        bonus_amount = int(amount * bonus_multiplier)
        total_amount = amount + bonus_amount
        
        update_bank(guild_id, user_id, total_amount)
        
        desc = f"Tu as gagné **{amount} coins**."
        if bonus_amount > 0:
            desc += f"\n👔 **Bonus de style :** +{bonus_amount} coins (Grâce à : *{clothing_name}*)"
            desc += f"\n💰 **Total perçu :** {total_amount} coins"
            
        # Système de progression connaissance
        work_count = job_data["work_count"] + 1
        knowledge_progress = work_count % 20
        if knowledge_progress == 0:
            desc += "\n\n🎓 **FÉLICITATIONS !** Tu as gagné **1 point de connaissance** ! (Total: `{}` points)".format(job_data["knowledge"] + 1)
        else:
            desc += f"\n\n📚 Progression Connaissance : `{knowledge_progress}/20` work"
            
        # Contract progress
        if ent_owner_id:
            from database import db
            ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(ent_owner_id)})
            if ent and ent.get("active_contract"):
                db.entreprises.update_one(
                    {"guild_id": str(guild_id), "owner_id": str(ent_owner_id)},
                    {"$inc": {"active_contract.progress": 1}}
                )
                desc += "\n📦 *+1 expédition ajoutée au contrat logistique de ton entreprise !*"

        embed = discord.Embed(
            title=f"💼 Travail : {job_name}",
            description=desc,
            color=0x000000
        )
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Work(bot))
