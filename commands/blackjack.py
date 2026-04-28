import discord
from discord.ext import commands
import random
from database import user_init, update_wallet, get_wallet_bank

class BlackjackView(discord.ui.View):
    def __init__(self, ctx, bet):
        super().__init__(timeout=40)
        self.ctx = ctx
        self.bet = bet
        self.player_cards = [self.get_card(), self.get_card()]
        self.dealer_cards = [self.get_card(), self.get_card()]
        self.done = False
        self.message = None

    def get_card(self):
        cards = {
            "A": 11, "2": 2, "3": 3, "4": 4, "5": 5,
            "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
            "J": 10, "Q": 10, "K": 10
        }
        suits = ["♠️", "♥️", "♦️", "♣️"]
        card = random.choice(list(cards.items()))
        suit = random.choice(suits)
        return (card[0], card[1], f"{suit} {card[0]}")

    def total(self, cards):
        total = sum(v for _, v, _ in cards)
        aces = sum(1 for k, _, _ in cards if k == "A")
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def format_hand(self, hand):
        return "  ".join([c for _, _, c in hand])

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Ce n'est pas ton jeu !", ephemeral=True)
            return False
        return True

    async def end_game(self, interaction: discord.Interaction, result_text: str, gain: int):
        self.done = True
        update_wallet(self.ctx.guild.id, self.ctx.author.id, gain)

        embed = discord.Embed(title="🎲 Blackjack - Fin de partie", color=0x000000)
        embed.add_field(name="Votre main",
                        value=f"{self.format_hand(self.player_cards)}\n\nTotal : {self.total(self.player_cards)}",
                        inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Main du croupier",
                        value=f"{self.format_hand(self.dealer_cards)}\n\nTotal : {self.total(self.dealer_cards)}",
                        inline=True)
        embed.add_field(name="Résultat", value=f"{result_text}\n💰 {'+' if gain >= 0 else ''}{gain} coins", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        if not self.done:
            self.done = True
            gain = -self.bet // 2
            embed = discord.Embed(title="🎲 Blackjack - Temps écoulé", color=0x000000)
            embed.add_field(name="Votre main",
                            value=f"{self.format_hand(self.player_cards)}\n\nTotal : {self.total(self.player_cards)}",
                            inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            embed.add_field(name="Main du croupier",
                            value=f"{self.dealer_cards[0][2]}  ??\n\nTotal : ?",
                            inline=True)
            embed.add_field(
                name="Résultat",
                value="⏰ Temps écoulé, partie abandonnée automatiquement. Vous perdez la moitié de votre mise.",
                inline=False
            )
            for child in self.children:
                child.disabled = True
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=None)
                except:
                    pass
            update_wallet(self.ctx.guild.id, self.ctx.author.id, gain)
            self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.blurple)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.done:
            await interaction.response.send_message("La partie est terminée.", ephemeral=True)
            return

        self.player_cards.append(self.get_card())
        total = self.total(self.player_cards)

        if total > 21:
            await self.end_game(interaction, "💥 Vous avez dépassé 21 ! Perdu.", -self.bet)
        else:
            embed = discord.Embed(title="🎲 Blackjack",color=0x000000)
            embed.add_field(name="Votre main",
                            value=f"{self.format_hand(self.player_cards)}\n\nTotal : {total}",
                            inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            embed.add_field(name="Main du croupier",
                            value=f"{self.dealer_cards[0][2]}  ??\n\nTotal : ?",
                            inline=True)
            embed.set_footer(text=f"Pari : {self.bet} coins")
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.blurple)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.done:
            await interaction.response.send_message("La partie est terminée.", ephemeral=True)
            return

        while self.total(self.dealer_cards) < 17:
            self.dealer_cards.append(self.get_card())

        player_total = self.total(self.player_cards)
        dealer_total = self.total(self.dealer_cards)

        if dealer_total > 21 or player_total > dealer_total:
            result = "🎉 Vous gagnez !"
            gain = self.bet
        elif player_total == dealer_total:
            result = "🤝 Égalité !"
            gain = 0
        else:
            result = "😔 Vous perdez."
            gain = -self.bet

        await self.end_game(interaction, result, gain)

    @discord.ui.button(label="Abandon", style=discord.ButtonStyle.gray)
    async def surrender(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.done:
            await interaction.response.send_message("La partie est terminée.", ephemeral=True)
            return

        gain = -self.bet // 2
        await self.end_game(interaction, "Vous avez abandonné la partie. Vous perdez la moitié de votre mise.", gain)


class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["bj"])
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def blackjack(self, ctx, amount: str = None):
        user_init(ctx.guild.id, ctx.author.id)
        user = get_wallet_bank(ctx.guild.id,ctx.author.id)
        if amount is None:
            return await ctx.reply("❌ Veuillez saisir une somme à miser.")
        if amount.lower() == "all":
            bet = user["wallet"]
        else:
            if not amount.isdigit():
                return await ctx.reply("❌ Montant invalide.")
            bet = int(amount)

        if bet <= 0 or bet > user["wallet"]:
            return await ctx.reply("❌ Vous n'avez pas assez d'argent.")

        view = BlackjackView(ctx, bet)
        embed = discord.Embed(title="🎲 Blackjack", color=0x000000)
        embed.add_field(name="Votre main",
                        value=f"{view.format_hand(view.player_cards)}\n\nTotal : {view.total(view.player_cards)}",
                        inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Main du croupier",
                        value=f"{view.dealer_cards[0][2]}  ??\n\nTotal : ?",
                        inline=True)
        embed.set_footer(text=f"Pari : {bet} coins")

        message = await ctx.reply(embed=embed, view=view)
        view.message = message


    @blackjack.error
    async def blackjack_error(self, ctx, error):
        from time import time
        if isinstance(error, commands.CommandOnCooldown):
            retry_after = round(error.retry_after, 1)
            future_time = int(time() + retry_after)
            embed = discord.Embed(
                description=(
                    f"⏳ Patiente encore, tu pourrass relancer cette commande <t:{future_time}:R>."
                ),
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Blackjack(bot))
