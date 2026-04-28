import discord
from discord.ext import commands
import asyncio
import random
from database import user_init, get_wallet_bank, update_wallet
import uuid

class RouletteRusse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}  # Clé : game_id (uuid), valeur : dict infos partie

    @commands.command(aliases=["rouletteRusse"])
    async def rlr(self, ctx, bet: str = None):
        try:
            user_init(ctx.guild.id, ctx.author.id)
            user = get_wallet_bank(ctx.guild.id, ctx.author.id)
            mise_en_cours = user["wallet"]
            if mise_en_cours <= 0:
                return await ctx.reply("❌ Vous n'avez pas d'argent sur vous.")
            if bet is None:
                return await ctx.reply("❌ Veuillez saisir une somme à miser.")
            if bet.lower() == "all":
                bet = mise_en_cours
            else:
                if not bet.isdigit():
                    return await ctx.reply("❌ Montant invalide.")
                bet = int(bet)
            if bet > mise_en_cours:
                return await ctx.reply("❌ Vous n'avez pas assez d'argent sur vous.")

            # Pas de blocage par salon : on permet plusieurs parties par salon

            update_wallet(ctx.guild.id, ctx.author.id, -bet)

            game_id = str(uuid.uuid4())
            players = [ctx.author]

            embed = discord.Embed(
                title="💀 Roulette Russe",
                description=f"{ctx.author.mention} a lancé une partie avec une mise de **{bet} 💰** !\nAppuyez sur **Rejoindre** pour participer.\n\n**Joueurs :**\n{ctx.author.mention}",
                color=0x000000
            )

            view = discord.ui.View(timeout=30)

            async def on_timeout(game_id=game_id):
                game = self.games.get(game_id)
                if not game:
                    return
                view.clear_items()
                await msg.edit(view=view)
                if len(game["players"]) < 2:
                    await msg.edit(content="❌ Pas assez de joueurs pour commencer la partie.", embed=None)
                    # Rembourse la mise aux joueurs
                    for p in game["players"]:
                        update_wallet(ctx.guild.id, p.id, game["bet"])
                    del self.games[game_id]
                    return
                await start_game(ctx, game["players"], game["bet"], msg)
                del self.games[game_id]

            async def join_callback(interaction: discord.Interaction, game_id=game_id):
                game = self.games.get(game_id)
                if not game:
                    return await interaction.response.send_message("❌ Cette partie n'existe plus.", ephemeral=True)
                if interaction.user in game["players"]:
                    return await interaction.response.send_message("❌ Tu es déjà inscrit !", ephemeral=True)
                if len(game["players"]) >= 6:
                    return await interaction.response.send_message("❌ La partie est pleine (6 joueurs max).", ephemeral=True)

                user_init(ctx.guild.id, interaction.user.id)
                userr = get_wallet_bank(ctx.guild.id, interaction.user.id)
                if userr["wallet"] < game["bet"]:
                    return await interaction.response.send_message(f"❌ Il vous faut au moins {game['bet']} 💰 pour rejoindre.", ephemeral=True)

                update_wallet(ctx.guild.id, interaction.user.id, -game["bet"])
                game["players"].append(interaction.user)

                new_embed = embed.copy()
                new_embed.description = f"{ctx.author.mention} a lancé une partie avec une mise de **{game['bet']} 💰** !\nAppuyez sur **Rejoindre** pour participer.\n\n**Joueurs :**\n" + "\n".join(p.mention for p in game["players"])
                await msg.edit(embed=new_embed)
                await interaction.response.send_message("✅ Tu as rejoint la partie !", ephemeral=True)

            join_btn = discord.ui.Button(label="🔫 Rejoindre", style=discord.ButtonStyle.gray)
            join_btn.callback = join_callback
            view.add_item(join_btn)
            view.on_timeout = on_timeout

            msg = await ctx.send(embed=embed, view=view)
            self.games[game_id] = {
                "channel_id": ctx.channel.id,
                "message_id": msg.id,
                "players": players,
                "bet": bet
            }
            try :
                asyncio.create_task(view.wait())
            except: 
                pass

        except :
            pass


async def start_game(ctx, players, bet, message):
    pot = bet * len(players)
    barrel = [False] * 5 + [True]
    random.shuffle(barrel)
    random.shuffle(players)
    dead = []
    current = 0
    previous_player = None

    while len(players) > 1:
        player = players[current]

        if previous_player == player:
            current = (current + 1) % len(players)
            continue

        previous_player = player
        spin_choice = {"value": None}
        selected_target = {"value": None}
        spin_view = discord.ui.View(timeout=20)

        embed = discord.Embed(
            title="🎲 Tour de jeu",
            description=f"C'est à {player.mention} de jouer.\nSouhaitez-vous **tourner le barillet** ?",
            color=0x000000
        )
        embed.set_footer(text="20s pour répondre, sinon tu tires sur toi-même.")
        
        async def spin_callback(interaction: discord.Interaction, choice: bool):
            if interaction.user != player:
                return await interaction.response.send_message("Ce n'est pas ton tour !", ephemeral=True)
            spin_choice["value"] = choice
            spin_view.stop()
            await interaction.response.defer()

        btn_spin = discord.ui.Button(label="🔁 Tourner", style=discord.ButtonStyle.blurple)
        btn_nospin = discord.ui.Button(label="⏭️ Ne pas tourner", style=discord.ButtonStyle.gray)
        btn_spin.callback = lambda i: spin_callback(i, True)
        btn_nospin.callback = lambda i: spin_callback(i, False)
        spin_view.add_item(btn_spin)
        spin_view.add_item(btn_nospin)

        await message.edit(embed=embed, view=spin_view)
        await spin_view.wait()

        if spin_choice["value"] is None:
            spin_choice["value"] = True
            selected_target["value"] = player

        if spin_choice["value"]:
            random.shuffle(barrel)
            embed = discord.Embed(
                title="🔁 Spin du barillet...",
                color=0x000000
            )
            embed.set_image(url="https://cdn.discordapp.com/attachments/1295827543563309177/1389003407758590062/gun.gif?ex=686309ba&is=6861b83a&hm=737f819c437c2a4a58b7743f60353e253d0a8154bae1349e4c7318f0e4c60093&")
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(2.5)

        if selected_target["value"] is None:
            select_view = discord.ui.View(timeout=20)
            options = [
                discord.SelectOption(label="Soi-même" if p == player else p.display_name, value=str(p.id))
                for p in players
            ]
            select = discord.ui.Select(placeholder="Choisis ta cible", options=options)

            async def select_callback(interaction: discord.Interaction):
                if interaction.user != player:
                    return await interaction.response.send_message("Ce n'est pas ton tour !", ephemeral=True)
                selected = int(select.values[0])
                selected_target["value"] = discord.utils.get(players, id=selected)
                select_view.stop()
                await interaction.response.defer()

            select.callback = select_callback
            select_view.add_item(select)

            embed = discord.Embed(
                title="🎯 Choix de la cible",
                description=f"{player.mention}, choisis qui viser.",
                color=0x000000
            )
            await message.edit(embed=embed, view=select_view)
            await select_view.wait()

            if selected_target["value"] is None:
                selected_target["value"] = player

        target = selected_target["value"]
        bullet = barrel.pop()

        display_target = "soi-même" if target == player else target.mention
        fire_embed = discord.Embed(
            title="🔫 Tir...",
            description=f"{player.mention} vise **{display_target}**...",
            color=0x000000
        )
        fire_embed.set_image(url="https://cdn.discordapp.com/attachments/1295827543563309177/1389004916693012551/2z23.gif?ex=68630b22&is=6861b9a2&hm=a4da2166bac5a96db4c634af327a0b9fc9f3d80b639fe0d7c8ffa842a4e10055&")
        await message.edit(embed=fire_embed, view=None)
        await asyncio.sleep(2.5)

        if bullet:
            embed = discord.Embed(
                title="💥 PAN !",
                description=f"💀 {target.mention} a été éliminé !",
                color=0x000000
            )
            players.remove(target)
            dead.append(target)
        else:
            embed = discord.Embed(
                title="😅 Ouf !",
                description=f"{target.mention} a survécu...",
                color=0x000000
            )

        await message.edit(embed=embed, view=None)
        await asyncio.sleep(2)

        if not bullet and target == player:
            continue

        current = (current + 1) % len(players)

    winner = players[0]
    update_wallet(ctx.guild.id, winner.id, pot)
    embed = discord.Embed(
        title="🏆 Victoire !",
        description=f"{winner.mention} remporte **{pot} 💰** !",
        color=0x000000
    )
    await message.edit(embed=embed, view=None)


async def setup(bot):
    await bot.add_cog(RouletteRusse(bot))
