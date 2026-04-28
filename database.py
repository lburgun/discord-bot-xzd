import sqlite3
import json
from typing import Optional, Dict, List, Union
from datetime import datetime

DB_NAME = "economy.db"

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
        "max_quantity": 3,
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
        "max_quantity": 2,
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
        "max_quantity": 2,
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
        "max_quantity": 2,
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
        "max_quantity": 2,
        "storage_bonus": 2500
    }
}

def get_conn():
    return sqlite3.connect(
        DB_NAME,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        isolation_level=None,
        timeout=10,
        check_same_thread=False
    )

def init_db():
    """Initialise la base de données avec toutes les tables nécessaires"""
    with get_conn() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Table users
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                guild_id TEXT,
                user_id TEXT,
                wallet INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Table user_items (utilisée par marketplace et phone)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_items (
                user_id INTEGER,
                item_name TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, item_name)
            )
        """)

        # Table inventaire (utilisée par d'autres modules)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventaire (
                guild_id TEXT,
                user_id TEXT,
                inventory TEXT DEFAULT '{}',
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Table jobs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                guild_id TEXT,
                user_id TEXT,
                current_job TEXT,
                knowledge INTEGER DEFAULT 0,
                unlocked_jobs TEXT DEFAULT '[]',
                work_count INTEGER DEFAULT 0,
                last_work TEXT DEFAULT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Table investissements
        conn.execute("""
            CREATE TABLE IF NOT EXISTS investissements (
                guild_id TEXT,
                user_id TEXT,
                nom_invest TEXT,
                duration INTEGER,
                reward INTEGER,
                start TEXT,
                end TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Table entreprises
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entreprises (
                guild_id TEXT,
                owner_id TEXT,
                nom TEXT DEFAULT 'Entreprise sans nom',
                tresorerie INTEGER DEFAULT 0,
                tresorerie_max INTEGER DEFAULT 1000,
                nb_work_requis INTEGER DEFAULT 9,
                nb_work_restants INTEGER DEFAULT 9,
                visibilite TEXT DEFAULT 'publique',
                revenu_par_cycle INTEGER DEFAULT 1000,
                last_rename TEXT DEFAULT NULL,
                PRIMARY KEY (guild_id, owner_id)
            )
        """)

        # Table entreprise_employes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entreprise_employes (
                guild_id TEXT,
                entreprise_owner_id TEXT,
                employe_id TEXT,
                role TEXT DEFAULT 'employe',
                salaire INTEGER DEFAULT 500,
                nb_work_effectues INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, entreprise_owner_id, employe_id)
            )
        """)

        # Table entreprise_buildings
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entreprise_buildings (
                guild_id TEXT,
                entreprise_owner_id TEXT,
                building_type TEXT,
                level INTEGER DEFAULT 1,
                last_maintenance TEXT,
                building_id INTEGER,
                PRIMARY KEY (guild_id, entreprise_owner_id, building_id)
            )
        """)

        # Table marketplace_listings
        conn.execute("""
            CREATE TABLE IF NOT EXISTS marketplace_listings (
                guild_id TEXT NOT NULL,
                listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                price_per_unit INTEGER NOT NULL CHECK (price_per_unit > 0),
                description TEXT DEFAULT '',
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                expires_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now', '+1 day')),
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'sold', 'cancelled', 'expired'))
            )
        """)

        # Table garden
        conn.execute("""
            CREATE TABLE IF NOT EXISTS garden (
                guild_id TEXT,
                user_id TEXT,
                plant_type TEXT,
                planted_at REAL,
                last_watered REAL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Table user_plants
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_plants (
                user_id INTEGER,
                plant_type TEXT,
                planted_date TEXT,
                last_watered TEXT,
                growth_stage INTEGER DEFAULT 0,
                water_days INTEGER DEFAULT 1,
                total_days INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, plant_type)
            )
        """)

        # Table user_notifications
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_notifications (
                guild_id TEXT,
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                type TEXT,
                data TEXT,
                timestamp INTEGER,
                read BOOLEAN DEFAULT 0
            )
        """)

        # Table guild_settings
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                economy_enabled INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Tables Jules
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id TEXT PRIMARY KEY,
                welcome_channel_id TEXT,
                welcome_message TEXT,
                welcome_image_url TEXT,
                leave_channel_id TEXT,
                leave_message TEXT,
                captcha_channel_id TEXT,
                verified_role_id TEXT,
                ticket_category_id TEXT,
                support_role_ids TEXT DEFAULT '[]',
                voice_trigger_id TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS command_permissions (
                guild_id TEXT,
                command_name TEXT,
                role_id TEXT,
                PRIMARY KEY (guild_id, command_name, role_id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                guild_id TEXT, 
                user_id TEXT, 
                moderator_id TEXT, 
                reason TEXT, 
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id TEXT PRIMARY KEY, 
                guild_id TEXT, 
                user_id TEXT, 
                status TEXT DEFAULT 'open'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                creator_id TEXT,
                name TEXT,
                data BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

# ---- FONCTIONS UTILITAIRES ----
def execute_query(query: str, params: tuple = ()) -> None:
    with get_conn() as conn:
        conn.execute(query, params)

def fetch_one(query: str, params: tuple = ()) -> Optional[tuple]:
    with get_conn() as conn:
        return conn.execute(query, params).fetchone()

def fetch_all(query: str, params: tuple = ()) -> List[tuple]:
    with get_conn() as conn:
        return conn.execute(query, params).fetchall()

# ---- FONCTIONS UTILISATEURS ----
def user_init(guild_id: str, user_id: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO users (guild_id, user_id, wallet, bank) VALUES (?, ?, 0, 0)", (str(guild_id), str(user_id)))
        conn.execute("INSERT OR IGNORE INTO inventaire (guild_id, user_id, inventory) VALUES (?, ?, '{}')", (str(guild_id), str(user_id)))
        conn.execute("INSERT OR IGNORE INTO jobs (guild_id, user_id, current_job, knowledge, unlocked_jobs, work_count, last_work) VALUES (?, ?, 'livreur', 0, '[\"livreur\"]', 0, NULL)", (str(guild_id), str(user_id)))

def get_wallet_bank(guild_id: str, user_id: str) -> Dict[str, int]:
    result = fetch_one("SELECT wallet, bank FROM users WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
    return {"wallet": result[0], "bank": result[1]} if result else {"wallet": 0, "bank": 0}

def update_wallet(guild_id: str, user_id: str, amount: int) -> None:
    current = get_wallet_bank(guild_id, user_id)
    new_wallet = max(0, current["wallet"] + amount)
    execute_query("UPDATE users SET wallet = ? WHERE guild_id = ? AND user_id = ?", (new_wallet, str(guild_id), str(user_id)))

def update_bank(guild_id: str, user_id: str, amount: int) -> None:
    current = get_wallet_bank(guild_id, user_id)
    new_bank = max(0, current["bank"] + amount)
    execute_query("UPDATE users SET bank = ? WHERE guild_id = ? AND user_id = ?", (new_bank, str(guild_id), str(user_id)))

def get_all_users_with_balances(guild_id: str) -> List[tuple]:
    return fetch_all("SELECT user_id, wallet, bank FROM users WHERE guild_id = ?", (str(guild_id),))

# ---- FONCTIONS INVENTAIRE ----
def get_inventaire(guild_id: str, user_id: str) -> Dict:
    result = fetch_one("SELECT inventory FROM inventaire WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
    return json.loads(result[0]) if result and result[0] else {}

def update_inventaire(guild_id: str, user_id: str, inventory: Dict) -> None:
    execute_query("UPDATE inventaire SET inventory = ? WHERE guild_id = ? AND user_id = ?", (json.dumps(inventory), str(guild_id), str(user_id)))

# ---- FONCTIONS INVESTISSEMENTS ----
def get_investissements(guild_id: str, user_id: str) -> Dict:
    row = fetch_one("SELECT nom_invest, duration, reward, start, end FROM investissements WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
    if not row: return {}
    return {"nom_invest": row[0], "duration": row[1], "reward": row[2], "start": row[3], "end": row[4]}

def update_investissements(guild_id: str, user_id: str, invest_dict: Optional[Dict]) -> None:
    if not invest_dict:
        execute_query("DELETE FROM investissements WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
    else:
        execute_query("""
            INSERT INTO investissements (guild_id, user_id, nom_invest, duration, reward, start, end)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                nom_invest = excluded.nom_invest, duration = excluded.duration,
                reward = excluded.reward, start = excluded.start, end = excluded.end
        """, (str(guild_id), str(user_id), invest_dict["nom_invest"], invest_dict["duration"], invest_dict["reward"], invest_dict["start"], invest_dict["end"]))

# ---- FONCTIONS JOBS ----
def get_job_data(guild_id: str, user_id: str) -> Dict:
    result = fetch_one("SELECT current_job, knowledge, unlocked_jobs, work_count, last_work FROM jobs WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
    if result:
        current_job, knowledge, unlocked_jobs_json, work_count, last_work = result
        try: unlocked_jobs = json.loads(unlocked_jobs_json)
        except: unlocked_jobs = []
        return {"current_job": current_job, "knowledge": knowledge, "unlocked_jobs": unlocked_jobs, "work_count": work_count, "last_work": last_work}
    return {"current_job": "Livreur", "knowledge": 0, "unlocked_jobs": ["Livreur", "Agent de nettoyage", "Caissier"], "work_count": 0, "last_work": None}

def update_job(guild_id: str, user_id: str, key: str, value: Union[str, int, List]) -> None:
    if isinstance(value, list): value = json.dumps(value)
    execute_query(f"UPDATE jobs SET {key} = ? WHERE guild_id = ? AND user_id = ?", (value, str(guild_id), str(user_id)))

def get_work_cooldown(guild_id: str, user_id: str) -> Optional[str]:
    result = fetch_one("SELECT last_work FROM jobs WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
    return result[0] if result else None

def update_work_cooldown(guild_id: str, user_id: str, timestamp: str) -> None:
    execute_query("UPDATE jobs SET last_work = ? WHERE guild_id = ? AND user_id = ?", (timestamp, str(guild_id), str(user_id)))

# ---- FONCTIONS ENTREPRISES ----
def create_entreprise(guild_id: str, owner_id: str, nom: str) -> None:
    execute_query("INSERT OR REPLACE INTO entreprises (guild_id, owner_id, nom, tresorerie, tresorerie_max, nb_work_requis, nb_work_restants, revenu_par_cycle, visibilite) VALUES (?, ?, ?, 5000, 10000, 10, 10, 1000, 'prive')", (str(guild_id), str(owner_id), nom))

def get_entreprise(guild_id: str, owner_id: str) -> Optional[Dict]:
    row = fetch_one("SELECT nom, tresorerie, tresorerie_max, nb_work_requis, nb_work_restants, visibilite, revenu_par_cycle, last_rename FROM entreprises WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
    if not row: return None
    return {"nom": row[0], "tresorerie": row[1], "tresorerie_max": row[2], "nb_work_requis": row[3], "nb_work_restants": row[4], "visibilite": row[5], "revenu_par_cycle": row[6], "last_rename": row[7]}

def get_entreprise_by_name(guild_id: str, nom_entreprise: str) -> Optional[Dict]:
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM entreprises WHERE guild_id = ? AND nom = ?", (str(guild_id), nom_entreprise))
        row = cursor.fetchone()
        if row:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, row))
        return None

def update_entreprise_name(guild_id: str, owner_id: str, new_name: str, timestamp: Optional[str] = None) -> None:
    execute_query("UPDATE entreprises SET nom = ?, last_rename = ? WHERE guild_id = ? AND owner_id = ?", (new_name, timestamp, str(guild_id), str(owner_id)))

def update_entreprise_visibility(guild_id: str, owner_id: str, new_visibility: str) -> None:
    execute_query("UPDATE entreprises SET visibilite = ? WHERE guild_id = ? AND owner_id = ?", (new_visibility, str(guild_id), str(owner_id)))

def get_tresorerie_entreprise(guild_id: str, owner_id: str) -> int:
    result = fetch_one("SELECT tresorerie FROM entreprises WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
    return result[0] if result else 0

def update_tresorerie_entreprise(guild_id: str, owner_id: str, montant: int) -> None:
    execute_query("UPDATE entreprises SET tresorerie = ? WHERE guild_id = ? AND owner_id = ?", (montant, str(guild_id), str(owner_id)))

def set_entreprise_tresorerie(guild_id: str, owner_id: str, montant: int) -> None:
    update_tresorerie_entreprise(guild_id, owner_id, montant)

def get_work_restants(guild_id: str, owner_id: str) -> int:
    result = fetch_one("SELECT nb_work_restants FROM entreprises WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
    return result[0] if result else 0

def update_work_restants(guild_id: str, owner_id: str, reste: int) -> None:
    execute_query("UPDATE entreprises SET nb_work_restants = ? WHERE guild_id = ? AND owner_id = ?", (reste, str(guild_id), str(owner_id)))

def set_work_restants(guild_id: str, owner_id: str, reste: int) -> None:
    update_work_restants(guild_id, owner_id, reste)

def get_work_requis(guild_id: str, owner_id: str) -> int:
    result = fetch_one("SELECT nb_work_requis FROM entreprises WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
    return result[0] if result else 0

def get_revenu_par_cycle(guild_id: str, owner_id: str) -> int:
    result = fetch_one("SELECT revenu_par_cycle FROM entreprises WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
    return result[0] if result else 0

def withdraw_entreprise_money(guild_id: str, owner_id: str, amount: int) -> bool:
    treso = get_tresorerie_entreprise(guild_id, owner_id)
    if treso >= amount:
        update_tresorerie_entreprise(guild_id, owner_id, treso - amount)
        update_bank(guild_id, owner_id, amount)
        return True
    return False

def delete_entreprise(guild_id: str, owner_id: str) -> None:
    gid, oid = str(guild_id), str(owner_id)
    execute_query("DELETE FROM entreprise_employes WHERE guild_id = ? AND entreprise_owner_id = ?", (gid, oid))
    execute_query("DELETE FROM entreprise_buildings WHERE guild_id = ? AND entreprise_owner_id = ?", (gid, oid))
    execute_query("DELETE FROM entreprises WHERE guild_id = ? AND owner_id = ?", (gid, oid))

def get_name_entreprise(guild_id: str, owner_id: str) -> str:
    result = fetch_one("SELECT nom FROM entreprises WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
    return result[0] if result else "Entreprise sans nom"

def get_name_change_cooldown(guild_id: str, owner_id: str) -> int:
    row = fetch_one("SELECT last_rename FROM entreprises WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
    if not row or not row[0]: return 0
    try:
        last_rename = datetime.fromisoformat(row[0])
        elapsed = (datetime.now() - last_rename).total_seconds()
        return max(0, int(24 * 3600 - elapsed))
    except: return 0

def get_all_entreprises_by_guild(guild_id: str) -> List[tuple]:
    return fetch_all("SELECT e.owner_id, e.nom, e.tresorerie, e.tresorerie_max, e.visibilite, e.revenu_par_cycle, (SELECT COUNT(*) FROM entreprise_employes em WHERE em.entreprise_owner_id = e.owner_id) as employee_count FROM entreprises e WHERE e.guild_id = ?", (str(guild_id),))

# ---- FONCTIONS EMPLOYES ----
def add_employe(guild_id: str, owner_id: str, employe_id: str, role: str = "Employé", salaire: int = 0) -> None:
    execute_query("INSERT OR REPLACE INTO entreprise_employes (guild_id, entreprise_owner_id, employe_id, role, salaire, nb_work_effectues) VALUES (?, ?, ?, ?, ?, 0)", (str(guild_id), str(owner_id), str(employe_id), role, salaire))

def remove_employe(guild_id: str, owner_id: str, employe_id: str) -> None:
    execute_query("DELETE FROM entreprise_employes WHERE guild_id = ? AND entreprise_owner_id = ? AND employe_id = ?", (str(guild_id), str(owner_id), str(employe_id)))

def get_employes(guild_id: str, owner_id: str) -> List[Dict]:
    rows = fetch_all("SELECT employe_id, role, salaire, nb_work_effectues FROM entreprise_employes WHERE guild_id = ? AND entreprise_owner_id = ?", (str(guild_id), str(owner_id)))
    return [{"employe_id": row[0], "role": row[1], "salaire": row[2], "nb_work_effectues": row[3]} for row in rows]

def get_employe(guild_id: str, owner_id: str, employe_id: str) -> Optional[Dict]:
    row = fetch_one("SELECT role, salaire, nb_work_effectues FROM entreprise_employes WHERE guild_id = ? AND entreprise_owner_id = ? AND employe_id = ?", (str(guild_id), str(owner_id), str(employe_id)))
    return {"role": row[0], "salaire": row[1], "nb_work_effectues": row[2]} if row else None

def update_employe_role(guild_id: str, owner_id: str, employe_id: str, role: str) -> None:
    execute_query("UPDATE entreprise_employes SET role = ? WHERE guild_id = ? AND entreprise_owner_id = ? AND employe_id = ?", (role, str(guild_id), str(owner_id), str(employe_id)))

def update_employe_salaire(guild_id: str, owner_id: str, employe_id: str, salaire: int) -> None:
    execute_query("UPDATE entreprise_employes SET salaire = ? WHERE guild_id = ? AND entreprise_owner_id = ? AND employe_id = ?", (salaire, str(guild_id), str(owner_id), str(employe_id)))

def increment_work_effectue(guild_id: str, user_id: str) -> None:
    with get_conn() as conn:
        result = conn.execute("SELECT entreprise_owner_id FROM entreprise_employes WHERE guild_id = ? AND employe_id = ?", (str(guild_id), str(user_id))).fetchone()
        if result:
            ent_id = result[0]
            conn.execute("UPDATE entreprise_employes SET nb_work_effectues = nb_work_effectues + 1 WHERE guild_id = ? AND entreprise_owner_id = ? AND employe_id = ?", (str(guild_id), ent_id, str(user_id)))
            conn.execute("UPDATE entreprises SET nb_work_restants = nb_work_restants - 1 WHERE guild_id = ? AND owner_id = ?", (str(guild_id), ent_id))

def is_employe(guild_id: str, user_id: str) -> bool:
    return fetch_one("SELECT 1 FROM entreprise_employes WHERE guild_id = ? AND employe_id = ? LIMIT 1", (str(guild_id), str(user_id))) is not None

def is_entreprise_owner(guild_id: str, user_id: str) -> bool:
    return fetch_one("SELECT 1 FROM entreprises WHERE guild_id = ? AND owner_id = ? LIMIT 1", (str(guild_id), str(user_id))) is not None

def get_entreprise_owner_id(guild_id: str, user_id: str) -> Optional[str]:
    result = fetch_one("SELECT entreprise_owner_id FROM entreprise_employes WHERE guild_id = ? AND employe_id = ?", (str(guild_id), str(user_id)))
    return result[0] if result else None

def has_permission(guild_id: str, user_id: str, permission: str) -> bool:
    if is_entreprise_owner(guild_id, user_id): return True
    owner_id = get_entreprise_owner_id(guild_id, user_id)
    if not owner_id: return False
    emp = get_employe(guild_id, owner_id, user_id)
    if not emp: return False
    role_info = EMPLOYEE_ROLES.get(emp["role"].lower())
    return permission in role_info["permissions"] if role_info else False

# ---- FONCTIONS BÂTIMENTS ----
def add_building(guild_id: str, owner_id: str, building_type: str) -> bool:
    if building_type not in BUILDING_TYPES: return False
    rows = fetch_all("SELECT building_id FROM entreprise_buildings WHERE guild_id = ? AND entreprise_owner_id = ?", (str(guild_id), str(owner_id)))
    next_id = max([r[0] for r in rows] + [0]) + 1
    execute_query("INSERT INTO entreprise_buildings (guild_id, entreprise_owner_id, building_type, level, last_maintenance, building_id) VALUES (?, ?, ?, 1, ?, ?)", (str(guild_id), str(owner_id), building_type, datetime.now().isoformat(), next_id))
    update_max_tresorerie(guild_id, owner_id)
    return True

def upgrade_building(guild_id: str, owner_id: str, building_id: int) -> bool:
    execute_query("UPDATE entreprise_buildings SET level = level + 1 WHERE guild_id = ? AND entreprise_owner_id = ? AND building_id = ?", (str(guild_id), str(owner_id), building_id))
    update_max_tresorerie(guild_id, owner_id)
    return True

def get_entreprise_buildings(guild_id: str, owner_id: str) -> List[Dict]:
    rows = fetch_all("SELECT building_type, level, last_maintenance, building_id FROM entreprise_buildings WHERE guild_id = ? AND entreprise_owner_id = ? ORDER BY building_id ASC", (str(guild_id), str(owner_id)))
    buildings = []
    for row in rows:
        b_type, level, last_m, b_id = row
        if b_type in BUILDING_TYPES:
            info = BUILDING_TYPES[b_type].copy()
            info.update({"building_type": b_type, "level": level, "last_maintenance": last_m, "building_id": b_id})
            buildings.append(info)
    return buildings

def update_max_tresorerie(guild_id: str, owner_id: str) -> None:
    buildings = get_entreprise_buildings(guild_id, owner_id)
    total = 10000 + sum(BUILDING_TYPES[b["building_type"]]["storage_bonus"] * b["level"] for b in buildings if b["building_type"] in BUILDING_TYPES)
    execute_query("UPDATE entreprises SET tresorerie_max = ? WHERE guild_id = ? AND owner_id = ?", (total, str(guild_id), str(owner_id)))

def reorganize_building_ids(guild_id: str, owner_id: str) -> None:
    buildings = fetch_all("SELECT building_type, level, last_maintenance FROM entreprise_buildings WHERE guild_id = ? AND entreprise_owner_id = ? ORDER BY building_id ASC", (str(guild_id), str(owner_id)))
    execute_query("DELETE FROM entreprise_buildings WHERE guild_id = ? AND entreprise_owner_id = ?", (str(guild_id), str(owner_id)))
    for i, (b_type, level, last_m) in enumerate(buildings, 1):
        execute_query("INSERT INTO entreprise_buildings (guild_id, entreprise_owner_id, building_type, level, last_maintenance, building_id) VALUES (?, ?, ?, ?, ?, ?)", (str(guild_id), str(owner_id), b_type, level, last_m, i))

def get_building_upgrade_cost(guild_id: str, owner_id: str, building_id: int) -> int:
    row = fetch_one("SELECT building_type, level FROM entreprise_buildings WHERE guild_id = ? AND entreprise_owner_id = ? AND building_id = ?", (str(guild_id), str(owner_id), building_id))
    if not row: return 0
    b_type, level = row
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
    return fetch_all("SELECT * FROM marketplace_listings WHERE status = 'active' AND expires_at > ?", (datetime.now().timestamp(),))

def cancel_marketplace_listing(guild_id: str, listing_id: int, seller_id: str) -> bool:
    execute_query("UPDATE marketplace_listings SET status = 'cancelled' WHERE guild_id = ? AND listing_id = ? AND seller_id = ?", (str(guild_id), listing_id, str(seller_id)))
    return True

# ---- FONCTIONS PLANTES ----
def get_user_plants(user_id: int):
    return fetch_all("SELECT plant_type, planted_date, last_watered, growth_stage, water_days, total_days FROM user_plants WHERE user_id = ?", (user_id,))

def manage_plant(user_id: int, action: str, plant_type: str = None, **kwargs) -> tuple[bool, str]:
    try:
        if action == "add":
            execute_query("INSERT INTO user_plants (user_id, plant_type, planted_date, last_watered, growth_stage, water_days, total_days) VALUES (?, ?, ?, ?, 0, ?, ?)", (user_id, plant_type, kwargs['planted_date'], kwargs['last_watered'], kwargs['water_days'], kwargs['total_days']))
            return True, "Plante ajoutée."
        elif action == "water":
            execute_query("UPDATE user_plants SET last_watered = ?, growth_stage = ? WHERE user_id = ? AND plant_type = ?", (kwargs['new_water_date'], kwargs['new_growth_stage'], user_id, plant_type))
            return True, "Plante arrosée."
        elif action == "delete":
            execute_query("DELETE FROM user_plants WHERE user_id = ? AND plant_type = ?", (user_id, plant_type))
            return True, "Plante supprimée."
        return False, "Action inconnue."
    except Exception as e: return False, str(e)

# ---- FONCTIONS JULES ----
def get_config(guild_id: int):
    row = fetch_one("SELECT * FROM guild_config WHERE guild_id = ?", (str(guild_id),))
    if row:
        with get_conn() as conn:
            cursor = conn.execute("PRAGMA table_info(guild_config)")
            cols = [c[1] for c in cursor.fetchall()]
        config = {}
        for i, col in enumerate(cols):
            val = row[i]
            if col == "support_role_ids": config[col] = json.loads(val) if val else []
            elif col.endswith("_id") and val: config[col] = int(val)
            else: config[col] = val
        return config
    return None

def update_config(guild_id: int, **kwargs):
    if not fetch_one("SELECT 1 FROM guild_config WHERE guild_id = ?", (str(guild_id),)):
        execute_query("INSERT INTO guild_config (guild_id) VALUES (?)", (str(guild_id),))
    for key, value in kwargs.items():
        execute_query(f"UPDATE guild_config SET {key} = ? WHERE guild_id = ?", (str(value) if value is not None else None, str(guild_id)))

def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str):
    execute_query("INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)", (str(guild_id), str(user_id), str(moderator_id), reason))

def get_warnings(guild_id: int, user_id: int):
    return fetch_all("SELECT moderator_id, reason, timestamp FROM warnings WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))

def clear_warnings(guild_id: int, user_id: int):
    execute_query("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))

def create_ticket(channel_id: int, guild_id: int, user_id: int):
    execute_query("INSERT INTO tickets (channel_id, guild_id, user_id) VALUES (?, ?, ?)", (str(channel_id), str(guild_id), str(user_id)))

def close_ticket(channel_id: int):
    execute_query("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (str(channel_id),))

def has_open_ticket(guild_id: int, user_id: int) -> bool:
    return fetch_one("SELECT 1 FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'", (str(guild_id), str(user_id))) is not None

# ---- PERMISSIONS DE COMMANDES ----
def add_command_permission(guild_id: str, command_name: str, role_id: str) -> None:
    execute_query("INSERT OR IGNORE INTO command_permissions (guild_id, command_name, role_id) VALUES (?, ?, ?)", (str(guild_id), command_name, str(role_id)))

def remove_command_permission(guild_id: str, command_name: str, role_id: str) -> None:
    execute_query("DELETE FROM command_permissions WHERE guild_id = ? AND command_name = ? AND role_id = ?", (str(guild_id), command_name, str(role_id)))

def get_command_permissions(guild_id: str, command_name: str) -> List[str]:
    rows = fetch_all("SELECT role_id FROM command_permissions WHERE guild_id = ? AND command_name = ?", (str(guild_id), command_name))
    return [r[0] for r in rows]

# ---- ECONOMIE ----
def set_economy_enabled(guild_id: str, enabled: bool) -> None:
    execute_query("INSERT OR REPLACE INTO guild_settings (guild_id, economy_enabled) VALUES (?, ?)", (str(guild_id), 1 if enabled else 0))

def is_economy_enabled(guild_id: str) -> bool:
    row = fetch_one("SELECT economy_enabled FROM guild_settings WHERE guild_id = ?", (str(guild_id),))
    return bool(row[0]) if row else True

def reset_guild_economy(guild_id: str) -> None:
    gid = str(guild_id)
    with get_conn() as conn:
        conn.execute("DELETE FROM entreprise_employes WHERE guild_id = ?", (gid,))
        conn.execute("DELETE FROM entreprise_buildings WHERE guild_id = ?", (gid,))
        conn.execute("DELETE FROM marketplace_listings WHERE guild_id = ?", (gid,))
        conn.execute("DELETE FROM investissements WHERE guild_id = ?", (gid,))
        conn.execute("DELETE FROM jobs WHERE guild_id = ?", (gid,))
        conn.execute("DELETE FROM inventaire WHERE guild_id = ?", (gid,))
        conn.execute("DELETE FROM garden WHERE guild_id = ?", (gid,))
        conn.execute("DELETE FROM entreprises WHERE guild_id = ?", (gid,))
        conn.execute("DELETE FROM users WHERE guild_id = ?", (gid,))

def get_unread_notifications_count(user_id: int) -> int:
    result = fetch_one("SELECT COUNT(*) FROM user_notifications WHERE user_id = ? AND read = 0", (str(user_id),))
    return result[0] if result else 0

# ---- BACKUPS ----
def save_db_backup(guild_id: str, creator_id: str, name: str, data: bytes) -> None:
    execute_query("INSERT INTO backups (guild_id, creator_id, name, data) VALUES (?, ?, ?, ?)", (str(guild_id), str(creator_id), name, data))

def get_user_backups(creator_id: str) -> List[tuple]:
    return fetch_all("SELECT id, name, created_at, guild_id FROM backups WHERE creator_id = ? ORDER BY created_at DESC", (str(creator_id),))

def get_backup_data(backup_id: int) -> Optional[bytes]:
    row = fetch_one("SELECT data FROM backups WHERE id = ?", (backup_id,))
    return row[0] if row else None

def delete_db_backup(backup_id: int, creator_id: str) -> bool:
    # On vérifie que c'est bien le créateur qui supprime
    row = fetch_one("SELECT 1 FROM backups WHERE id = ? AND creator_id = ?", (backup_id, str(creator_id)))
    if row:
        execute_query("DELETE FROM backups WHERE id = ?", (backup_id,))
        return True
    return False

def update_db_structure():
    """Migre la base de données pour ajouter les colonnes manquantes si nécessaire"""
    with get_conn() as conn:
        # Colonnes pour le message de départ
        try:
            conn.execute("ALTER TABLE guild_config ADD COLUMN leave_channel_id TEXT")
        except sqlite3.OperationalError: pass
        
        try:
            conn.execute("ALTER TABLE guild_config ADD COLUMN leave_message TEXT")
        except sqlite3.OperationalError: pass

init_db()
update_db_structure()
