import discord
from discord.ext import commands
from database import update_job, user_init, get_job_data
from .work import JOBS, unlock_cost, STARTING_JOBS_COUNT

class JobsView(discord.ui.View):
    def __init__(self, ctx, bot, job_data):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot = bot
        self.job_data = job_data
        self.user_id = ctx.author.id
        self.guild_id = ctx.guild.id
        
        self.selected_job = None
        
        # Build options for select
        options = []
        unlocked = [j.lower() for j in job_data.get("unlocked_jobs", [])]
        for i, (name, gain) in enumerate(JOBS):
            cost = unlock_cost(i) if i >= STARTING_JOBS_COUNT else 0
            is_unlocked = name.lower() in unlocked
            status = "🟢" if is_unlocked else "🔒"
            desc = f"Gain: {gain} coins | Déjà débloqué" if is_unlocked else f"Gain: {gain} coins | Coût: {cost} pts"
            
            options.append(discord.SelectOption(
                label=name,
                description=desc,
                emoji=status,
                value=str(i)
            ))
            
        self.select = discord.ui.Select(placeholder="Sélectionne un métier pour voir les options...", options=options, row=0)
        self.select.callback = self.select_callback
        self.add_item(self.select)
        
        self.action_btn = discord.ui.Button(label="S'équiper / Acheter", style=discord.ButtonStyle.secondary, disabled=True, row=1)
        self.action_btn.callback = self.action_callback
        self.add_item(self.action_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce n'est pas ton menu !", ephemeral=True)
            return False
        return True

    async def select_callback(self, interaction: discord.Interaction):
        job_index = int(self.select.values[0])
        self.selected_job = job_index
        job_name, _ = JOBS[job_index]
        
        # Refresh job data
        user_init(self.guild_id, self.user_id)
        self.job_data = get_job_data(self.guild_id, self.user_id)
        unlocked = [j.lower() for j in self.job_data.get("unlocked_jobs", [])]
        
        if job_name.lower() in unlocked:
            if self.job_data.get("current_job", "").lower() == job_name.lower():
                self.action_btn.label = "Déjà équipé"
                self.action_btn.style = discord.ButtonStyle.secondary
                self.action_btn.disabled = True
            else:
                self.action_btn.label = "S'équiper"
                self.action_btn.style = discord.ButtonStyle.success
                self.action_btn.disabled = False
        else:
            cost = unlock_cost(job_index)
            self.action_btn.label = f"Acheter ({cost} pts)"
            self.action_btn.style = discord.ButtonStyle.primary
            self.action_btn.disabled = self.job_data.get("knowledge", 0) < cost
            
        await interaction.response.edit_message(view=self)
        
    async def action_callback(self, interaction: discord.Interaction):
        if self.selected_job is None: return
        
        job_index = self.selected_job
        job_name, _ = JOBS[job_index]
        
        # Refresh data
        user_init(self.guild_id, self.user_id)
        self.job_data = get_job_data(self.guild_id, self.user_id)
        unlocked = [j.lower() for j in self.job_data.get("unlocked_jobs", [])]
        knowledge = self.job_data.get("knowledge", 0)
        
        embed = self.build_embed()
        
        if job_name.lower() in unlocked:
            # Equip
            update_job(self.guild_id, self.user_id, "current_job", job_name)
            self.job_data["current_job"] = job_name
            
            embed = self.build_embed()
            embed.description += f"\n\n✅ Tu travailles désormais en tant que **{job_name}**."
            
            self.action_btn.label = "Déjà équipé"
            self.action_btn.style = discord.ButtonStyle.secondary
            self.action_btn.disabled = True
        else:
            # Buy
            cost = unlock_cost(job_index)
            if knowledge >= cost:
                update_job(self.guild_id, self.user_id, "knowledge", knowledge - cost)
                
                unlocked_original = self.job_data.get("unlocked_jobs", [])
                unlocked_original.append(job_name.lower())
                update_job(self.guild_id, self.user_id, "unlocked_jobs", unlocked_original)
                
                self.job_data["knowledge"] = knowledge - cost
                self.job_data["unlocked_jobs"] = unlocked_original
                
                embed = self.build_embed()
                embed.description += f"\n\n🎉 Tu as débloqué le métier **{job_name}** !"
                
                self.action_btn.label = "S'équiper"
                self.action_btn.style = discord.ButtonStyle.success
                self.action_btn.disabled = False
                
                # Update select options visually
                for opt in self.select.options:
                    if opt.value == str(job_index):
                        opt.emoji = "🟢"
                        opt.description = f"Gain: {JOBS[job_index][1]} coins | Déjà débloqué"
            else:
                await interaction.response.send_message("❌ Pas assez de points.", ephemeral=True)
                return
                
        await interaction.response.edit_message(embed=embed, view=self)

    def build_embed(self):
        current = self.job_data.get("current_job", "Inconnu")
        knowledge = self.job_data.get("knowledge", 0)
        return discord.Embed(
            title="🔧 Gestion des métiers",
            description=(
                f"**Métier actuel :** {current.capitalize()}\n"
                f"🎓 Points de connaissance : {knowledge}\n"
                f"\n*Utilise le menu ci-dessous pour changer de métier ou en acheter de nouveaux.*"
            ),
            color=0x000000
        )

class Jobs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_user_job_data(self, guild_id, user_id):
        user_init(guild_id, user_id)
        return get_job_data(guild_id, user_id)

    @commands.command(name="job", aliases=["jobs"])
    async def job(self, ctx):
        job_data = self._get_user_job_data(ctx.guild.id, ctx.author.id)
        view = JobsView(ctx, self.bot, job_data)
        await ctx.reply(embed=view.build_embed(), view=view)

async def setup(bot):
    await bot.add_cog(Jobs(bot))
