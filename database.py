import os
from typing import Optional, Dict, List, Union, Tuple
from datetime import datetime
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://leointernet90_db_user:UyBjcI1iTATaTjbB@cluster0.b0zapmd.mongodb.net/?appName=Cluster0")
DB_NAME = os.getenv("MONGO_DB_NAME", "discord_bot")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# ---- CONSTANTES ----
EMPLOYEE_ROLES = {
    "stagiaire": {
        "nom": "Stagiaire",
        "description": "Accès limité aux informations de base",
        "permissions": ["voir_status"],
        "salaire_min": 1,
        "salaire_max": 1000
    },
    "employe": {
        "nom": "Employé",
        "description": "Accès aux informations de base et statistiques",
        "permissions": ["voir_status", "voir_batiments"],
        "salaire_min": 1,
        "salaire_max": 2500
    },
    "manager": {
        "nom": "Manager",
        "description": "Accès étendu et gestion des employés juniors",
        "permissions": ["voir_status", "voir_batiments", "voir_employes", "gerer_stagiaires"],
        "salaire_min": 1,
        "salaire_max": 5000
    },
    "directeur": {
        "nom": "Directeur",
        "description": "Accès complet sauf retrait de fonds",
        "permissions": ["voir_status", "voir_batiments", "voir_employes", "gerer_employes", "gerer_batiments"],
        "salaire_min": 1,
        "salaire_max": 10000
    }
}

BUILDING_TYPES = {
    "usine": {
        "nom": "Usine",
        "description": "Augmente la production de revenus (+50% par niveau)",
        "base_revenue": 800,
        "revenue_multiplier": 3.0,
        "base_maintenance": 150,
        "maintenance_multiplier": 1.5,
        "base_work": 4,
        "work_multiplier": 1.5,
        "base_cost": 2500,
        "cost_multiplier": 2.5,
        "max_quantity": 1,
        "storage_bonus": 2000
    },
    "bureau": {
        "nom": "Bureau",
        "description": "Réduit les coûts de maintenance (-20% par niveau)",
        "base_revenue": 500,
        "revenue_multiplier": 2.5,
        "base_maintenance": 100,
        "maintenance_multiplier": 1.3,
        "base_work": 3,
        "work_multiplier": 1.3,
        "base_cost": 1500,
        "cost_multiplier": 2.0,
        "max_quantity": 1,
        "storage_bonus": 1500
    },
    "atelier": {
        "nom": "Atelier",
        "description": "Réduit le nombre de works requis (-25% par niveau)",
        "base_revenue": 600,
        "revenue_multiplier": 2.7,
        "base_maintenance": 120,
        "maintenance_multiplier": 1.4,
        "base_work": 3,
        "work_multiplier": 1.4,
        "base_cost": 2000,
        "cost_multiplier": 2.2,
        "max_quantity": 1,
        "storage_bonus": 1800
    },
    "entrepot": {
        "nom": "Entrepôt",
        "description": "Augmente la capacité de stockage (+3000 par niveau)",
        "base_revenue": 700,
        "revenue_multiplier": 2.8,
        "base_maintenance": 130,
        "maintenance_multiplier": 1.6,
        "base_work": 4,
        "work_multiplier": 1.6,
        "base_cost": 2200,
        "cost_multiplier": 2.3,
        "max_quantity": 1,
        "storage_bonus": 5000
    },
    "laboratoire": {
        "nom": "Laboratoire R&D",
        "description": "Bonus aux revenus et réduction des coûts (+30% rev, -10% coûts par niveau)",
        "base_revenue": 1000,
        "revenue_multiplier": 3.3,
        "base_maintenance": 200,
        "maintenance_multiplier": 1.7,
        "base_work": 5,
        "work_multiplier": 1.7,
        "base_cost": 3500,
        "cost_multiplier": 3.0,
        "max_quantity": 1,
        "storage_bonus": 3000
    },
    "mine": {
        "nom": "Mine",
        "description": "Production de ressources brutes (+60% revenus par niveau)",
        "base_revenue": 900,
        "revenue_multiplier": 3.1,
        "base_maintenance": 175,
        "maintenance_multiplier": 1.8,
        "base_work": 5,
        "work_multiplier": 1.8,
        "base_cost": 3000,
        "cost_multiplier": 2.8,
        "max_quantity": 1,
        "storage_bonus": 2500
    },
    "securite": {
        "nom": "Système de Sécurité",
        "description": "Défense contre les braquages (+15% de protection par niveau)",
        "base_revenue": 0,
        "revenue_multiplier": 0,
        "base_maintenance": 250,
        "maintenance_multiplier": 1.5,
        "base_work": 2,
        "work_multiplier": 1.2,
        "base_cost": 5000,
        "cost_multiplier": 2.5,
        "max_quantity": 1,
        "storage_bonus": 0
    }
}

def init_db():
    """Initialise la base de données MongoDB (crée des index si nécessaire)"""
    # Index pour les utilisateurs
    db.users.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
    # Index pour l'inventaire
    db.inventaire.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
    # Index pour les jobs
    db.jobs.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
    # Index pour les entreprises
    db.entreprises.create_index([("guild_id", 1), ("owner_id", 1)], unique=True)
    db.entreprises.create_index([("guild_id", 1), ("nom", 1)])
    # Index pour les employés
    db.entreprise_employes.create_index([("guild_id", 1), ("entreprise_owner_id", 1), ("employe_id", 1)], unique=True)
    db.entreprise_employes.create_index([("guild_id", 1), ("employe_id", 1)])
    # Index pour les bâtiments
    db.entreprise_buildings.create_index([("guild_id", 1), ("entreprise_owner_id", 1), ("building_id", 1)], unique=True)
    # Index pour le marketplace
    db.marketplace_listings.create_index([("guild_id", 1), ("listing_id", 1)], unique=True)
    db.marketplace_listings.create_index([("status", 1), ("expires_at", 1)])
    # Index pour les warnings
    db.warnings.create_index([("guild_id", 1), ("user_id", 1)])
    # Index pour les tickets
    db.tickets.create_index([("channel_id", 1)], unique=True)
    # Index pour les configs
    db.guild_config.create_index([("guild_id", 1)], unique=True)
    # Index pour les permissions
    db.command_permissions.create_index([("guild_id", 1), ("command_name", 1), ("role_id", 1)], unique=True)

# ---- BRIDGE SQL-TO-MONGO POUR COMPATIBILITÉ ----
import re

def parse_sql_where(where_clause: str, params: tuple) -> dict:
    if not where_clause: return {}
    # Split by AND but handle potential case variations and spaces
    parts = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
    query = {}
    param_idx = 0
    for part in parts:
        part = part.strip()
        if not part: continue
        # Matches "col = ?", "col=?", "col  !=  ?", etc.
        match = re.match(r'(\w+)\s*(=|!=|>|<|>=|<=|IN|LIKE)\s*\?', part, re.IGNORECASE)
        if match:
            col, op = match.groups()
            if param_idx < len(params):
                val = params[param_idx]
                param_idx += 1
                if op == '=': query[col] = val
                elif op == '!=': query[col] = {"$ne": val}
                elif op == '>': query[col] = {"$gt": val}
                elif op == '<': query[col] = {"$lt": val}
                elif op == '>=': query[col] = {"$gte": val}
                elif op == '<=': query[col] = {"$lte": val}
        else:
            # Match literal values like "status = 'active'" or "status = active"
            match_lit = re.match(r"(\w+)\s*(=|!=)\s*'([^']+)'", part, re.IGNORECASE)
            if not match_lit:
                match_lit = re.match(r"(\w+)\s*(=|!=)\s*(\w+)", part, re.IGNORECASE)
            
            if match_lit:
                col, op, val = match_lit.groups()
                # Si val est purement numérique, on le convertit
                if val.isdigit(): val = int(val)
                
                if op == '=': query[col] = val
                elif op == '!=': query[col] = {"$ne": val}
            else:
                # Match numeric literals like "level = 1"
                match_num = re.match(r"(\w+)\s*(=|!=|>|<|>=|<=)\s*(\d+)", part, re.IGNORECASE)
                if match_num:
                    col, op, val = match_num.groups()
                    val = int(val)
                    if op == '=': query[col] = val
                    elif op == '!=': query[col] = {"$ne": val}
                    elif op == '>': query[col] = {"$gt": val}
                    elif op == '<': query[col] = {"$lt": val}
                    elif op == '>=': query[col] = {"$gte": val}
                    elif op == '<=': query[col] = {"$lte": val}
    return query

def get_next_sequence_value(sequence_name):
    result = db.counters.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=True
    )
    return result["sequence_value"]

def execute_query(query: str, params: tuple = ()) -> None:
    query_upper = query.strip().upper()
    
    # CREATE TABLE - Ignoré
    if any(query_upper.startswith(cmd) for cmd in ["CREATE TABLE", "DROP TABLE", "PRAGMA", "ALTER TABLE"]):
        return

    # INSERT INTO table (cols) VALUES (?, ?, ...)
    stripped_query = query.strip()
    match_insert = re.match(r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)", stripped_query, re.IGNORECASE | re.DOTALL)
    if match_insert:
        table, cols_str, vals_placeholder = match_insert.groups()
        cols = [c.strip() for c in cols_str.split(",")]
        
        # S'assurer que le nombre de paramètres correspond
        if len(cols) != len(params):
            return
            
        doc = dict(zip(cols, params))
        
        # Gestion de l'auto-increment
        auto_inc_tables = {
            "marketplace_listings": "listing_id",
            "warnings": "id",
            "backups": "id",
            "user_notifications": "notification_id",
            "tickets": "id",
            "state_orders": "order_id",
            "bounties": "bounty_id"
        }
        
        table_lower = table.lower()
        if table_lower in auto_inc_tables:
            id_col = auto_inc_tables[table_lower]
            if id_col not in doc or doc[id_col] is None:
                doc[id_col] = get_next_sequence_value(table_lower + "_" + id_col)
        
        # INSERT OR REPLACE / INSERT OR IGNORE
        if "REPLACE" in query_upper:
            filter_doc = {}
            # Clés d'unicité courantes pour MongoDB
            for key in ["guild_id", "user_id", "listing_id", "id", "owner_id", "channel_id"]:
                if key in doc and doc[key] is not None: 
                    filter_doc[key] = doc[key]
            
            if not filter_doc: filter_doc = doc
            db[table].update_one(filter_doc, {"$set": doc}, upsert=True)
        else:
            try: 
                db[table].insert_one(doc)
            except Exception as e:
                print(f"[ERROR] MongoDB INSERT in {table}: {e}")
        return

    stripped_query = query.strip()
    match_update = re.match(r"UPDATE\s+(\w+)\s+SET\s+(.*?)\s+WHERE\s+(.*)", stripped_query, re.IGNORECASE | re.DOTALL)
    if match_update:
        table, set_clause, where_clause = match_update.groups()
        set_params_count = set_clause.count('?')
        set_params = params[:set_params_count]
        where_params = params[set_params_count:]
        
        filter_doc = parse_sql_where(where_clause, where_params)
        
        updates = {"$set": {}, "$inc": {}}
        set_parts = [p.strip() for p in set_clause.split(",")]
        for i, part in enumerate(set_parts):
            # Gérer "col = col + ?" ou "col = col - ?"
            inc_match = re.match(r"(\w+)\s*=\s*\1\s*([+-])\s*\?", part, re.IGNORECASE)
            if inc_match:
                col, op = inc_match.groups()
                val = set_params[i]
                updates["$inc"][col] = val if op == '+' else -val
            else:
                set_match = re.match(r"(\w+)\s*=\s*\?", part, re.IGNORECASE)
                if set_match:
                    col = set_match.group(1)
                    updates["$set"][col] = set_params[i]
        
        if not updates["$inc"]: del updates["$inc"]
        if not updates["$set"]: del updates["$set"]
        
        if updates:
            db[table].update_many(filter_doc, updates)
        return

    stripped_query = query.strip()
    match_delete = re.match(r"DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?", stripped_query, re.IGNORECASE | re.DOTALL)
    if match_delete:
        table, where_clause = match_delete.groups()
        filter_doc = parse_sql_where(where_clause, params) if where_clause else {}
        db[table].delete_many(filter_doc)
        return

def fetch_one(query: str, params: tuple = ()) -> Optional[tuple]:
    stripped_query = query.strip()
    query_upper = stripped_query.upper()
    if not query_upper.startswith("SELECT"): return None
    
    # Gérer "SELECT 1 FROM ..."
    if re.match(r"SELECT\s+1\s+FROM", stripped_query, re.IGNORECASE):
        table_match = re.search(r"FROM\s+(\w+)", stripped_query, re.IGNORECASE)
        if table_match:
            table = table_match.group(1)
            where_match = re.search(r"WHERE\s+(.*?)(?=\s+ORDER\s+BY|\s+LIMIT|$)", stripped_query, re.IGNORECASE | re.DOTALL)
            where_clause = where_match.group(1).strip() if where_match else None
            filter_doc = parse_sql_where(where_clause, params) if where_clause else {}
            doc = db[table].find_one(filter_doc)
            return (1,) if doc else None

    # Extraction plus robuste
    table_match = re.search(r"FROM\s+(\w+)", stripped_query, re.IGNORECASE)
    if not table_match: return None
    table = table_match.group(1)
    
    cols_match = re.search(r"SELECT\s+(.*?)\s+FROM", stripped_query, re.IGNORECASE | re.DOTALL)
    cols_str = cols_match.group(1).strip() if cols_match else "*"
    
    where_match = re.search(r"WHERE\s+(.*?)(?=\s+ORDER\s+BY|\s+LIMIT|$)", stripped_query, re.IGNORECASE | re.DOTALL)
    where_clause = where_match.group(1).strip() if where_match else None
    
    filter_doc = parse_sql_where(where_clause, params) if where_clause else {}
    doc = db[table].find_one(filter_doc)
    
    if not doc: return None
    
    if cols_str == "*":
        doc.pop("_id", None)
        # Trier les clés pour assurer un ordre déterministe
        vals = [doc.get(k) for k in sorted(doc.keys())]
    else:
        cols = [c.strip() for c in cols_str.split(",")]
        if len(cols) == 1 and cols[0].upper().startswith("COUNT("):
            count = db[table].count_documents(filter_doc)
            return (count,)
        
        vals = []
        for c in cols:
            val = doc.get(c)
            # Casting pour les colonnes numériques connues
            numeric_cols = ["wallet", "bank", "tresorerie", "tresorerie_max", "revenue", "maintenance_cost", "nb_work_restants", "nb_work_requis", "salaire", "quantity", "price_per_unit", "price", "listing_id", "id"]
            if c in numeric_cols:
                if val is None:
                    val = 0
                else:
                    try: val = int(val)
                    except: pass
            vals.append(val)
        
    row = []
    for v in vals:
        if isinstance(v, (dict, list)):
            import json
            row.append(json.dumps(v))
        else:
            row.append(v)
    return tuple(row)

def fetch_all(query: str, params: tuple = ()) -> List[tuple]:
    stripped_query = query.strip()
    query_upper = stripped_query.upper()
    if not query_upper.startswith("SELECT"): return []
    
    # Extraction plus robuste
    table_match = re.search(r"FROM\s+(\w+)", stripped_query, re.IGNORECASE)
    if not table_match: return []
    table = table_match.group(1)
    
    cols_match = re.search(r"SELECT\s+(.*?)\s+FROM", stripped_query, re.IGNORECASE | re.DOTALL)
    cols_str = cols_match.group(1).strip() if cols_match else "*"
    
    where_match = re.search(r"WHERE\s+(.*?)(?=\s+ORDER\s+BY|\s+LIMIT|$)", stripped_query, re.IGNORECASE | re.DOTALL)
    where_clause = where_match.group(1).strip() if where_match else None
    
    order_match = re.search(r"ORDER\s+BY\s+(.*?)(?=\s+LIMIT|$)", stripped_query, re.IGNORECASE | re.DOTALL)
    order_clause = order_match.group(1).strip() if order_match else None
    
    limit_match = re.search(r"LIMIT\s+(\d+)", stripped_query, re.IGNORECASE)
    limit = limit_match.group(1) if limit_match else None

    filter_doc = parse_sql_where(where_clause, params) if where_clause else {}
    
    cursor = db[table].find(filter_doc)
    if order_clause:
        # Simple order: "col DESC"
        order_parts = order_clause.strip().split()
        col = order_parts[0]
        direction = -1 if "DESC" in order_clause.upper() else 1
        cursor = cursor.sort(col, direction)
    if limit:
        cursor = cursor.limit(int(limit))
        
    results = []
    cols = [c.strip() for c in cols_str.split(",")]
    
    for doc in cursor:
        doc.pop("_id", None)
        if cols_str == "*":
            # Trier les clés pour assurer un ordre déterministe
            vals = [doc.get(k) for k in sorted(doc.keys())]
        else:
            vals = []
            for c in cols:
                val = doc.get(c)
                # Casting numérique si nécessaire
                numeric_cols = ["wallet", "bank", "tresorerie", "tresorerie_max", "revenue", "maintenance_cost", "nb_work_restants", "nb_work_requis", "salaire", "quantity", "price_per_unit", "price", "listing_id", "id", "expires_at", "created_at"]
                if c in numeric_cols:
                    if val is None:
                        val = 0
                    else:
                        try: val = int(val)
                        except: pass
                vals.append(val)
            
        row = []
        for v in vals:
            if isinstance(v, (dict, list)):
                import json
                row.append(json.dumps(v))
            else:
                row.append(v)
        results.append(tuple(row))
    return results

# ---- HACK / DDOS ----
def get_user_ddos(guild_id: str, user_id: str) -> Optional[str]:
    user = db.users.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    return user.get("ddos_until") if user else None

def set_user_ddos(guild_id: str, user_id: str, expiry_iso: str) -> None:
    db.users.update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        {"$set": {"ddos_until": expiry_iso}},
        upsert=True
    )

def get_ddos_cooldown(guild_id: str, user_id: str) -> Optional[str]:
    user = db.users.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    return user.get("last_ddos_attempt") if user else None

def set_ddos_cooldown(guild_id: str, user_id: str, timestamp_iso: str) -> None:
    db.users.update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        {"$set": {"last_ddos_attempt": timestamp_iso}},
        upsert=True
    )

# ---- DRUGS PLANTATION ----
def get_drug_plantation(guild_id: str, user_id: str) -> Optional[Dict]:
    return db.drug_plantations.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})

def update_drug_plantation(guild_id: str, user_id: str, data: Dict) -> None:
    db.drug_plantations.update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        {"$set": data},
        upsert=True
    )

def delete_drug_plantation(guild_id: str, user_id: str) -> None:
    db.drug_plantations.delete_one({"guild_id": str(guild_id), "user_id": str(user_id)})

# ---- CRYPTO ----
def get_crypto_data() -> Dict:
    """Returns current price and history list of dicts"""
    data = db.crypto.find_one({"_id": "ghostcoin"})
    if not data:
        data = {
            "_id": "ghostcoin",
            "current_price": 100,
            "history": [{"price": 100, "timestamp": datetime.now().isoformat()}],
            "last_update": datetime.now().isoformat()
        }
        db.crypto.insert_one(data)
    return data

def update_crypto_data(new_price: int, history: List[Dict]) -> None:
    db.crypto.update_one(
        {"_id": "ghostcoin"},
        {"$set": {
            "current_price": new_price,
            "history": history,
            "last_update": datetime.now().isoformat()
        }},
        upsert=True
    )

def get_user_crypto(guild_id: str, user_id: str) -> int:
    user = db.users.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    return int(user.get("crypto", 0)) if user else 0

def update_user_crypto(guild_id: str, user_id: str, amount: int) -> None:
    db.users.update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        {"$inc": {"crypto": amount}},
        upsert=True
    )

# ---- FONCTIONS UTILISATEURS ----
def user_init(guild_id: str, user_id: str) -> None:
    guild_id, user_id = str(guild_id), str(user_id)
    # On s'assure que les champs existent même pour les utilisateurs déjà créés
    db.users.update_one(
        {"guild_id": guild_id, "user_id": user_id},
        {"$setOnInsert": {"wallet": 0, "bank": 0}},
        upsert=True
    )
    # Migration/Fix pour les champs manquants
    db.users.update_one(
        {"guild_id": guild_id, "user_id": user_id, "wallet": {"$exists": False}},
        {"$set": {"wallet": 0}}
    )
    db.users.update_one(
        {"guild_id": guild_id, "user_id": user_id, "bank": {"$exists": False}},
        {"$set": {"bank": 0}}
    )

    db.inventaire.update_one(
        {"guild_id": guild_id, "user_id": user_id},
        {"$setOnInsert": {"inventory": {}}},
        upsert=True
    )
    db.jobs.update_one(
        {"guild_id": guild_id, "user_id": user_id},
        {"$setOnInsert": {
            "current_job": "livreur",
            "knowledge": 0,
            "unlocked_jobs": ["livreur"],
            "work_count": 0,
            "last_work": None
        }},
        upsert=True
    )

def get_user_wallet(guild_id: str, user_id: str) -> int:
    user = db.users.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    return int(user.get("wallet", 0)) if user else 0

def get_wallet_bank(guild_id: str, user_id: str) -> Dict[str, int]:
    user = db.users.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    if user:
        return {"wallet": user.get("wallet", 0), "bank": user.get("bank", 0)}
    return {"wallet": 0, "bank": 0}

def update_wallet(guild_id: str, user_id: str, amount: int) -> None:
    guild_id, user_id = str(guild_id), str(user_id)
    db.users.update_one(
        {"guild_id": guild_id, "user_id": user_id},
        {"$inc": {"wallet": amount}},
        upsert=True
    )
    # Assurer que le wallet n'est pas négatif
    db.users.update_one(
        {"guild_id": guild_id, "user_id": user_id, "wallet": {"$lt": 0}},
        {"$set": {"wallet": 0}}
    )

def update_bank(guild_id: str, user_id: str, amount: int) -> None:
    guild_id, user_id = str(guild_id), str(user_id)
    db.users.update_one(
        {"guild_id": guild_id, "user_id": user_id},
        {"$inc": {"bank": amount}},
        upsert=True
    )
    # Assurer que la banque n'est pas négative
    db.users.update_one(
        {"guild_id": guild_id, "user_id": user_id, "bank": {"$lt": 0}},
        {"$set": {"bank": 0}}
    )

def get_all_users_with_balances(guild_id: str) -> List[tuple]:
    users = db.users.find({"guild_id": str(guild_id)})
    return [(u["user_id"], u.get("wallet", 0), u.get("bank", 0)) for u in users]

# ---- FONCTIONS INVENTAIRE ----
def get_inventaire(guild_id: str, user_id: str) -> Dict:
    inv = db.inventaire.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    return inv.get("inventory", {}) if inv else {}

def update_inventaire(guild_id: str, user_id: str, inventory: Dict) -> None:
    db.inventaire.update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        {"$set": {"inventory": inventory}},
        upsert=True
    )

# ---- FONCTIONS INVESTISSEMENTS ----
def get_investissements(guild_id: str, user_id: str) -> Dict:
    inv = db.investissements.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    if not inv: return {}
    return {
        "nom_invest": inv.get("nom_invest"),
        "duration": inv.get("duration"),
        "reward": inv.get("reward"),
        "start": inv.get("start"),
        "end": inv.get("end")
    }

def update_investissements(guild_id: str, user_id: str, invest_dict: Optional[Dict]) -> None:
    if not invest_dict:
        db.investissements.delete_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    else:
        db.investissements.update_one(
            {"guild_id": str(guild_id), "user_id": str(user_id)},
            {"$set": invest_dict},
            upsert=True
        )

# ---- FONCTIONS JOBS ----
def get_job_data(guild_id: str, user_id: str) -> Dict:
    job = db.jobs.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    if job:
        return {
            "current_job": job.get("current_job", "Livreur"),
            "knowledge": job.get("knowledge", 0),
            "unlocked_jobs": job.get("unlocked_jobs", ["Livreur", "Agent de nettoyage", "Caissier"]),
            "work_count": job.get("work_count", 0),
            "last_work": job.get("last_work")
        }
    return {"current_job": "Livreur", "knowledge": 0, "unlocked_jobs": ["Livreur", "Agent de nettoyage", "Caissier"], "work_count": 0, "last_work": None}

def update_job(guild_id: str, user_id: str, key: str, value: Union[str, int, List]) -> None:
    db.jobs.update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        {"$set": {key: value}},
        upsert=True
    )

def get_work_cooldown(guild_id: str, user_id: str) -> Optional[str]:
    job = db.jobs.find_one({"guild_id": str(guild_id), "user_id": str(user_id)})
    return job.get("last_work") if job else None

def update_work_cooldown(guild_id: str, user_id: str, timestamp: str) -> None:
    db.jobs.update_one(
        {"guild_id": str(guild_id), "user_id": str(user_id)},
        {"$set": {"last_work": timestamp}},
        upsert=True
    )

# ---- FONCTIONS ENTREPRISES ----
def create_entreprise(guild_id: str, owner_id: str, nom: str) -> None:
    db.entreprises.update_one(
        {"guild_id": str(guild_id), "owner_id": str(owner_id)},
        {"$set": {
            "nom": nom,
            "tresorerie": 0,
            "tresorerie_max": 10000,
            "nb_work_requis": 10,
            "nb_work_restants": 10,
            "revenu_par_cycle": 1000,
            "visibilite": "prive"
        }},
        upsert=True
    )

def get_entreprise(guild_id: str, owner_id: str) -> Optional[Dict]:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    if not ent: return None
    return {
        "nom": ent.get("nom"),
        "tresorerie": int(ent.get("tresorerie", 0)),
        "tresorerie_max": int(ent.get("tresorerie_max", 10000)),
        "nb_work_requis": int(ent.get("nb_work_requis", 0)),
        "nb_work_restants": int(ent.get("nb_work_restants", 0)),
        "visibilite": ent.get("visibilite"),
        "revenu_par_cycle": int(ent.get("revenu_par_cycle", 0)),
        "last_rename": ent.get("last_rename")
    }

def get_entreprise_by_name(guild_id: str, nom_entreprise: str) -> Optional[Dict]:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "nom": nom_entreprise})
    if ent:
        ent["tresorerie"] = int(ent.get("tresorerie", 0))
        ent["tresorerie_max"] = int(ent.get("tresorerie_max", 10000))
        ent["nb_work_requis"] = int(ent.get("nb_work_requis", 0))
        ent["nb_work_restants"] = int(ent.get("nb_work_restants", 0))
        ent["revenu_par_cycle"] = int(ent.get("revenu_par_cycle", 0))
    return ent

def update_entreprise_name(guild_id: str, owner_id: str, new_name: str, timestamp: Optional[str] = None) -> None:
    db.entreprises.update_one(
        {"guild_id": str(guild_id), "owner_id": str(owner_id)},
        {"$set": {"nom": new_name, "last_rename": timestamp}}
    )

def update_entreprise_visibility(guild_id: str, owner_id: str, new_visibility: str) -> None:
    db.entreprises.update_one(
        {"guild_id": str(guild_id), "owner_id": str(owner_id)},
        {"$set": {"visibilite": new_visibility}}
    )

def get_tresorerie_entreprise(guild_id: str, owner_id: str) -> int:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    return ent.get("tresorerie", 0) if ent else 0

def update_tresorerie_entreprise(guild_id: str, owner_id: str, montant: int) -> None:
    db.entreprises.update_one(
        {"guild_id": str(guild_id), "owner_id": str(owner_id)},
        {"$set": {"tresorerie": montant}}
    )

def set_entreprise_tresorerie(guild_id: str, owner_id: str, montant: int) -> None:
    update_tresorerie_entreprise(guild_id, owner_id, montant)

def get_work_restants(guild_id: str, owner_id: str) -> int:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    return ent.get("nb_work_restants", 0) if ent else 0

def update_work_restants(guild_id: str, owner_id: str, reste: int) -> None:
    db.entreprises.update_one(
        {"guild_id": str(guild_id), "owner_id": str(owner_id)},
        {"$set": {"nb_work_restants": reste}}
    )

def set_work_restants(guild_id: str, owner_id: str, reste: int) -> None:
    update_work_restants(guild_id, owner_id, reste)

def get_work_requis(guild_id: str, owner_id: str) -> int:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    return ent.get("nb_work_requis", 0) if ent else 0

def get_revenu_par_cycle(guild_id: str, owner_id: str) -> int:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    return ent.get("revenu_par_cycle", 0) if ent else 0

def withdraw_entreprise_money(guild_id: str, owner_id: str, amount: int) -> bool:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    if ent and ent.get("tresorerie", 0) >= amount:
        db.entreprises.update_one(
            {"guild_id": str(guild_id), "owner_id": str(owner_id)},
            {"$inc": {"tresorerie": -amount}}
        )
        update_bank(guild_id, owner_id, amount)
        return True
    return False

def delete_entreprise(guild_id: str, owner_id: str) -> None:
    gid, oid = str(guild_id), str(owner_id)
    db.entreprise_employes.delete_many({"guild_id": gid, "entreprise_owner_id": oid})
    db.entreprise_buildings.delete_many({"guild_id": gid, "entreprise_owner_id": oid})
    db.entreprises.delete_one({"guild_id": gid, "owner_id": oid})

def get_name_entreprise(guild_id: str, owner_id: str) -> str:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    return ent.get("nom", "Entreprise sans nom") if ent else "Entreprise sans nom"

def get_name_change_cooldown(guild_id: str, owner_id: str) -> int:
    ent = db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(owner_id)})
    if not ent or not ent.get("last_rename"): return 0
    try:
        last_rename = datetime.fromisoformat(ent["last_rename"])
        elapsed = (datetime.now() - last_rename).total_seconds()
        return max(0, int(24 * 3600 - elapsed))
    except: return 0

def get_all_entreprises_by_guild(guild_id: str) -> List[tuple]:
    ents = db.entreprises.find({"guild_id": str(guild_id)})
    result = []
    for e in ents:
        emp_count = db.entreprise_employes.count_documents({"guild_id": str(guild_id), "entreprise_owner_id": e["owner_id"]})
        result.append((
            e["owner_id"],
            e.get("nom", "Entreprise sans nom"),
            int(e.get("tresorerie", 0)),
            int(e.get("tresorerie_max", 10000)),
            e.get("visibilite", "prive"),
            int(e.get("revenu_par_cycle", 1000)),
            emp_count
        ))
    return result

# ---- FONCTIONS EMPLOYES ----
def add_employe(guild_id: str, owner_id: str, employe_id: str, role: str = "employe", salaire: int = 0) -> None:
    db.entreprise_employes.update_one(
        {"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id), "employe_id": str(employe_id)},
        {"$set": {"role": role, "salaire": int(salaire), "nb_work_effectues": 0}},
        upsert=True
    )

def remove_employe(guild_id: str, owner_id: str, employe_id: str) -> None:
    db.entreprise_employes.delete_one({"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id), "employe_id": str(employe_id)})

def get_employes(guild_id: str, owner_id: str) -> List[Dict]:
    emps = db.entreprise_employes.find({"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id)})
    return [{"employe_id": e["employe_id"], "role": e.get("role"), "salaire": int(e.get("salaire", 0)), "nb_work_effectues": int(e.get("nb_work_effectues", 0))} for e in emps]

def get_employe(guild_id: str, owner_id: str, employe_id: str) -> Optional[Dict]:
    emp = db.entreprise_employes.find_one({"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id), "employe_id": str(employe_id)})
    if not emp: return None
    return {"role": emp.get("role"), "salaire": int(emp.get("salaire", 0)), "nb_work_effectues": int(emp.get("nb_work_effectues", 0))}

def update_employe_role(guild_id: str, owner_id: str, employe_id: str, role: str) -> None:
    db.entreprise_employes.update_one(
        {"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id), "employe_id": str(employe_id)},
        {"$set": {"role": role}}
    )

def update_employe_salaire(guild_id: str, owner_id: str, employe_id: str, salaire: int) -> None:
    db.entreprise_employes.update_one(
        {"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id), "employe_id": str(employe_id)},
        {"$set": {"salaire": salaire}}
    )

def increment_work_effectue(guild_id: str, user_id: str) -> None:
    emp = db.entreprise_employes.find_one({"guild_id": str(guild_id), "employe_id": str(user_id)})
    if emp:
        ent_id = emp["entreprise_owner_id"]
        db.entreprise_employes.update_one(
            {"guild_id": str(guild_id), "entreprise_owner_id": ent_id, "employe_id": str(user_id)},
            {"$inc": {"nb_work_effectues": 1}}
        )
        db.entreprises.update_one(
            {"guild_id": str(guild_id), "owner_id": ent_id},
            {"$inc": {"nb_work_restants": -1}}
        )

def is_employe(guild_id: str, user_id: str) -> bool:
    return db.entreprise_employes.find_one({"guild_id": str(guild_id), "employe_id": str(user_id)}) is not None

def is_entreprise_owner(guild_id: str, user_id: str) -> bool:
    return db.entreprises.find_one({"guild_id": str(guild_id), "owner_id": str(user_id)}) is not None

def get_entreprise_owner_id(guild_id: str, user_id: str) -> Optional[str]:
    emp = db.entreprise_employes.find_one({"guild_id": str(guild_id), "employe_id": str(user_id)})
    return emp["entreprise_owner_id"] if emp else None

def has_permission(guild_id: str, user_id: str, permission: str) -> bool:
    if is_entreprise_owner(guild_id, user_id): return True
    owner_id = get_entreprise_owner_id(guild_id, user_id)
    if not owner_id: return False
    emp = get_employe(guild_id, owner_id, user_id)
    if not emp: return False
    
    role = emp["role"].lower()
    # Gestion des accents pour la compatibilité
    role_map = {"employé": "employe", "stagiaire": "stagiaire", "manager": "manager", "directeur": "directeur"}
    role_key = role_map.get(role, role)
    
    role_info = EMPLOYEE_ROLES.get(role_key)
    return permission in role_info["permissions"] if role_info else False

# ---- FONCTIONS BÂTIMENTS ----
def add_building(guild_id: str, owner_id: str, building_type: str) -> bool:
    if building_type not in BUILDING_TYPES: return False
    buildings = list(db.entreprise_buildings.find({"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id)}))
    next_id = max([int(b.get("building_id", 0)) for b in buildings] + [0]) + 1
    db.entreprise_buildings.insert_one({
        "guild_id": str(guild_id),
        "entreprise_owner_id": str(owner_id),
        "building_type": building_type,
        "level": 1,
        "last_maintenance": datetime.now().isoformat(),
        "building_id": next_id
    })
    update_max_tresorerie(guild_id, owner_id)
    return True

def get_building_gold_cost(level: int) -> int:
    """Return the amount of gold (Or) required to upgrade to this level."""
    if level >= 5:
        return 5 # Requires 5 Gold for level 5 and above
    return 0

def upgrade_building(guild_id: str, owner_id: str, building_id: int) -> bool:
    db.entreprise_buildings.update_one(
        {"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id), "building_id": int(building_id)},
        {"$inc": {"level": 1}}
    )
    update_max_tresorerie(guild_id, owner_id)
    return True

def get_entreprise_buildings(guild_id: str, owner_id: str) -> List[Dict]:
    rows = db.entreprise_buildings.find({"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id)}).sort("building_id", 1)
    buildings = []
    for row in rows:
        try:
            b_type = row["building_type"]
            level = int(row.get("level", 1))
            last_m = row.get("last_maintenance")
            b_id = int(row.get("building_id", 0))
            if b_type in BUILDING_TYPES:
                info = BUILDING_TYPES[b_type].copy()
                # Calculer les stats dynamiques ici pour plus de sécurité
                info.update({
                    "building_type": b_type, 
                    "level": level, 
                    "last_maintenance": last_m, 
                    "building_id": b_id,
                    "revenue": get_building_revenue(b_type, level),
                    "maintenance_cost": get_building_maintenance(b_type, level),
                    "work_required": get_building_work_required(b_type, level)
                })
                buildings.append(info)
        except: continue
    return buildings

def update_max_tresorerie(guild_id: str, owner_id: str) -> None:
    buildings = get_entreprise_buildings(guild_id, owner_id)
    total = 10000 + sum(BUILDING_TYPES[b["building_type"]]["storage_bonus"] * b["level"] for b in buildings if b["building_type"] in BUILDING_TYPES)
    db.entreprises.update_one(
        {"guild_id": str(guild_id), "owner_id": str(owner_id)},
        {"$set": {"tresorerie_max": int(total)}}
    )

def reorganize_building_ids(guild_id: str, owner_id: str) -> None:
    buildings = list(db.entreprise_buildings.find({"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id)}).sort("building_id", 1))
    db.entreprise_buildings.delete_many({"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id)})
    for i, b in enumerate(buildings, 1):
        b.pop("_id", None)
        b["building_id"] = i
        db.entreprise_buildings.insert_one(b)

def get_building_upgrade_cost(guild_id: str, owner_id: str, building_id: int) -> int:
    row = db.entreprise_buildings.find_one({"guild_id": str(guild_id), "entreprise_owner_id": str(owner_id), "building_id": building_id})
    if not row: return 0
    b_type, level = row["building_type"], row["level"]
    return get_building_cost(b_type, level + 1)

def get_building_cost(b_type: str, level: int) -> int:
    if b_type not in BUILDING_TYPES: return 0
    return int(BUILDING_TYPES[b_type]["base_cost"] * (BUILDING_TYPES[b_type]["cost_multiplier"] ** (level - 1)))

def get_building_revenue(b_type: str, level: int) -> int:
    if b_type not in BUILDING_TYPES: return 0
    return int(BUILDING_TYPES[b_type]["base_revenue"] * (BUILDING_TYPES[b_type]["revenue_multiplier"] ** (level - 1)))

def get_building_maintenance(b_type: str, level: int) -> int:
    if b_type not in BUILDING_TYPES: return 0
    return int(BUILDING_TYPES[b_type]["base_maintenance"] * (BUILDING_TYPES[b_type]["maintenance_multiplier"] ** (level - 1)))

def get_building_work_required(b_type: str, level: int) -> int:
    if b_type not in BUILDING_TYPES: return 0
    return int(BUILDING_TYPES[b_type]["base_work"] * (BUILDING_TYPES[b_type]["work_multiplier"] ** (level - 1)))

def calculate_total_revenue(guild_id: str, owner_id: str) -> int:
    buildings = get_entreprise_buildings(guild_id, owner_id)
    return sum(get_building_revenue(b["building_type"], b["level"]) for b in buildings)

def calculate_total_maintenance_cost(guild_id: str, owner_id: str) -> int:
    buildings = get_entreprise_buildings(guild_id, owner_id)
    return sum(get_building_maintenance(b["building_type"], b["level"]) for b in buildings)

def calculate_total_work_required(guild_id: str, owner_id: str) -> int:
    buildings = get_entreprise_buildings(guild_id, owner_id)
    return sum(get_building_work_required(b["building_type"], b["level"]) for b in buildings)

# ---- FONCTIONS MARKETPLACE ----
def get_marketplace_listings():
    listings = db.marketplace_listings.find({"status": "active", "expires_at": {"$gt": datetime.now().timestamp()}})
    # Conversion vers le format attendu par le reste du code (tuples ou dicts selon l'usage)
    # Dans SQLite fetch_all retournait des tuples. Si le code utilise des index numériques, il faut des tuples.
    # On va retourner des tuples pour matcher le comportement SQLite.
    result = []
    for l in listings:
        result.append((
            l.get("guild_id"),
            l.get("listing_id"),
            l.get("seller_id"),
            l.get("item_name"),
            l.get("quantity"),
            l.get("price_per_unit"),
            l.get("description", ""),
            l.get("created_at"),
            l.get("expires_at"),
            l.get("status")
        ))
    return result

def cancel_marketplace_listing(guild_id: str, listing_id: int, seller_id: str) -> Tuple[bool, str]:
    listing = db.marketplace_listings.find_one({
        "guild_id": str(guild_id), 
        "listing_id": int(listing_id), 
        "seller_id": str(seller_id),
        "status": "active"
    })
    
    if not listing:
        return False, "Annonce introuvable ou déjà traitée."
        
    # Marquer comme annulé
    db.marketplace_listings.update_one(
        {"_id": listing["_id"]},
        {"$set": {"status": "cancelled"}}
    )
    
    # Rendre les items au vendeur
    item_name = listing["item_name"]
    quantity = listing["quantity"]
    
    inventory = get_inventaire(guild_id, seller_id)
    # On utilise une version simplifiée car update_inventory_quantity est définie plus haut dans database.py (si elle l'est)
    # En fait elle est définie dans database.py ? Je dois vérifier.
    # Apparemment elle est dans marketplace.py mais pas forcément dans database.py.
    # Ah si, je l'ai vue dans marketplace.py. Dans database.py je vais faire une mise à jour directe.
    
    db.inventaire.update_one(
        {"guild_id": str(guild_id), "user_id": str(seller_id)},
        {"$inc": {f"inventory.{item_name}.quantity": quantity}},
        upsert=True
    )
    # Si l'item n'était pas un dict mais un simple int, on le convertit (cas rare avec MongoDB flexible)
    # Mais ici on va supposer que le format est cohérent.
    
    return True, f"L'annonce a été annulée et {quantity}x {item_name} ont été rendus à votre inventaire."

def update_marketplace_price(guild_id: str, listing_id: int, seller_id: str, new_price: int) -> Tuple[bool, str]:
    if new_price <= 0:
        return False, "Le prix doit être positif."
        
    res = db.marketplace_listings.update_one(
        {
            "guild_id": str(guild_id), 
            "listing_id": int(listing_id), 
            "seller_id": str(seller_id),
            "status": "active"
        },
        {"$set": {"price_per_unit": new_price}}
    )
    
    if res.modified_count > 0:
        return True, f"Le prix a été mis à jour à {new_price} coins par unité."
    return False, "Annonce introuvable ou vous n'êtes pas le vendeur."

# ---- FONCTIONS PLANTES ----
def get_user_plants(user_id: int):
    plants = db.user_plants.find({"user_id": str(user_id)})
    return [(p["plant_type"], p.get("planted_date"), p.get("last_watered"), p.get("growth_stage"), p.get("water_days"), p.get("total_days")) for p in plants]

def manage_plant(user_id: int, action: str, plant_type: str = None, **kwargs) -> tuple[bool, str]:
    user_id = str(user_id)
    try:
        if action == "add":
            db.user_plants.insert_one({
                "user_id": user_id,
                "plant_type": plant_type,
                "planted_date": kwargs['planted_date'],
                "last_watered": kwargs['last_watered'],
                "growth_stage": 0,
                "water_days": kwargs['water_days'],
                "total_days": kwargs['total_days']
            })
            return True, "Plante ajoutée."
        elif action == "water":
            db.user_plants.update_one(
                {"user_id": user_id, "plant_type": plant_type},
                {"$set": {"last_watered": kwargs['new_water_date'], "growth_stage": kwargs['new_growth_stage']}}
            )
            return True, "Plante arrosée."
        elif action == "delete":
            db.user_plants.delete_one({"user_id": user_id, "plant_type": plant_type})
            return True, "Plante supprimée."
        return False, "Action inconnue."
    except Exception as e: return False, str(e)

# ---- FONCTIONS JULES ----
def get_config(guild_id: int):
    conf = db.guild_config.find_one({"guild_id": str(guild_id)})
    if conf:
        conf.pop("_id", None)
        # Conversion des IDs en int pour la compatibilité
        for key, val in conf.items():
            if key.endswith("_id") and val:
                try: conf[key] = int(val)
                except: pass
            if key == "support_role_ids" and isinstance(val, str):
                import json
                try: conf[key] = json.loads(val)
                except: pass
        return conf
    return None

def update_config(guild_id: int, **kwargs):
    updates = {}
    for k, v in kwargs.items():
        if k == "support_role_ids" and isinstance(v, list):
            import json
            updates[k] = json.dumps(v)
        else:
            updates[k] = str(v) if v is not None else None
            
    db.guild_config.update_one(
        {"guild_id": str(guild_id)},
        {"$set": updates},
        upsert=True
    )

def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str):
    db.warnings.insert_one({
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "moderator_id": str(moderator_id),
        "reason": reason,
        "timestamp": datetime.now().isoformat()
    })

def get_warnings(guild_id: int, user_id: int):
    warns = db.warnings.find({"guild_id": str(guild_id), "user_id": str(user_id)})
    return [(w["moderator_id"], w["reason"], w["timestamp"]) for w in warns]

def clear_warnings(guild_id: int, user_id: int):
    db.warnings.delete_many({"guild_id": str(guild_id), "user_id": str(user_id)})

def create_ticket(channel_id: int, guild_id: int, user_id: int):
    db.tickets.insert_one({
        "channel_id": str(channel_id),
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "status": "open"
    })

def close_ticket(channel_id: int):
    db.tickets.update_one({"channel_id": str(channel_id)}, {"$set": {"status": "closed"}})

def has_open_ticket(guild_id: int, user_id: int) -> bool:
    return db.tickets.find_one({"guild_id": str(guild_id), "user_id": str(user_id), "status": "open"}) is not None

# ---- PERMISSIONS DE COMMANDES ----
def reset_all_permissions(guild_id: str):
    """Supprime toutes les permissions de commandes configurées pour un serveur."""
    db.command_permissions.delete_many({"guild_id": guild_id})

def set_global_lock(guild_id: str, locked: bool):
    """Active ou désactive le lock global pour un serveur."""
    db.config.update_one(
        {"guild_id": guild_id},
        {"$set": {"global_lock": locked}},
        upsert=True
    )

def get_global_lock(guild_id: str) -> bool:
    """Récupère l'état du lock global."""
    config = db.config.find_one({"guild_id": guild_id})
    return config.get("global_lock", False) if config else False

def add_command_permission(guild_id: str, command_name: str, role_id: int):
    db.command_permissions.update_one(
        {"guild_id": str(guild_id), "command_name": command_name, "role_id": str(role_id)},
        {"$set": {"guild_id": str(guild_id), "command_name": command_name, "role_id": str(role_id)}},
        upsert=True
    )

def remove_command_permission(guild_id: str, command_name: str, role_id: str) -> None:
    db.command_permissions.delete_one({"guild_id": str(guild_id), "command_name": command_name, "role_id": str(role_id)})

def get_command_permissions(guild_id: str, command_name: str) -> List[str]:
    perms = db.command_permissions.find({"guild_id": str(guild_id), "command_name": command_name})
    return [p["role_id"] for p in perms]

# ---- ECONOMIE ----
def set_economy_enabled(guild_id: str, enabled: bool) -> None:
    db.guild_settings.update_one(
        {"guild_id": str(guild_id)},
        {"$set": {"economy_enabled": 1 if enabled else 0}},
        upsert=True
    )

def is_economy_enabled(guild_id: str) -> bool:
    res = db.guild_settings.find_one({"guild_id": str(guild_id)})
    return bool(res.get("economy_enabled", 1)) if res else True

def reset_guild_economy(guild_id: str) -> None:
    gid = str(guild_id)
    db.entreprise_employes.delete_many({"guild_id": gid})
    db.entreprise_buildings.delete_many({"guild_id": gid})
    db.marketplace_listings.delete_many({"guild_id": gid})
    db.investissements.delete_many({"guild_id": gid})
    db.jobs.delete_many({"guild_id": gid})
    db.inventaire.delete_many({"guild_id": gid})
    db.garden.delete_many({"guild_id": gid})
    db.entreprises.delete_many({"guild_id": gid})
    db.drug_plantations.delete_many({"guild_id": gid})
    db.users.delete_many({"guild_id": gid})
    # Reset crypto pour ce serveur (si stocké par serveur, ici c'est global mais on peut reset le lien)
    db.crypto.delete_many({"guild_id": gid})

def get_unread_notifications_count(user_id: int) -> int:
    return db.user_notifications.count_documents({"user_id": str(user_id), "read": 0})

# ---- BACKUPS ----
from bson.binary import Binary

def save_db_backup(guild_id: str, creator_id: str, name: str, data: bytes) -> None:
    # MongoDB a une limite de 16MB par document. On vÃ©rifie ici.
    if len(data) > 15 * 1024 * 1024:
        raise ValueError("La sauvegarde est trop volumineuse (> 15MB)")

    db.backups.insert_one({
        "guild_id": str(guild_id),
        "creator_id": str(creator_id),
        "name": name,
        "data": Binary(data), # Utilisation du type Binary de BSON pour l'optimisation
        "created_at": datetime.now().isoformat()
    })

def get_user_backups(creator_id: str) -> List[tuple]:
    # On ne rÃ©cupÃ¨re pas le champ 'data' ici pour Ã©conomiser de la bande passante
    backups = db.backups.find({"creator_id": str(creator_id)}, {"data": 0}).sort("created_at", -1)
    return [(str(b.get("_id")), b.get("name"), b.get("created_at"), b.get("guild_id")) for b in backups]

def get_backup_data(backup_id: str) -> Optional[bytes]:
    from bson.objectid import ObjectId
    try:
        b = db.backups.find_one({"_id": ObjectId(backup_id)})
        if b and "data" in b:
            # MongoDB retourne un objet Binary, on le convertit en bytes
            return bytes(b["data"])
        return None
    except: return None
def delete_db_backup(backup_id: str, creator_id: str) -> bool:
    from bson.objectid import ObjectId
    try:
        res = db.backups.delete_one({"_id": ObjectId(backup_id), "creator_id": str(creator_id)})
        return res.deleted_count > 0
    except: return False

def update_db_structure():
    # Avec MongoDB, la structure est flexible, donc peu de choses à faire ici
    pass

init_db()
