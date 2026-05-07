import discord
from discord.ext import commands
import random
import string
from PIL import Image, ImageDraw, ImageFont
import io
from database import get_config

class CaptchaModal(discord.ui.Modal, title="Vérification"):
    answer = discord.ui.TextInput(label="Entrez le code de l'image", placeholder="Code ici...", min_length=5, max_length=5)

    def __init__(self, correct_code, role):
        super().__init__()
        self.correct_code = correct_code
        self.role = role

    async def on_submit(self, interaction: discord.Interaction):
        if self.role in interaction.user.roles:
            return await interaction.response.send_message("✅ Tu es déjà vérifié !", ephemeral=True)
            
        if self.answer.value.upper() == self.correct_code:
            try:
                await interaction.user.add_roles(self.role)
                await interaction.response.send_message("✅ Vérification réussie ! Tu as maintenant accès au serveur.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erreur lors de l'attribution du rôle : {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Code incorrect. Réessaye en cliquant à nouveau sur 'Se vérifier'.", ephemeral=True)

class CaptchaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Se vérifier", style=discord.ButtonStyle.green, custom_id="captcha_verify_persistent")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(interaction.guild_id)
        if not config or not config.get("verified_role_id"):
            return await interaction.response.send_message("❌ Le système de captcha n'est pas configuré (rôle manquant).", ephemeral=True)
        
        role = interaction.guild.get_role(int(config["verified_role_id"]))
        if not role:
            return await interaction.response.send_message("❌ Le rôle de vérification est introuvable.", ephemeral=True)

        if role in interaction.user.roles:
            return await interaction.response.send_message("✅ Tu es déjà vérifié !", ephemeral=True)

        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        img = Image.new('RGB', (200, 80), color=(73, 109, 137))
        d = ImageDraw.Draw(img)
        try:
            fnt = ImageFont.truetype("arial.ttf", 40)
        except:
            fnt = ImageFont.load_default()
        
        d.text((40, 20), code, font=fnt, fill=(255, 255, 0))
        for _ in range(100):
            d.point((random.randint(0, 200), random.randint(0, 80)), fill=(255, 255, 255))

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        
        file = discord.File(buf, filename="captcha.png")
        await interaction.response.send_message(
            content="Regarde l'image ci-dessous et clique sur 'Répondre' :", 
            file=file, 
            view=CaptchaResponseView(code, role), 
            ephemeral=True
        )

class CaptchaResponseView(discord.ui.View):
    def __init__(self, code, role):
        super().__init__(timeout=180)
        self.code = code
        self.role = role

    @discord.ui.button(label="Répondre", style=discord.ButtonStyle.primary)
    async def answer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CaptchaModal(self.code, self.role))

class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="send_captcha_panel")
    async def send_captcha_panel(self, ctx):
        """Envoie le panneau de vérification dans ce salon"""
        embed = discord.Embed(
            title="🧱 Firewall de Sécurité", 
            description="Pour accéder au serveur et éviter les bots, merci de cliquer sur le bouton ci-dessous.", 
            color=0x000000
        )
        await ctx.send(embed=embed, view=CaptchaView())

async def setup(bot):
    await bot.add_cog(Security(bot))
