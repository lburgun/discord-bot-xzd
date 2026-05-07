import random
import discord
from discord.ext import commands
import asyncio
from typing import Union
from datetime import datetime
from database import (
    user_init, get_wallet_bank, update_wallet, update_bank, get_inventaire, 
    execute_query, fetch_one, fetch_all, update_inventaire, 
    get_entreprise_by_name, get_entreprise_buildings, update_tresorerie_entreprise, 
    get_user_ddos
)

class Rob(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ensure_tables()

    def ensure_tables(self):
        execute_query("CREATE TABLE IF NOT EXISTS thief_stats (guild_id TEXT, user_id TEXT, successful_robs INTEGER DEFAULT 0, failed_robs INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id))")
        execute_query("CREATE TABLE IF NOT EXISTS bounties (bounty_id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, target_id TEXT, issuer_id TEXT, amount INTEGER)")

    def get_thief_stats(self, guild_id: str, user_id: str):
        stats = fetch_one("SELECT successful_robs, failed_robs FROM thief_stats WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
        if not stats:
            execute_query("INSERT INTO thief_stats (guild_id, user_id, successful_robs, failed_robs) VALUES (?, ?, 0, 0)", (str(guild_id), str(user_id)))
            return {"success": 0, "fail": 0}
        return {"success": stats[0], "fail": stats[1]}

    def add_thief_success(self, guild_id: str, user_id: str):
        stats = self.get_thief_stats(guild_id, user_id)
        execute_query("UPDATE thief_stats SET successful_robs = successful_robs + 1 WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))

    def add_thief_fail(self, guild_id: str, user_id: str):
        stats = self.get_thief_stats(guild_id, user_id)
        execute_query("UPDATE thief_stats SET failed_robs = failed_robs + 1 WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))

    def get_thief_level(self, success_count: int):
        if success_count >= 50: return 5
        if success_count >= 30: return 4
        if success_count >= 15: return 3
        if success_count >= 5:  return 2
        return 1

    def get_best_vehicle_bonus(self, inventory):
        from .catalogue import catalogue_items
        if not inventory: return 0.0, None
        
        max_bonus = 0.0
        best_vehicle = None
        
        for item_name, data in inventory.items():
            for prop in catalogue_items.get("Véhicules", []):
                for rarity, variant_name in prop.get("variants", {}).items():
                    if item_name.lower() == variant_name.lower():
                        bonus = 0.0
                        if prop["name"] == "Vélo":
                            if rarity == "common": bonus = 0.05
                            elif rarity == "uncommon": bonus = 0.10
                            elif rarity == "rare": bonus = 0.15
                        elif prop["name"] == "Moto":
                            if rarity == "common": bonus = 0.15
                            elif rarity == "uncommon": bonus = 0.20
                            elif rarity == "rare": bonus = 0.25
                            elif rarity == "epic": bonus = 0.30
                        elif prop["name"] == "Voiture":
                            if rarity == "common": bonus = 0.15
                            elif rarity == "uncommon": bonus = 0.25
                            elif rarity == "rare": bonus = 0.35
                            elif rarity == "epic": bonus = 0.45
                            elif rarity == "legendary": bonus = 0.55
                        elif prop["name"] == "Hélicoptère":
                            if rarity == "rare": bonus = 0.40
                            elif rarity == "epic": bonus = 0.50
                            elif rarity == "legendary": bonus = 0.60
                            
                        if bonus > max_bonus:
                            max_bonus = bonus
                            best_vehicle = variant_name
        return max_bonus, best_vehicle

    def get_best_weapon_defense(self, inventory):
        from .catalogue import catalogue_items
        if not inventory: return 0.0, None
        
        max_defense = 0.0
        best_weapon = None
        
        for item_name, data in inventory.items():
            for prop in catalogue_items.get("Sécurité & Armes", []):
                if prop["name"] == "Arme à feu":
                    for rarity, variant_name in prop.get("variants", {}).items():
                        if item_name.lower() == variant_name.lower():
                            defense = 0.0
                            if rarity == "rare": defense = 0.30
                            elif rarity == "epic": defense = 0.50
                            elif rarity == "legendary": defense = 0.75
                            
                            if defense > max_defense:
                                max_defense = defense
                                best_weapon = variant_name
        return max_defense, best_weapon

    def get_best_safe_defense(self, inventory):
        from .catalogue import catalogue_items
        if not inventory: return 0.0, None
        
        max_defense = 0.0
        best_safe = None
        
        for item_name, data in inventory.items():
            for prop in catalogue_items.get("Sécurité & Armes", []):
                if prop["name"] == "Coffre-fort":
                    for rarity, variant_name in prop.get("variants", {}).items():
                        if item_name.lower() == variant_name.lower():
                            defense = 0.0
                            if rarity == "common": defense = 0.20
                            elif rarity == "uncommon": defense = 0.35
                            elif rarity == "rare": defense = 0.50
                            elif rarity == "epic": defense = 0.70
                            elif rarity == "legendary": defense = 0.85
                            
                            if defense > max_defense:
                                max_defense = defense
                                best_safe = variant_name
        return max_defense, best_safe

    def get_best_alarm_defense(self, inventory):
        from .catalogue import catalogue_items
        if not inventory: return 0.0, None
        
        max_defense = 0.0
        best_alarm = None
        
        for item_name, data in inventory.items():
            for prop in catalogue_items.get("Sécurité & Armes", []):
                if prop["name"] == "Alarme":
                    for rarity, variant_name in prop.get("variants", {}).items():
                        if item_name.lower() == variant_name.lower():
                            defense = 0.0
                            if rarity == "common": defense = 0.10
                            elif rarity == "uncommon": defense = 0.15
                            elif rarity == "rare": defense = 0.25
                            elif rarity == "epic": defense = 0.40
                            
                            if defense > max_defense:
                                max_defense = defense
                                best_alarm = variant_name
        return max_defense, best_alarm

    def has_item_type(self, inventory, item_base_name_or_variants):
        if not inventory: return False
        for k in inventory.keys():
            if isinstance(item_base_name_or_variants, list):
                if any(v.lower() in k.lower() for v in item_base_name_or_variants):
                    return True
            else:
                if item_base_name_or_variants.lower() in k.lower():
                    return True
        return False

    @commands.command(name="rob")
    @commands.cooldown(1, 1800, commands.BucketType.user)  
    async def rob(self, ctx, member: commands.MemberConverter):
        attacker = ctx.author.id
        victim = member.id
        guild_id = str(ctx.guild.id)

        if attacker == victim:
            return await ctx.reply(embed=discord.Embed(description="❌ Tu ne peux pas t'auto voler.", color=discord.Color.red()))

        user_init(guild_id, attacker)
        user_init(guild_id, victim)
        
        data1 = get_wallet_bank(guild_id, attacker)
        data2 = get_wallet_bank(guild_id, victim)
        
        attacker_wallet = data1["wallet"]
        victim_wallet = data2["wallet"]

        if attacker_wallet < 500:
            return await ctx.reply(embed=discord.Embed(description="❌ Tu as besoin d'au moins 500 coins sur ton wallet pour tenter un vol.", color=discord.Color.red()))

        if victim_wallet < 500:
            return await ctx.reply(embed=discord.Embed(description="❌ La cible n'a pas assez d'argent (500 coins minimum dans son wallet).", color=discord.Color.red()))

        stats = self.get_thief_stats(guild_id, attacker)
        level = self.get_thief_level(stats["success"])
        
        victim_inv = get_inventaire(guild_id, victim)
        attacker_inv = get_inventaire(guild_id, attacker)
        
        # --- DDOS CHECK ---
        from database import get_user_ddos
        import datetime
        
        attacker_ddos = get_user_ddos(guild_id, attacker)
        if attacker_ddos:
            try:
                expiry = datetime.datetime.fromisoformat(attacker_ddos)
                if datetime.datetime.now() < expiry:
                    return await ctx.reply(embed=discord.Embed(description="❌ Ton système est piraté (DDoS). Tu ne peux rien faire pour l'instant.", color=discord.Color.red()))
            except: pass

        victim_ddos = get_user_ddos(guild_id, victim)
        victim_is_ddosed = False
        if victim_ddos:
            try:
                expiry = datetime.datetime.fromisoformat(victim_ddos)
                if datetime.datetime.now() < expiry:
                    victim_is_ddosed = True
            except: pass

        # --- DEFENSES ---
        weapon_defense_chance, weapon_name = self.get_best_weapon_defense(victim_inv)
        safe_defense_percent, safe_name = self.get_best_safe_defense(victim_inv)
        vehicle_escape_bonus, vehicle_name = self.get_best_vehicle_bonus(attacker_inv)
        
        # Si la victime est DDoS, ses défenses sont désactivées !
        if victim_is_ddosed:
            weapon_defense_chance = 0
            safe_defense_percent = 0
        
        # Confrontation si arme à feu
        if weapon_defense_chance > 0 and random.random() < weapon_defense_chance:
            fine = random.randint(1000, 2500)
            
            # Réduction de l'amende avec le véhicule
            if vehicle_escape_bonus > 0:
                fine = int(fine * (1.0 - vehicle_escape_bonus))
                
            if attacker_wallet < fine: fine = attacker_wallet
            update_wallet(guild_id, attacker, -fine)
            self.add_thief_fail(guild_id, attacker)
            
            desc = f"{member.mention} a sorti son/sa **{weapon_name}** et t'a mis en fuite !\nTu perds **{fine} coins** dans ta fuite."
            if vehicle_escape_bonus > 0:
                desc += f"\n*(Tu as fui plus vite grâce à ton {vehicle_name}, réduisant tes pertes !)*"
                
            embed = discord.Embed(
                title="🔫 CONFRONTATION ARMÉE !",
                description=desc,
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        # Calcul des chances
        base_chance = 0.50
        if level >= 2: base_chance += 0.05
        if level >= 3: base_chance += 0.05
        if level >= 5: base_chance += 0.10

        success = random.random() < base_chance
        
        # Identité cachée (Niveau 5)
        hidden_identity = (level >= 5 and random.random() < 0.5)
        thief_name = "Un fantôme 👻" if hidden_identity else ctx.author.display_name

        if success:
            self.add_thief_success(guild_id, attacker)
            
            # Calcul du butin
            max_steal = victim_wallet
            if safe_defense_percent > 0:
                # Le coffre protège un pourcentage de l'argent
                max_steal = int(victim_wallet * (1.0 - safe_defense_percent))
                
            amount = random.randint(max_steal // 2, max_steal)
            
            update_wallet(guild_id, attacker, amount)
            update_wallet(guild_id, victim, -amount)
            
            desc = f"🕵️ {thief_name} a volé **{amount} coins** à {member.display_name} !"
            if safe_defense_percent > 0:
                desc += f"\n*(Le **{safe_name}** de la victime a protégé {int(safe_defense_percent*100)}% de son argent !)*"
                
            embed = discord.Embed(description=desc, color=0x00FF00)
            await ctx.reply(embed=embed)
            
            # Notification à la victime si non caché
            if not hidden_identity:
                try:
                    await member.send(f"🚨 Tu as été volé de **{amount} coins** par **{ctx.author.display_name}** sur le serveur **{ctx.guild.name}** !")
                except: pass

        else:
            self.add_thief_fail(guild_id, attacker)
            fine = random.randint(200, 500)
            if level >= 3: fine = random.randint(500, 1000) # Plus de risques à haut niveau
            
            # Réduction de l'amende avec le véhicule
            if vehicle_escape_bonus > 0:
                fine = int(fine * (1.0 - vehicle_escape_bonus))
            
            if attacker_wallet < fine: fine = attacker_wallet
            update_wallet(guild_id, attacker, -fine) 
            
            desc = f"🚨 {thief_name} a échoué son vol sur {member.display_name} et a perdu **{fine} coins** dans sa fuite !"
            if vehicle_escape_bonus > 0:
                desc += f"\n*(Ton **{vehicle_name}** t'a permis de limiter la casse)*"
                
            embed = discord.Embed(
                description=desc,
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

    @commands.command(name="scout")
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def scout(self, ctx, member: commands.MemberConverter):
        """Espionner un joueur avant de le voler (Requis: Voleur Niv 3)"""
        guild_id = str(ctx.guild.id)
        stats = self.get_thief_stats(guild_id, ctx.author.id)
        level = self.get_thief_level(stats["success"])
        
        if level < 3:
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply(embed=discord.Embed(description=f"❌ Il faut être **Voleur Niveau 3** (15 vols réussis). Tu es Niveau {level}.", color=discord.Color.red()))
            
        user_init(guild_id, member.id)
        data = get_wallet_bank(guild_id, member.id)
        inv = get_inventaire(guild_id, member.id)
        
        _, weapon_name = self.get_best_weapon_defense(inv)
        _, safe_name = self.get_best_safe_defense(inv)
        
        has_weapon = f"Oui 🔫 ({weapon_name})" if weapon_name else "Non"
        has_safe = f"Oui 🗄️ ({safe_name})" if safe_name else "Non"
        
        embed = discord.Embed(title=f"🕵️ Rapport d'espionnage : {member.display_name}", color=0x2f3136)
        embed.add_field(name="Argent en poche (Wallet)", value=f"{data['wallet']:,} 💰", inline=False)
        embed.add_field(name="Arme à feu", value=has_weapon, inline=True)
        embed.add_field(name="Coffre-fort", value=has_safe, inline=True)
        
        await ctx.author.send(embed=embed)
        await ctx.message.add_reaction("✅")

    @commands.command(name="heist")
    @commands.cooldown(1, 7200, commands.BucketType.user)
    async def heist(self, ctx, *, target: Union[discord.Member, str]):
        """Braquer le compte en banque d'un joueur ou d'une entreprise (Requis: Voleur Niv 4)"""
        guild_id = str(ctx.guild.id)
        attacker_id = str(ctx.author.id)
        
        # Initialisation de l'attaquant
        user_init(guild_id, attacker_id)
        attacker_balances = get_wallet_bank(guild_id, attacker_id)
        
        if attacker_balances["wallet"] < 5000:
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply("❌ Tu as besoin de 5000 coins (pour le matériel) pour lancer un braquage.")

        stats = self.get_thief_stats(guild_id, attacker_id)
        level = self.get_thief_level(stats["success"])
        
        if level < 4:
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply(embed=discord.Embed(description=f"❌ Il faut être **Braqueur Niveau 4** (30 vols réussis). Tu es Niveau {level}.", color=discord.Color.red()))

        is_company = False
        target_name = ""
        target_id = "" # Owner ID if company, Victim ID if player
        target_tresorerie = 0
        target_inv = {}

        if isinstance(target, discord.Member):
            victim = target
            if attacker_id == str(victim.id):
                ctx.command.reset_cooldown(ctx)
                return await ctx.reply("❌ Tu ne peux pas braquer ta propre banque.")
            
            user_init(guild_id, str(victim.id))
            victim_balances = get_wallet_bank(guild_id, str(victim.id))
            
            if victim_balances["bank"] < 10000:
                ctx.command.reset_cooldown(ctx)
                return await ctx.reply("❌ La banque de la cible est trop vide (moins de 10k). Ça n'en vaut pas la peine.")
            
            target_name = victim.mention
            target_id = str(victim.id)
            target_tresorerie = victim_balances["bank"]
            target_inv = get_inventaire(guild_id, target_id)
        else:
            # Recherche par nom d'entreprise
            entreprise = get_entreprise_by_name(guild_id, target)
            if not entreprise:
                ctx.command.reset_cooldown(ctx)
                return await ctx.reply(f"❌ Aucune entreprise ou joueur trouvé avec le nom '**{target}**'.")
            
            if entreprise["owner_id"] == attacker_id:
                ctx.command.reset_cooldown(ctx)
                return await ctx.reply("❌ Tu ne peux pas braquer ta propre entreprise.")
            
            if entreprise["tresorerie"] < 10000:
                ctx.command.reset_cooldown(ctx)
                return await ctx.reply(f"❌ La trésorerie de **{entreprise['nom']}** est trop vide (moins de 10k). Ça n'en vaut pas la peine.")
            
            is_company = True
            target_name = f"l'entreprise **{entreprise['nom']}**"
            target_id = entreprise["owner_id"]
            target_tresorerie = entreprise["tresorerie"]
            target_inv = get_inventaire(guild_id, target_id)

        # Calcul des chances de succès
        success_chance = 0.35 # 35% de chance de base
        if level == 5: success_chance = 0.45
        
        attacker_inv = get_inventaire(guild_id, attacker_id)
        
        # Défenses
        alarm_defense, alarm_name = self.get_best_alarm_defense(target_inv)
        building_defense = 0
        
        if is_company:
            buildings = get_entreprise_buildings(guild_id, target_id)
            securite = next((b for b in buildings if b["building_type"] == "securite"), None)
            if securite:
                building_defense = securite["level"] * 0.15 # 15% par niveau
        
        total_defense = alarm_defense + building_defense
        
        # Si la victime (owner si entreprise) est DDoS, les défenses tech sont désactivées
        ddos_expiry = get_user_ddos(guild_id, target_id)
        if ddos_expiry and datetime.fromisoformat(ddos_expiry) > datetime.now():
            total_defense = 0
            
        success_chance -= total_defense
        if success_chance < 0.05: success_chance = 0.05 # Minimum 5% de chance
            
        success = random.random() < success_chance
        
        if success:
            self.add_thief_success(guild_id, attacker_id)
            # Vole 10% à 30%
            percent = random.uniform(0.1, 0.3)
            amount = int(target_tresorerie * percent)
            
            update_wallet(guild_id, attacker_id, amount)
            
            if is_company:
                update_tresorerie_entreprise(guild_id, target_id, target_tresorerie - amount)
                embed = discord.Embed(title="🏢 BRAQUAGE D'ENTREPRISE RÉUSSI", description=f"Tu as infiltré le coffre de **{target}** et dérobé **{amount:,} coins** !", color=0x00FF00)
            else:
                update_bank(guild_id, target_id, -amount)
                embed = discord.Embed(title="🏦 BRAQUAGE RÉUSSI", description=f"Tu as infiltré la banque de {target.mention} et dérobé **{amount:,} coins** !", color=0x00FF00)
            
            await ctx.reply(embed=embed)
        else:
            self.add_thief_fail(guild_id, attacker_id)
            # Échec : très grosse amende
            fine = random.randint(3000, 8000)
            
            vehicle_escape_bonus, vehicle_name = self.get_best_vehicle_bonus(attacker_inv)
            if vehicle_escape_bonus > 0:
                fine = int(fine * (1.0 - vehicle_escape_bonus))
                
            if attacker_balances["wallet"] < fine: fine = attacker_balances["wallet"]
            update_wallet(guild_id, attacker_id, -fine)
            
            desc = f"La sécurité t'a repéré chez {target_name} ! Tu fuis en abandonnant **{fine:,} coins**."
            if alarm_defense > 0:
                desc += f"\n*(L'alarme (**{alarm_name}**) de la cible s'est déclenchée !)*"
            if building_defense > 0:
                desc += f"\n*(Le **Système de Sécurité** de l'entreprise t'a rendu la tâche difficile !)*"
            if vehicle_escape_bonus > 0:
                desc += f"\n*(Ton **{vehicle_name}** t'a sauvé d'une plus grosse amende)*"
                
            embed = discord.Embed(title="🚨 BRAQUAGE ÉCHOUÉ", description=desc, color=discord.Color.red())
            await ctx.reply(embed=embed)


    @commands.group(name="police", aliases=["bounty"], invoke_without_command=True)
    async def police(self, ctx):
        embed = discord.Embed(title="🚓 Commissariat de Police", color=0x2f3136)
        embed.add_field(name="`+bounty add @joueur montant`", value="Placer une prime sur la tête d'un joueur.", inline=False)
        embed.add_field(name="`+bounty list`", value="Voir les criminels recherchés.", inline=False)
        embed.add_field(name="`+arrest @joueur`", value="Tenter d'arrêter un joueur recherché.", inline=False)
        await ctx.reply(embed=embed)

    @police.command(name="add")
    async def bounty_add(self, ctx, member: commands.MemberConverter, amount: int):
        if amount < 1000:
            return await ctx.reply("❌ La prime doit être d'au moins 1000 coins.")
        if member.id == ctx.author.id:
            return await ctx.reply("❌ Tu ne peux pas mettre une prime sur toi-même.")
            
        wallet = get_wallet_bank(str(ctx.guild.id), ctx.author.id)["wallet"]
        if wallet < amount:
            return await ctx.reply("❌ Tu n'as pas cet argent en poche.")
            
        update_wallet(str(ctx.guild.id), ctx.author.id, -amount)
        
        # Ajouter ou mettre à jour la prime
        existing = fetch_one("SELECT amount FROM bounties WHERE guild_id = ? AND target_id = ?", (str(ctx.guild.id), str(member.id)))
        if existing:
            execute_query("UPDATE bounties SET amount = amount + ? WHERE guild_id = ? AND target_id = ?", (amount, str(ctx.guild.id), str(member.id)))
        else:
            execute_query("INSERT INTO bounties (guild_id, target_id, issuer_id, amount) VALUES (?, ?, ?, ?)", (str(ctx.guild.id), str(member.id), str(ctx.author.id), amount))
            
        await ctx.reply(f"✅ Prime de **{amount:,} coins** placée sur la tête de {member.mention} !")

    @police.command(name="list")
    async def bounty_list(self, ctx):
        bounties = fetch_all("SELECT target_id, amount FROM bounties WHERE guild_id = ? ORDER BY amount DESC LIMIT 10", (str(ctx.guild.id),))
        if not bounties:
            return await ctx.reply("🚔 Aucun criminel n'est actuellement recherché.")
            
        embed = discord.Embed(title="📜 Tableau des Primes (Wanted)", color=0x2f3136)
        for target_id, amount in bounties:
            target = ctx.guild.get_member(int(target_id))
            name = target.display_name if target else f"ID: {target_id}"
            embed.add_field(name=f"👤 {name}", value=f"Prime: **{amount:,} 💰**", inline=False)
            
        await ctx.reply(embed=embed)

    @commands.command(name="arrest")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def arrest(self, ctx, member: commands.MemberConverter):
        """Tenter d'arrêter un joueur recherché"""
        guild_id = str(ctx.guild.id)
        if member.id == ctx.author.id:
            return await ctx.reply("❌ Tu ne peux pas t'arrêter toi-même.")
            
        bounty = fetch_one("SELECT amount FROM bounties WHERE guild_id = ? AND target_id = ?", (guild_id, str(member.id)))
        if not bounty:
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply("❌ Ce joueur n'est pas recherché.")
            
        target_inv = get_inventaire(guild_id, member.id)
        has_weapon = self.has_item_type(target_inv, ["Arme à feu", "Pistolet", "Fusil", "Arme lourde"])
        
        # L'arrestation est difficile si la cible est armée
        chance = 0.40 if has_weapon else 0.70
        
        if random.random() < chance:
            reward = bounty[0]
            execute_query("DELETE FROM bounties WHERE guild_id = ? AND target_id = ?", (guild_id, str(member.id)))
            
            update_wallet(guild_id, ctx.author.id, reward)
            # La cible perd de l'argent de sa banque comme "frais de justice"
            update_bank(guild_id, member.id, -int(reward * 0.5))
            
            embed = discord.Embed(title="🚔 ARRESTATION RÉUSSIE", description=f"Tu as arrêté {member.mention} et empoché la prime de **{reward:,} coins** !", color=0x00FF00)
            await ctx.reply(embed=embed)
        else:
            embed = discord.Embed(title="🚨 ARRESTATION ÉCHOUÉE", description=f"{member.mention} t'a échappé ! Reviens mieux préparé.", color=discord.Color.red())
            await ctx.reply(embed=embed)

    @scout.error
    @heist.error
    @arrest.error
    @rob.error
    async def rob_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = int(error.retry_after)
            minutes, sec = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)

            time_str = ""
            if hours > 0: time_str += f"{hours}h "
            if minutes > 0: time_str += f"{minutes}m "
            time_str += f"{sec}s"

            embed = discord.Embed(
                description=f"⏳ Patiente encore {time_str.strip()} avant de pouvoir faire cette action.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
        else:
            raise error

async def setup(bot):
    await bot.add_cog(Rob(bot))