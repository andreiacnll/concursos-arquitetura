import json
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "concursos.db"

ESTADOS_ANALISE = (
    "aguarda",
    "extracao",
    "processamento",
    "geracao",
    "concluida",
    "cancelada",
    "erro",
)

ESTADOS_ANALISE_ATIVOS = (
    "aguarda",
    "extracao",
    "processamento",
    "geracao",
)

COLUNAS_ANALISE = {
    "estado": "TEXT NOT NULL DEFAULT 'concluida'",
    "progresso": "INTEGER NOT NULL DEFAULT 100",
    "score": "INTEGER",
    "ficheiro_ficha": "TEXT",
    "user_id": "TEXT",
    "job_id": "INTEGER",
    # O SQLite não aceita CURRENT_TIMESTAMP ao acrescentar uma coluna.
    "updated_at": "TEXT",
}

COLUNAS_ALERTA = {
    "origem_evento": "TEXT NOT NULL DEFAULT 'workflow_concursos'",
    "analise_job_id": "INTEGER",
    "documento_anterior": "TEXT",
    "documento_novo": "TEXT",
    "hash_anterior": "TEXT",
    "hash_novo": "TEXT",
}

COLUNAS_ANALISE_VERSAO = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "analise_id": "INTEGER NOT NULL",
    "user_id": "TEXT",
    "concurso_id": "INTEGER NOT NULL",
    "dados_json": "TEXT",
    "score": "INTEGER",
    "ficheiro_ficha": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

TIPOS_ALERTA_RELEVANTES = {
    "novo_documento",
    "alteracao_economica",
    "alteracao_programa",
    "alteracao_criterio",
}


COLUNAS_ADICIONAIS = {
    "data_limite": "TEXT",
    "data_esclarecimentos": "TEXT",
    "preco_base": "TEXT",
    "cpv": "TEXT",
    "tipo_procedimento": "TEXT",
    "criterio_tipo": "TEXT",
    "criterio_resumo": "TEXT",
    "criterio_detalhe": "TEXT",
    "entregaveis": "TEXT",
    "link_anuncio_dr": "TEXT",
    "link_pecas": "TEXT",
    "data_entrega_propostas": "TEXT",
    "municipio": "TEXT",
    "freguesia": "TEXT",
    "morada": "TEXT",
    "codigo_postal": "TEXT",
    "latitude": "REAL",
    "longitude": "REAL",
    "localizacao_contexto": "TEXT",
}


def abrir_conexao() -> sqlite3.Connection:
    """Abre a base principal com as garantias usadas pela API."""
    conexao = sqlite3.connect(DB_PATH, timeout=5)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA busy_timeout = 5000")
    return conexao


def _adicionar_colunas_em_falta(cursor):
    """
    Acrescenta novas colunas à tabela sem apagar
    os concursos que já existem.
    """
    cursor.execute(
        """
        PRAGMA table_info(concursos)
        """
    )

    colunas_existentes = {
        linha[1]
        for linha in cursor.fetchall()
    }

    for nome_coluna, tipo_coluna in (
        COLUNAS_ADICIONAIS.items()
    ):
        if nome_coluna in colunas_existentes:
            continue

        cursor.execute(
            f"""
            ALTER TABLE concursos
            ADD COLUMN {nome_coluna} {tipo_coluna}
            """
        )


def _adicionar_colunas_analise_em_falta(cursor):
    """Migra o registo legado de análises sem perder fichas existentes."""
    cursor.execute("PRAGMA table_info(analises)")
    colunas_existentes = {linha[1] for linha in cursor.fetchall()}

    for nome_coluna, definicao in COLUNAS_ANALISE.items():
        if nome_coluna not in colunas_existentes:
            cursor.execute(
                f"ALTER TABLE analises ADD COLUMN {nome_coluna} {definicao}"
            )


def _adicionar_colunas_alertas_em_falta(cursor):
    """Mantem a tabela pronta para eventos vindos do worker documental."""
    cursor.execute("PRAGMA table_info(alertas)")
    colunas_existentes = {linha[1] for linha in cursor.fetchall()}

    for nome_coluna, definicao in COLUNAS_ALERTA.items():
        if nome_coluna not in colunas_existentes:
            cursor.execute(
                f"ALTER TABLE alertas ADD COLUMN {nome_coluna} {definicao}"
            )


def _criar_tabela_versoes_analise(cursor):
    """Histórico simples das fichas substituídas por atualizações do utilizador."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analise_versoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analise_id INTEGER NOT NULL,
            user_id TEXT,
            concurso_id INTEGER NOT NULL,
            dados_json TEXT,
            score INTEGER,
            ficheiro_ficha TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(analise_id)
            REFERENCES analises(id)
            ON DELETE CASCADE
        )
        """
    )


def _criar_tabelas_company_ai(cursor):
    """Base SQLite para empresas, equipa e perfil AI da empresa."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            website TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(company_id, user_id),
            FOREIGN KEY(company_id)
            REFERENCES companies(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS companies_updated_at
        AFTER UPDATE ON companies
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE companies
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_members_company_id
        ON company_members(company_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_members_user_id
        ON company_members(user_id)
        """
    )


def _migrar_tabela_company_members(cursor):
    """Garante cascade entre companies e company_members sem perder dados."""
    definicao = cursor.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'company_members'
        """
    ).fetchone()

    if not definicao:
        return

    sql_tabela = definicao[0] or ""
    if "ON DELETE CASCADE" in sql_tabela:
        return

    cursor.execute("PRAGMA foreign_keys = OFF")

    try:
        cursor.execute("DROP TABLE IF EXISTS company_members_migrada")
        cursor.execute(
            """
            CREATE TABLE company_members_migrada (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(company_id, user_id),
                FOREIGN KEY(company_id)
                REFERENCES companies(id)
                ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO company_members_migrada (
                id,
                company_id,
                user_id,
                role,
                status,
                created_at
            )
            SELECT
                id,
                company_id,
                user_id,
                role,
                status,
                created_at
            FROM company_members
            """
        )

        cursor.execute("DROP TABLE company_members")
        cursor.execute(
            """
            ALTER TABLE company_members_migrada
            RENAME TO company_members
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_company_members_company_id
            ON company_members(company_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_company_members_user_id
            ON company_members(user_id)
            """
        )
    finally:
        cursor.execute("PRAGMA foreign_keys = ON")


def _criar_tabela_company_profiles(cursor):
    """Armazena o profile AI agregado por empresa."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER UNIQUE NOT NULL,
            profile_json TEXT NOT NULL,
            strategy_json TEXT,
            ai_memory_json TEXT,
            completion_score REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(company_id)
            REFERENCES companies(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS company_profiles_updated_at
        AFTER UPDATE ON company_profiles
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE company_profiles
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_profiles_company_id
        ON company_profiles(company_id)
        """
    )


def _criar_tabela_member_profiles(cursor):
    """Armazena a identidade profissional individual de cada membro."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS member_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER UNIQUE NOT NULL,
            identity_json TEXT NOT NULL,
            experience_json TEXT,
            competences_json TEXT,
            preferences_json TEXT,
            goals_json TEXT,
            visibility_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(member_id)
            REFERENCES company_members(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS member_profiles_updated_at
        AFTER UPDATE ON member_profiles
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE member_profiles
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_member_profiles_member_id
        ON member_profiles(member_id)
        """
    )


def _criar_tabelas_company_interview(cursor):
    """Persiste sessões, perguntas e respostas da entrevista da empresa."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_interview_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'completed', 'archived')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(company_id)
            REFERENCES companies(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS company_interview_sessions_updated_at
        AFTER UPDATE ON company_interview_sessions
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE company_interview_sessions
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_interview_sessions_company_id
        ON company_interview_sessions(company_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_interview_sessions_status
        ON company_interview_sessions(status)
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_interview_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            field TEXT NOT NULL,
            question TEXT NOT NULL,
            question_type TEXT,
            priority TEXT,
            options_json TEXT,
            question_source TEXT NOT NULL DEFAULT 'discovery',
            knowledge_fact_id INTEGER,
            source TEXT,
            evidence TEXT,
            confidence REAL DEFAULT 0,
            suggested_answer_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(session_id)
            REFERENCES company_interview_sessions(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_interview_questions_session_id
        ON company_interview_questions(session_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_interview_questions_field
        ON company_interview_questions(field)
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_interview_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL UNIQUE,
            answer_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(question_id)
            REFERENCES company_interview_questions(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_interview_answers_question_id
        ON company_interview_answers(question_id)
        """
    )


def _migrar_tabela_company_interview_questions(cursor):
    """Garante compatibilidade da tabela de perguntas com novas colunas."""
    cursor.execute("PRAGMA table_info(company_interview_questions)")
    colunas_existentes = {linha[1] for linha in cursor.fetchall()}

    if "question_source" not in colunas_existentes:
        cursor.execute(
            """
            ALTER TABLE company_interview_questions
            ADD COLUMN question_source TEXT NOT NULL DEFAULT 'discovery'
            """
        )

    if "knowledge_fact_id" not in colunas_existentes:
        cursor.execute(
            """
            ALTER TABLE company_interview_questions
            ADD COLUMN knowledge_fact_id INTEGER
            """
        )

    if "source" not in colunas_existentes:
        cursor.execute(
            """
            ALTER TABLE company_interview_questions
            ADD COLUMN source TEXT
            """
        )

    if "evidence" not in colunas_existentes:
        cursor.execute(
            """
            ALTER TABLE company_interview_questions
            ADD COLUMN evidence TEXT
            """
        )

    if "confidence" not in colunas_existentes:
        cursor.execute(
            """
            ALTER TABLE company_interview_questions
            ADD COLUMN confidence REAL DEFAULT 0
            """
        )

    if "suggested_answer_json" not in colunas_existentes:
        cursor.execute(
            """
            ALTER TABLE company_interview_questions
            ADD COLUMN suggested_answer_json TEXT
            """
        )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_interview_questions_source
        ON company_interview_questions(question_source)
        """
    )


def _criar_tabela_company_knowledge_memory(cursor):
    """Guarda factos empresariais com origem, confiança e estado."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_knowledge_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            field TEXT NOT NULL,
            value_json TEXT NOT NULL,
            source TEXT,
            source_type TEXT,
            url TEXT,
            section TEXT,
            evidence_text TEXT,
            confidence REAL DEFAULT 0,
            status TEXT DEFAULT 'unknown',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(company_id)
            REFERENCES companies(id)
            ON DELETE CASCADE
        )
        """
    )

    colunas = {
        linha[1]
        for linha in cursor.execute(
            "PRAGMA table_info(company_knowledge_memory)"
        ).fetchall()
    }
    if "url" not in colunas:
        cursor.execute("ALTER TABLE company_knowledge_memory ADD COLUMN url TEXT")
    if "section" not in colunas:
        cursor.execute("ALTER TABLE company_knowledge_memory ADD COLUMN section TEXT")
    if "evidence_text" not in colunas:
        cursor.execute(
            "ALTER TABLE company_knowledge_memory ADD COLUMN evidence_text TEXT"
        )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS company_knowledge_memory_updated_at
        AFTER UPDATE ON company_knowledge_memory
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE company_knowledge_memory
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_knowledge_memory_company_id
        ON company_knowledge_memory(company_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_knowledge_memory_field
        ON company_knowledge_memory(company_id, field)
        """
    )


def _criar_tabela_company_source_raw_texts(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_source_raw_texts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            source_type TEXT,
            url TEXT,
            raw_text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(company_id)
            REFERENCES companies(id)
            ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_company_source_raw_unique
        ON company_source_raw_texts(company_id, source)
        """
    )


def _migrar_tabela_analises(cursor):
    """Permite uma análise por utilizador sem tocar nas fichas legadas."""
    definicao = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'analises'"
    ).fetchone()
    if not definicao or "concurso_id INTEGER UNIQUE" not in (definicao[0] or ""):
        return

    cursor.execute("ALTER TABLE analises RENAME TO analises_legado")
    cursor.execute(
        """
        CREATE TABLE analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            job_id INTEGER,
            concurso_id INTEGER NOT NULL,
            nivel TEXT,
            resumo TEXT,
            dados_json TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            estado TEXT NOT NULL DEFAULT 'concluida',
            progresso INTEGER NOT NULL DEFAULT 100,
            score INTEGER,
            ficheiro_ficha TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO analises (
            id, user_id, job_id, concurso_id, nivel, resumo,
            dados_json, criado_em, estado, progresso, score,
            ficheiro_ficha, updated_at
        )
        SELECT
            id, user_id, job_id, concurso_id, nivel, resumo,
            dados_json, criado_em, estado, progresso, score,
            ficheiro_ficha, updated_at
        FROM analises_legado
        """
    )
    cursor.execute("DROP TABLE analises_legado")


def _migrar_estados_analise_jobs(cursor, estados_sql: str):
    """Acrescenta o estado cancelada ao CHECK dos jobs existentes."""
    definicao = cursor.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'analise_jobs'"
    ).fetchone()
    if not definicao or "cancelada" in (definicao[0] or ""):
        return

    cursor.execute("ALTER TABLE analise_jobs RENAME TO analise_jobs_legado")
    cursor.execute(
        f"""
        CREATE TABLE analise_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            concurso_id INTEGER NOT NULL,
            estado TEXT NOT NULL DEFAULT 'aguarda'
                CHECK (estado IN ({estados_sql})),
            progresso INTEGER NOT NULL DEFAULT 0
                CHECK (progresso BETWEEN 0 AND 100),
            erro TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, concurso_id),
            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
            ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO analise_jobs (
            id, user_id, concurso_id, estado, progresso,
            erro, created_at, updated_at
        )
        SELECT
            id, user_id, concurso_id, estado, progresso,
            erro, created_at, updated_at
        FROM analise_jobs_legado
        """
    )
    cursor.execute("DROP TABLE analise_jobs_legado")


def _id_portal_base(link: str | None):
    if not link:
        return None

    correspondencia = re.search(r"[?&]id=(\d+)", link)
    return correspondencia.group(1) if correspondencia else None


def _extrair_score(ficha: dict):
    candidatos = (
        ficha.get("analise_ai", {}).get("score"),
        ficha.get("decisao", {}).get("score"),
        ficha.get("score"),
    )

    for candidato in candidatos:
        if isinstance(candidato, dict):
            candidato = candidato.get("valor")
        try:
            return max(0, min(100, int(float(candidato))))
        except (TypeError, ValueError):
            continue
    return None


def _sincronizar_fichas_existentes(cursor):
    """Regista as fichas reais do repositório no histórico durável."""
    raiz_fichas = BASE_DIR / "analise_documentos"
    if not raiz_fichas.is_dir():
        return

    concursos = cursor.execute(
        "SELECT id, titulo, link FROM concursos"
    ).fetchall()
    concursos_por_portal = {
        portal_id: concurso
        for concurso in concursos
        if (portal_id := _id_portal_base(concurso["link"]))
    }

    for caminho_ficha in raiz_fichas.glob("*/ficha.json"):
        concurso = concursos_por_portal.get(caminho_ficha.parent.name)
        if concurso is None:
            continue

        try:
            ficha = json.loads(caminho_ficha.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue

        if ficha.get("identificacao", {}).get("job_id"):
            continue

        caminho_relativo = caminho_ficha.relative_to(BASE_DIR).as_posix()
        score = _extrair_score(ficha)
        resumo = (
            ficha.get("analise_ai", {}).get("recomendacao")
            or ficha.get("decisao", {}).get("classificacao")
            or concurso["titulo"]
        )

        parametros = (
            resumo,
            json.dumps(ficha, ensure_ascii=False),
            score,
            caminho_relativo,
            concurso["id"],
        )
        atualizado = cursor.execute(
            """
            UPDATE analises
            SET nivel = 'AI', resumo = ?, dados_json = ?,
                estado = 'concluida', progresso = 100, score = ?,
                ficheiro_ficha = ?, updated_at = CURRENT_TIMESTAMP
            WHERE concurso_id = ? AND user_id IS NULL
            """,
            parametros,
        ).rowcount

        if not atualizado:
            cursor.execute(
                """
                INSERT INTO analises (
                    user_id, concurso_id, nivel, resumo, dados_json,
                    estado, progresso, score, ficheiro_ficha
                )
                VALUES (NULL, ?, 'AI', ?, ?, 'concluida', 100, ?, ?)
                """,
                (
                    concurso["id"],
                    resumo,
                    json.dumps(ficha, ensure_ascii=False),
                    score,
                    caminho_relativo,
                ),
            )


def _limpar_analises_sistema_de_jobs(cursor):
    """Remove falsas análises base criadas a partir de fichas de jobs."""
    cursor.execute(
        """
        DELETE FROM analises
        WHERE user_id IS NULL
          AND ficheiro_ficha IS NOT NULL
          AND ficheiro_ficha IN (
              SELECT ficheiro_ficha
              FROM analises
              WHERE user_id IS NOT NULL
                AND ficheiro_ficha IS NOT NULL
          )
        """
    )


def criar_base_dados():
    """
    Cria a base de dados e a tabela de concursos.

    Se a tabela já existir, acrescenta automaticamente
    as colunas novas sem apagar os dados existentes.
    """
    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS concursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            entidade TEXT,
            link TEXT NOT NULL UNIQUE,
            data TEXT,
            relevante INTEGER DEFAULT 1,
            data_limite TEXT,
            preco_base TEXT,
            cpv TEXT,
            tipo_procedimento TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS timeline_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concurso_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            data TEXT,
            estado TEXT,
            origem TEXT,

            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            job_id INTEGER,
            concurso_id INTEGER NOT NULL,
            nivel TEXT,
            resumo TEXT,
            dados_json TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            estado TEXT NOT NULL DEFAULT 'concluida',
            progresso INTEGER NOT NULL DEFAULT 100,
            score INTEGER,
            ficheiro_ficha TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS favoritos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            concurso_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, concurso_id),
            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
            ON DELETE CASCADE
        )
        """
    )

    estados_sql = ", ".join(
        f"'{estado}'"
        for estado in ESTADOS_ANALISE
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS analise_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            concurso_id INTEGER NOT NULL,
            estado TEXT NOT NULL DEFAULT 'aguarda'
                CHECK (estado IN ({estados_sql})),
            progresso INTEGER NOT NULL DEFAULT 0
                CHECK (progresso BETWEEN 0 AND 100),
            erro TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, concurso_id),
            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alerta_subscricoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            concurso_id INTEGER NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            origem TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, concurso_id),
            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
            ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            concurso_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT,
            dados_extraidos TEXT,
            documento_origem TEXT,
            documento_anterior TEXT,
            documento_novo TEXT,
            hash_anterior TEXT,
            hash_novo TEXT,
            link TEXT,
            data_deteccao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            estado TEXT NOT NULL DEFAULT 'novo',
            relevante INTEGER NOT NULL DEFAULT 0,
            origem_evento TEXT NOT NULL DEFAULT 'workflow_concursos',
            analise_job_id INTEGER,
            fingerprint TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, concurso_id, fingerprint),
            FOREIGN KEY(concurso_id)
            REFERENCES concursos(id)
            ON DELETE CASCADE
        )
        """
    )

    _migrar_estados_analise_jobs(cursor, estados_sql)
    _adicionar_colunas_em_falta(cursor)
    _adicionar_colunas_analise_em_falta(cursor)
    _migrar_tabela_analises(cursor)
    _adicionar_colunas_alertas_em_falta(cursor)
    _criar_tabela_versoes_analise(cursor)
    _criar_tabelas_company_ai(cursor)
    _migrar_tabela_company_members(cursor)
    _criar_tabela_company_profiles(cursor)
    _criar_tabela_member_profiles(cursor)
    _criar_tabelas_company_interview(cursor)
    _migrar_tabela_company_interview_questions(cursor)
    _criar_tabela_company_knowledge_memory(cursor)
    _criar_tabela_company_source_raw_texts(cursor)

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_favoritos_user_id
        ON favoritos(user_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analise_jobs_user_id
        ON analise_jobs(user_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analise_jobs_estado
        ON analise_jobs(estado, created_at)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alerta_subscricoes_user_id
        ON alerta_subscricoes(user_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alerta_subscricoes_concurso_id
        ON alerta_subscricoes(concurso_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alertas_user_id
        ON alertas(user_id, estado, data_deteccao)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alertas_concurso_id
        ON alertas(concurso_id)
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analises_legado_concurso
        ON analises(concurso_id)
        WHERE user_id IS NULL
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analises_user_concurso
        ON analises(user_id, concurso_id)
        WHERE user_id IS NOT NULL
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analises_job_id
        ON analises(job_id)
        WHERE job_id IS NOT NULL
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analise_versoes_analise_id
        ON analise_versoes(analise_id, created_at)
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS analise_jobs_updated_at
        AFTER UPDATE ON analise_jobs
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE analise_jobs
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )

    cursor.execute(
        """
        UPDATE analises
        SET updated_at = COALESCE(updated_at, criado_em, CURRENT_TIMESTAMP)
        WHERE updated_at IS NULL
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS alerta_subscricoes_updated_at
        AFTER UPDATE ON alerta_subscricoes
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE alerta_subscricoes
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )

    cursor.execute(
        """
        CREATE TRIGGER IF NOT EXISTS alertas_updated_at
        AFTER UPDATE ON alertas
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE alertas
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END
        """
    )

    cursor.execute(
        """
        UPDATE analise_jobs
        SET estado = 'aguarda', progresso = 0
        WHERE estado IN ('extracao', 'processamento', 'geracao')
          AND id NOT IN (
              SELECT id
              FROM analise_jobs
              WHERE estado IN ('extracao', 'processamento', 'geracao')
              ORDER BY updated_at ASC, id ASC
              LIMIT 1
          )
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analise_jobs_um_ativo
        ON analise_jobs((1))
        WHERE estado IN ('extracao', 'processamento', 'geracao')
        """
    )

    _limpar_analises_sistema_de_jobs(cursor)
    _sincronizar_fichas_existentes(cursor)

    conn.commit()
    conn.close()


def concurso_por_id(concurso_id: int):
    """Obtém um concurso pelo identificador canónico da BD."""
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT *
            FROM concursos
            WHERE id = ?
            """,
            (concurso_id,),
        ).fetchone()

    return dict(linha) if linha else None


def atualizar_localizacao_concurso(
    concurso_id: int,
    localizacao: dict,
) -> bool:
    """Guarda localização verificada sem substituir dados bons por vazio."""
    if not concurso_id or not localizacao:
        return False

    campos = {
        "municipio": _texto_ou_none(localizacao.get("municipio")),
        "freguesia": _texto_ou_none(localizacao.get("freguesia")),
        "morada": _texto_ou_none(localizacao.get("morada")),
        "codigo_postal": _texto_ou_none(localizacao.get("codigo_postal")),
        "latitude": localizacao.get("latitude"),
        "longitude": localizacao.get("longitude"),
        "localizacao_contexto": _texto_ou_none(
            localizacao.get("contexto_urbano")
        ),
    }

    if not any(valor is not None for valor in campos.values()):
        return False

    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            UPDATE concursos
            SET
                municipio = COALESCE(?, municipio),
                freguesia = COALESCE(?, freguesia),
                morada = COALESCE(?, morada),
                codigo_postal = COALESCE(?, codigo_postal),
                latitude = COALESCE(?, latitude),
                longitude = COALESCE(?, longitude),
                localizacao_contexto = COALESCE(
                    ?,
                    localizacao_contexto
                )
            WHERE id = ?
            """,
            (
                campos["municipio"],
                campos["freguesia"],
                campos["morada"],
                campos["codigo_postal"],
                campos["latitude"],
                campos["longitude"],
                campos["localizacao_contexto"],
                concurso_id,
            ),
        )
        conexao.commit()
        return cursor.rowcount > 0


def listar_favoritos_utilizador(user_id: str):
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT
                f.id,
                f.user_id,
                f.concurso_id,
                f.created_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.preco_base,
                c.data_limite,
                c.tipo_procedimento
            FROM favoritos AS f
            JOIN concursos AS c
              ON c.id = f.concurso_id
            WHERE f.user_id = ?
            ORDER BY f.created_at DESC, f.id DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(linha) for linha in linhas]


def criar_ou_obter_favorito(
    user_id: str,
    concurso_id: int,
):
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            INSERT OR IGNORE INTO favoritos (
                user_id,
                concurso_id
            )
            VALUES (?, ?)
            """,
            (user_id, concurso_id),
        )
        criado = cursor.rowcount == 1

        linha = conexao.execute(
            """
            SELECT
                f.id,
                f.user_id,
                f.concurso_id,
                f.created_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.preco_base,
                c.data_limite,
                c.tipo_procedimento
            FROM favoritos AS f
            JOIN concursos AS c
              ON c.id = f.concurso_id
            WHERE f.user_id = ?
              AND f.concurso_id = ?
            """,
            (user_id, concurso_id),
        ).fetchone()

        conexao.commit()

    return dict(linha), criado


def remover_favorito(
    user_id: str,
    concurso_id: int,
) -> bool:
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            DELETE FROM favoritos
            WHERE user_id = ?
              AND concurso_id = ?
            """,
            (user_id, concurso_id),
        )
        conexao.commit()
        return cursor.rowcount > 0


def _normalizar_alerta(valor):
    if valor is None:
        return ""
    return " ".join(str(valor).strip().split())


def _serializar_dados_alerta(dados: dict | None) -> str:
    return json.dumps(dados or {}, ensure_ascii=False)


def _criar_alerta(
    conexao,
    *,
    user_id: str,
    concurso_id: int,
    tipo: str,
    titulo: str,
    descricao: str | None,
    dados_extraidos: dict | None,
    documento_origem: str | None,
    link: str | None,
    fingerprint: str,
    relevante: bool = False,
    origem_evento: str = "workflow_concursos",
    analise_job_id: int | None = None,
    documento_anterior: str | None = None,
    documento_novo: str | None = None,
    hash_anterior: str | None = None,
    hash_novo: str | None = None,
):
    conexao.execute(
        """
        INSERT OR IGNORE INTO alertas (
            user_id,
            concurso_id,
            tipo,
            titulo,
            descricao,
            dados_extraidos,
            documento_origem,
            documento_anterior,
            documento_novo,
            hash_anterior,
            hash_novo,
            link,
            estado,
            relevante,
            origem_evento,
            analise_job_id,
            fingerprint
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'novo', ?, ?, ?, ?)
        """,
        (
            user_id,
            concurso_id,
            tipo,
            titulo,
            descricao,
            _serializar_dados_alerta(dados_extraidos),
            documento_origem,
            documento_anterior,
            documento_novo,
            hash_anterior,
            hash_novo,
            link,
            1 if relevante else 0,
            origem_evento,
            analise_job_id,
            fingerprint,
        ),
    )


def _utilizadores_monitorizar_concurso(
    conexao,
    concurso_id: int,
) -> list[str]:
    linhas = conexao.execute(
        """
        SELECT user_id
        FROM favoritos
        WHERE concurso_id = ?

        UNION

        SELECT user_id
        FROM analises
        WHERE concurso_id = ?
          AND user_id IS NOT NULL

        UNION

        SELECT user_id
        FROM analise_jobs
        WHERE concurso_id = ?

        UNION

        SELECT user_id
        FROM alerta_subscricoes
        WHERE concurso_id = ?
          AND ativo = 1
        """,
        (concurso_id, concurso_id, concurso_id, concurso_id),
    ).fetchall()

    utilizadores = [linha["user_id"] for linha in linhas]
    if not utilizadores:
        return []

    desativados = conexao.execute(
        """
        SELECT user_id
        FROM alerta_subscricoes
        WHERE concurso_id = ?
          AND ativo = 0
        """,
        (concurso_id,),
    ).fetchall()
    bloqueados = {linha["user_id"] for linha in desativados}
    return [
        user_id
        for user_id in utilizadores
        if user_id not in bloqueados
    ]


def ativar_alertas_concurso(
    user_id: str,
    concurso_id: int,
    origem: str = "manual",
):
    with closing(abrir_conexao()) as conexao:
        conexao.execute(
            """
            INSERT INTO alerta_subscricoes (
                user_id,
                concurso_id,
                ativo,
                origem
            )
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, concurso_id)
            DO UPDATE SET
                ativo = 1,
                origem = excluded.origem
            """,
            (user_id, concurso_id, origem),
        )
        linha = conexao.execute(
            """
            SELECT
                s.id,
                s.user_id,
                s.concurso_id,
                s.ativo,
                s.origem,
                s.created_at,
                s.updated_at,
                c.titulo,
                c.entidade,
                c.link
            FROM alerta_subscricoes AS s
            JOIN concursos AS c
              ON c.id = s.concurso_id
            WHERE s.user_id = ?
              AND s.concurso_id = ?
            """,
            (user_id, concurso_id),
        ).fetchone()
        conexao.commit()
    return dict(linha) if linha else None


def desativar_alertas_concurso(
    user_id: str,
    concurso_id: int,
):
    with closing(abrir_conexao()) as conexao:
        conexao.execute(
            """
            INSERT INTO alerta_subscricoes (
                user_id,
                concurso_id,
                ativo,
                origem
            )
            VALUES (?, ?, 0, 'manual')
            ON CONFLICT(user_id, concurso_id)
            DO UPDATE SET
                ativo = 0,
                origem = 'manual'
            """,
            (user_id, concurso_id),
        )
        linha = conexao.execute(
            """
            SELECT *
            FROM alerta_subscricoes
            WHERE user_id = ?
              AND concurso_id = ?
            """,
            (user_id, concurso_id),
        ).fetchone()
        conexao.commit()
    return dict(linha) if linha else None


def obter_alertas_concurso_utilizador(
    user_id: str,
    concurso_id: int,
):
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT
                s.id,
                s.user_id,
                s.concurso_id,
                s.ativo,
                s.origem,
                s.created_at,
                s.updated_at,
                EXISTS (
                    SELECT 1 FROM favoritos AS f
                    WHERE f.user_id = s.user_id
                      AND f.concurso_id = s.concurso_id
                ) AS e_favorito,
                EXISTS (
                    SELECT 1 FROM analises AS a
                    WHERE a.user_id = s.user_id
                      AND a.concurso_id = s.concurso_id
                ) AS tem_analise
            FROM alerta_subscricoes AS s
            WHERE s.user_id = ?
              AND s.concurso_id = ?
            """,
            (user_id, concurso_id),
        ).fetchone()

        if linha is not None:
            return dict(linha)

        acompanhado = conexao.execute(
            """
            SELECT
                ? AS user_id,
                ? AS concurso_id,
                EXISTS (
                    SELECT 1 FROM favoritos
                    WHERE user_id = ?
                      AND concurso_id = ?
                ) AS e_favorito,
                EXISTS (
                    SELECT 1 FROM analises
                    WHERE user_id = ?
                      AND concurso_id = ?
                ) AS tem_analise,
                EXISTS (
                    SELECT 1 FROM analise_jobs
                    WHERE user_id = ?
                      AND concurso_id = ?
                ) AS tem_job
            """,
            (
                user_id,
                concurso_id,
                user_id,
                concurso_id,
                user_id,
                concurso_id,
                user_id,
                concurso_id,
            ),
        ).fetchone()

    dados = dict(acompanhado)
    dados["ativo"] = bool(
        dados.get("e_favorito")
        or dados.get("tem_analise")
        or dados.get("tem_job")
    )
    dados["origem"] = "automatica" if dados["ativo"] else "manual"
    return dados


def listar_alerta_subscricoes_utilizador(user_id: str):
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            WITH acompanhados AS (
                SELECT concurso_id, 'favorito' AS origem
                FROM favoritos
                WHERE user_id = ?

                UNION

                SELECT concurso_id, 'analise' AS origem
                FROM analises
                WHERE user_id = ?

                UNION

                SELECT concurso_id, 'analise' AS origem
                FROM analise_jobs
                WHERE user_id = ?

                UNION

                SELECT concurso_id, origem
                FROM alerta_subscricoes
                WHERE user_id = ?
            )
            SELECT
                c.id AS concurso_id,
                c.titulo,
                c.entidade,
                c.link,
                COALESCE(s.ativo, 1) AS ativo,
                COALESCE(s.origem, a.origem) AS origem,
                EXISTS (
                    SELECT 1 FROM favoritos AS f
                    WHERE f.user_id = ?
                      AND f.concurso_id = c.id
                ) AS e_favorito,
                EXISTS (
                    SELECT 1 FROM analises AS an
                    WHERE an.user_id = ?
                      AND an.concurso_id = c.id
                ) AS tem_analise
            FROM acompanhados AS a
            JOIN concursos AS c
              ON c.id = a.concurso_id
            LEFT JOIN alerta_subscricoes AS s
              ON s.user_id = ?
             AND s.concurso_id = c.id
            GROUP BY c.id
            ORDER BY c.titulo
            """,
            (
                user_id,
                user_id,
                user_id,
                user_id,
                user_id,
                user_id,
                user_id,
            ),
        ).fetchall()

    return [dict(linha) for linha in linhas]


def _data_limite_alerta(concurso) -> date | None:
    data_direta = _converter_data_guardada(
        concurso["data_entrega_propostas"]
        if "data_entrega_propostas" in concurso.keys()
        else None
    )
    if data_direta:
        return data_direta

    data_limite = concurso["data_limite"] if "data_limite" in concurso.keys() else None
    data_convertida = _converter_data_guardada(data_limite)
    if data_convertida:
        return data_convertida

    data_publicacao = _converter_data_guardada(concurso["data"])
    if not data_publicacao or not data_limite:
        return None

    correspondencia = re.search(r"\d+", str(data_limite))
    if not correspondencia:
        return None

    return data_publicacao + timedelta(days=int(correspondencia.group()))


def gerar_alertas_datas_monitorizados(user_id: str | None = None):
    hoje = date.today()

    with closing(abrir_conexao()) as conexao:
        if user_id:
            concursos = conexao.execute(
                """
                WITH acompanhados AS (
                    SELECT concurso_id
                    FROM favoritos
                    WHERE user_id = ?

                    UNION

                    SELECT concurso_id
                    FROM analises
                    WHERE user_id = ?

                    UNION

                    SELECT concurso_id
                    FROM analise_jobs
                    WHERE user_id = ?

                    UNION

                    SELECT concurso_id
                    FROM alerta_subscricoes
                    WHERE user_id = ?
                      AND ativo = 1
                )
                SELECT DISTINCT c.*
                FROM concursos AS c
                JOIN acompanhados AS a
                  ON a.concurso_id = c.id
                """,
                (user_id, user_id, user_id, user_id),
            ).fetchall()
        else:
            concursos = conexao.execute(
                """
                WITH acompanhados AS (
                    SELECT concurso_id FROM favoritos
                    UNION
                    SELECT concurso_id FROM analises WHERE user_id IS NOT NULL
                    UNION
                    SELECT concurso_id FROM analise_jobs
                    UNION
                    SELECT concurso_id
                    FROM alerta_subscricoes
                    WHERE ativo = 1
                )
                SELECT DISTINCT c.*
                FROM concursos AS c
                JOIN acompanhados AS a
                  ON a.concurso_id = c.id
                """
            ).fetchall()

        criados = 0
        for concurso in concursos:
            data_limite = _data_limite_alerta(concurso)
            if data_limite is None:
                continue

            dias_restantes = (data_limite - hoje).days
            if dias_restantes not in {30, 15, 7}:
                continue

            for utilizador in _utilizadores_monitorizar_concurso(
                conexao,
                concurso["id"],
            ):
                if user_id and utilizador != user_id:
                    continue

                antes = conexao.total_changes
                _criar_alerta(
                    conexao,
                    user_id=utilizador,
                    concurso_id=concurso["id"],
                    tipo="prazo",
                    titulo=f"Faltam {dias_restantes} dias",
                    descricao=(
                        "O prazo deste concurso esta a aproximar-se."
                    ),
                    dados_extraidos={
                        "data_limite": data_limite.isoformat(),
                        "dias_restantes": dias_restantes,
                    },
                    documento_origem=None,
                    link=concurso["link"],
                    fingerprint=(
                        f"prazo:{dias_restantes}:"
                        f"{data_limite.isoformat()}"
                    ),
                    relevante=False,
                )
                criados += int(conexao.total_changes > antes)

        conexao.commit()
        return criados


def listar_alertas_utilizador(user_id: str):
    gerar_alertas_datas_monitorizados(user_id)

    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT
                a.id,
                a.user_id,
                a.concurso_id,
                a.tipo,
                a.titulo,
                a.descricao,
                a.dados_extraidos,
                a.documento_origem,
                a.documento_anterior,
                a.documento_novo,
                a.hash_anterior,
                a.hash_novo,
                a.link,
                a.data_deteccao,
                a.estado,
                a.relevante,
                a.origem_evento,
                a.analise_job_id,
                a.created_at,
                a.updated_at,
                c.titulo AS concurso_titulo,
                c.entidade,
                c.link AS concurso_link,
                c.data_limite,
                c.data_entrega_propostas,
                EXISTS (
                    SELECT 1 FROM analises AS an
                    WHERE an.user_id = a.user_id
                      AND an.concurso_id = a.concurso_id
                      AND an.estado = 'concluida'
                ) AS tem_analise
            FROM alertas AS a
            JOIN concursos AS c
              ON c.id = a.concurso_id
            WHERE a.user_id = ?
              AND a.estado != 'arquivado'
            ORDER BY a.data_deteccao DESC, a.id DESC
            """,
            (user_id,),
        ).fetchall()

    resultados = []
    for linha in linhas:
        item = dict(linha)
        try:
            item["dados_extraidos"] = json.loads(
                item.get("dados_extraidos") or "{}"
            )
        except json.JSONDecodeError:
            item["dados_extraidos"] = {}
        resultados.append(item)

    return resultados


def arquivar_alerta_utilizador(user_id: str, alerta_id: int) -> bool:
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            UPDATE alertas
            SET estado = 'arquivado'
            WHERE id = ?
              AND user_id = ?
            """,
            (alerta_id, user_id),
        )
        conexao.commit()
        return cursor.rowcount == 1


def _registar_alertas_alteracoes_concurso_conexao(
    conexao,
    concurso_atual,
    novos: dict,
):
    utilizadores = _utilizadores_monitorizar_concurso(
        conexao,
        concurso_atual["id"],
    )
    if not utilizadores:
        return 0

    alteracoes = []

    def mudou(campo: str) -> bool:
        antigo = _normalizar_alerta(concurso_atual[campo])
        novo = _normalizar_alerta(novos.get(campo))
        return bool(novo and antigo and novo != antigo)

    def adicionado(campo: str) -> bool:
        antigo = _normalizar_alerta(concurso_atual[campo])
        novo = _normalizar_alerta(novos.get(campo))
        return bool(novo and not antigo)

    if mudou("preco_base"):
        alteracoes.append(
            {
                "tipo": "alteracao_economica",
                "titulo": "Valor estimado alterado",
                "descricao": "Foi detetada uma alteracao economica no concurso.",
                "dados": {
                    "campo": "preco_base",
                    "antes": concurso_atual["preco_base"],
                    "agora": novos.get("preco_base"),
                    "impacto": (
                        "Pode alterar a leitura de escala, risco e adequacao da equipa."
                    ),
                },
                "documento": novos.get("link_anuncio_dr"),
                "link": novos.get("link_anuncio_dr") or concurso_atual["link"],
            }
        )

    for campo in ("data_limite", "data_entrega_propostas"):
        if mudou(campo):
            alteracoes.append(
                {
                    "tipo": "alteracao_prazo",
                    "titulo": "Prazo do concurso alterado",
                    "descricao": "Foi detetada uma alteracao no calendario.",
                    "dados": {
                        "campo": campo,
                        "antes": concurso_atual[campo],
                        "agora": novos.get(campo),
                        "impacto": (
                            "Revê o planeamento da candidatura e a disponibilidade da equipa."
                        ),
                    },
                    "documento": novos.get("link_anuncio_dr"),
                    "link": novos.get("link_anuncio_dr") or concurso_atual["link"],
                }
            )

    if mudou("criterio_resumo") or mudou("criterio_detalhe"):
        alteracoes.append(
            {
                "tipo": "alteracao_criterio",
                "titulo": "Criterios de adjudicacao alterados",
                "descricao": (
                    "Foram detetadas alteracoes nos criterios ou ponderacoes."
                ),
                "dados": {
                    "antes": concurso_atual["criterio_resumo"],
                    "agora": novos.get("criterio_resumo"),
                    "impacto": (
                        "Esta alteracao pode influenciar a analise existente."
                    ),
                },
                "documento": novos.get("link_anuncio_dr"),
                "link": novos.get("link_anuncio_dr") or concurso_atual["link"],
            }
        )

    if mudou("entregaveis") or adicionado("entregaveis"):
        alteracoes.append(
            {
                "tipo": "alteracao_programa",
                "titulo": "Entregaveis ou programa alterados",
                "descricao": (
                    "Foi detetada informacao nova sobre entregaveis ou programa."
                ),
                "dados": {
                    "antes": concurso_atual["entregaveis"],
                    "agora": novos.get("entregaveis"),
                    "impacto": (
                        "Pode afetar o esforço de preparacao da proposta."
                    ),
                },
                "documento": novos.get("link_anuncio_dr"),
                "link": novos.get("link_anuncio_dr") or concurso_atual["link"],
            }
        )

    if mudou("link_pecas") or adicionado("link_pecas"):
        alteracoes.append(
            {
                "tipo": "novo_documento",
                "titulo": "Novo documento ou pacote de pecas publicado",
                "descricao": (
                    "Foi detetado um link novo para pecas do procedimento."
                ),
                "dados": {
                    "documento": "Pecas do procedimento",
                    "tipo_documento": "documentos_base_gov",
                    "impacto": (
                        "Os documentos oficiais podem alterar a leitura do concurso."
                    ),
                },
                "documento": novos.get("link_pecas"),
                "link": novos.get("link_pecas") or concurso_atual["link"],
            }
        )

    if mudou("data_esclarecimentos") or adicionado("data_esclarecimentos"):
        alteracoes.append(
            {
                "tipo": "esclarecimento",
                "titulo": "Informacao de esclarecimentos atualizada",
                "descricao": (
                    "Foi detetada informacao nova sobre pedidos de esclarecimento."
                ),
                "dados": {
                    "antes": concurso_atual["data_esclarecimentos"],
                    "agora": novos.get("data_esclarecimentos"),
                    "entidade": concurso_atual["entidade"],
                },
                "documento": novos.get("link_anuncio_dr"),
                "link": novos.get("link_anuncio_dr") or concurso_atual["link"],
            }
        )

    criados = 0
    for alteracao in alteracoes:
        relevante = alteracao["tipo"] in TIPOS_ALERTA_RELEVANTES
        for utilizador in utilizadores:
            antes = conexao.total_changes
            _criar_alerta(
                conexao,
                user_id=utilizador,
                concurso_id=concurso_atual["id"],
                tipo=alteracao["tipo"],
                titulo=alteracao["titulo"],
                descricao=alteracao["descricao"],
                dados_extraidos=alteracao["dados"],
                documento_origem=alteracao["documento"],
                link=alteracao["link"],
                fingerprint=(
                    f"{alteracao['tipo']}:"
                    f"{_normalizar_alerta(alteracao['dados'].get('agora') or alteracao['link'])}"
                ),
                relevante=relevante,
            )
            criados += int(conexao.total_changes > antes)

    return criados


def listar_analises_utilizador(user_id: str):
    with closing(abrir_conexao()) as conexao:
        fichas = conexao.execute(
            """
            SELECT
                a.id,
                'analise' AS tipo,
                a.user_id,
                a.concurso_id,
                a.estado,
                a.progresso,
                NULL AS erro,
                a.score,
                a.criado_em AS created_at,
                a.updated_at,
                CASE WHEN a.user_id = ? THEN 1 ELSE 0 END AS pode_apagar,
                0 AS pode_cancelar,
                0 AS pode_repetir,
                1 AS pode_atualizar,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analises AS a
            JOIN concursos AS c
              ON c.id = a.concurso_id
            WHERE a.estado = 'concluida'
              AND (a.user_id IS NULL OR a.user_id = ?)
            """,
            (user_id, user_id),
        ).fetchall()

        jobs = conexao.execute(
            """
            SELECT
                j.id,
                'job' AS tipo,
                j.user_id,
                j.concurso_id,
                j.estado,
                j.progresso,
                j.erro,
                NULL AS score,
                j.created_at,
                j.updated_at,
                CASE
                    WHEN j.estado IN ('erro', 'cancelada') THEN 1 ELSE 0
                END AS pode_apagar,
                CASE
                    WHEN j.estado IN (
                        'aguarda', 'extracao', 'processamento', 'geracao'
                    ) THEN 1 ELSE 0
                END AS pode_cancelar,
                CASE
                    WHEN j.estado = 'erro' THEN 1 ELSE 0
                END AS pode_repetir,
                CASE
                    WHEN j.estado IN ('erro', 'cancelada', 'concluida') THEN 1
                    ELSE 0
                END AS pode_atualizar,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analise_jobs AS j
            JOIN concursos AS c
              ON c.id = j.concurso_id
            WHERE j.user_id = ?
            ORDER BY j.updated_at DESC, j.id DESC
            """,
            (user_id,),
        ).fetchall()

    concursos_concluidos = {linha["concurso_id"] for linha in fichas}
    resultados = [dict(linha) for linha in fichas]
    resultados.extend(
        dict(linha)
        for linha in jobs
        if (
            linha["concurso_id"] not in concursos_concluidos
            or linha["estado"] != "concluida"
        )
    )
    resultados.sort(
        key=lambda linha: (linha.get("updated_at") or "", linha["id"]),
        reverse=True,
    )
    return resultados


def estados_analise_concursos(user_id: str | None = None):
    """
    Estado único de análise por concurso.

    Prioridade:
    1. Job do utilizador, se estiver ativo/erro/cancelado.
    2. Análise concluída do utilizador.
    3. Análise base do sistema.
    """
    with closing(abrir_conexao()) as conexao:
        mapa: dict[int, dict] = {}

        sistema = conexao.execute(
            """
            SELECT
                id AS analise_id,
                concurso_id,
                estado,
                progresso,
                score,
                updated_at
            FROM analises
            WHERE user_id IS NULL
              AND estado = 'concluida'
            """
        ).fetchall()
        for linha in sistema:
            mapa[linha["concurso_id"]] = {
                "temAnalise": True,
                "estadoAnalise": linha["estado"],
                "analiseId": linha["analise_id"],
                "analiseTipo": "sistema",
                "progressoAnalise": linha["progresso"],
                "scoreAnalise": linha["score"],
                "updatedAtAnalise": linha["updated_at"],
            }

        if user_id:
            concluidas = conexao.execute(
                """
                SELECT
                    id AS analise_id,
                    concurso_id,
                    estado,
                    progresso,
                    score,
                    updated_at
                FROM analises
                WHERE user_id = ?
                  AND estado = 'concluida'
                """,
                (user_id,),
            ).fetchall()
            for linha in concluidas:
                mapa[linha["concurso_id"]] = {
                    "temAnalise": True,
                    "estadoAnalise": linha["estado"],
                    "analiseId": linha["analise_id"],
                    "analiseTipo": "utilizador",
                    "progressoAnalise": linha["progresso"],
                    "scoreAnalise": linha["score"],
                    "updatedAtAnalise": linha["updated_at"],
                }

            jobs = conexao.execute(
                """
                SELECT
                    id AS job_id,
                    concurso_id,
                    estado,
                    progresso,
                    updated_at
                FROM analise_jobs
                WHERE user_id = ?
                  AND estado != 'concluida'
                """,
                (user_id,),
            ).fetchall()
            for linha in jobs:
                mapa[linha["concurso_id"]] = {
                    "temAnalise": True,
                    "estadoAnalise": linha["estado"],
                    "analiseId": linha["job_id"],
                    "analiseTipo": "job",
                    "progressoAnalise": linha["progresso"],
                    "scoreAnalise": None,
                    "updatedAtAnalise": linha["updated_at"],
                }

    return mapa


def obter_analise_ativa_concurso(
    concurso_id: int,
    user_id: str | None = None,
):
    """Resolve a ficha ativa pela BD, não pelo ficheiro solto."""
    with closing(abrir_conexao()) as conexao:
        if user_id:
            linha = conexao.execute(
                """
                SELECT *
                FROM analises
                WHERE concurso_id = ?
                  AND user_id = ?
                  AND estado = 'concluida'
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (concurso_id, user_id),
            ).fetchone()
            if linha:
                return dict(linha)

        linha = conexao.execute(
            """
            SELECT *
            FROM analises
            WHERE concurso_id = ?
              AND user_id IS NULL
              AND estado = 'concluida'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (concurso_id,),
        ).fetchone()

    return dict(linha) if linha else None


def listar_versoes_analise(
    analise_id: int,
):
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT
                id,
                analise_id,
                concurso_id,
                score,
                ficheiro_ficha,
                created_at
            FROM analise_versoes
            WHERE analise_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (analise_id,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def analise_concluida_por_concurso(
    concurso_id: int,
    user_id: str | None = None,
):
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT
                a.id,
                'analise' AS tipo,
                a.user_id,
                a.concurso_id,
                a.estado,
                a.progresso,
                NULL AS erro,
                a.score,
                a.criado_em AS created_at,
                a.updated_at,
                CASE WHEN a.user_id = ? THEN 1 ELSE 0 END AS pode_apagar,
                0 AS pode_cancelar,
                0 AS pode_repetir,
                1 AS pode_atualizar,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analises AS a
            JOIN concursos AS c ON c.id = a.concurso_id
            WHERE a.concurso_id = ?
              AND a.estado = 'concluida'
              AND (a.user_id IS NULL OR a.user_id = ?)
            ORDER BY CASE WHEN a.user_id = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (user_id, concurso_id, user_id, user_id),
        ).fetchone()
    return dict(linha) if linha else None


def reivindicar_proximo_analise_job():
    """Reserva atomicamente o job mais antigo para um futuro worker."""
    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")

        ativo = conexao.execute(
            """
            SELECT 1
            FROM analise_jobs
            WHERE estado IN ('extracao', 'processamento', 'geracao')
            LIMIT 1
            """
        ).fetchone()
        if ativo:
            conexao.rollback()
            return None

        job = conexao.execute(
            """
            SELECT id
            FROM analise_jobs
            WHERE estado = 'aguarda'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        ).fetchone()
        if job is None:
            conexao.rollback()
            return None

        conexao.execute(
            """
            UPDATE analise_jobs
            SET estado = 'extracao', progresso = 5, erro = NULL
            WHERE id = ? AND estado = 'aguarda'
            """,
            (job["id"],),
        )
        linha = conexao.execute(
            "SELECT * FROM analise_jobs WHERE id = ?",
            (job["id"],),
        ).fetchone()
        conexao.commit()
        return dict(linha) if linha else None


def atualizar_analise_job(
    job_id: int,
    estado: str,
    progresso: int,
    erro: str | None = None,
):
    """Atualiza um job; é a fronteira de integração do futuro worker."""
    if estado not in ESTADOS_ANALISE:
        raise ValueError(f"Estado de análise inválido: {estado}")
    if not 0 <= progresso <= 100:
        raise ValueError("O progresso tem de estar entre 0 e 100.")
    if estado == "concluida":
        progresso = 100

    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            UPDATE analise_jobs
            SET estado = ?, progresso = ?, erro = ?
            WHERE id = ?
              AND estado != 'cancelada'
            """,
            (estado, progresso, erro, job_id),
        )
        conexao.commit()
        return cursor.rowcount == 1


def criar_ou_obter_analise_job(
    user_id: str,
    concurso_id: int,
):
    """Cria um job idempotente sem iniciar o processamento."""
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            INSERT OR IGNORE INTO analise_jobs (
                user_id,
                concurso_id,
                estado,
                progresso
            )
            VALUES (?, ?, 'aguarda', 0)
            """,
            (user_id, concurso_id),
        )
        criado = cursor.rowcount == 1

        linha = conexao.execute(
            """
            SELECT
                j.id,
                j.user_id,
                j.concurso_id,
                j.estado,
                j.progresso,
                j.erro,
                j.created_at,
                j.updated_at,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analise_jobs AS j
            JOIN concursos AS c
              ON c.id = j.concurso_id
            WHERE j.user_id = ?
              AND j.concurso_id = ?
            """,
            (user_id, concurso_id),
        ).fetchone()

        conexao.commit()

    return dict(linha), criado


def criar_ou_reiniciar_analise_job(
    user_id: str,
    concurso_id: int,
):
    """Cria ou volta a colocar uma análise do utilizador na fila normal."""
    estados_ativos_sql = ", ".join(
        f"'{estado}'" for estado in ESTADOS_ANALISE_ATIVOS
    )
    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")
        linha = conexao.execute(
            """
            SELECT *
            FROM analise_jobs
            WHERE user_id = ? AND concurso_id = ?
            """,
            (user_id, concurso_id),
        ).fetchone()

        criado = False
        if linha is None:
            cursor = conexao.execute(
                """
                INSERT INTO analise_jobs (
                    user_id, concurso_id, estado, progresso, erro
                )
                VALUES (?, ?, 'aguarda', 0, NULL)
                """,
                (user_id, concurso_id),
            )
            job_id = cursor.lastrowid
            criado = True
        elif linha["estado"] in ESTADOS_ANALISE_ATIVOS:
            job_id = linha["id"]
        else:
            job_id = linha["id"]
            conexao.execute(
                f"""
                UPDATE analise_jobs
                SET estado = 'aguarda',
                    progresso = 0,
                    erro = NULL,
                    created_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND estado NOT IN ({estados_ativos_sql})
                """,
                (job_id,),
            )

        atualizado = conexao.execute(
            """
            SELECT
                j.id,
                'job' AS tipo,
                j.user_id,
                j.concurso_id,
                j.estado,
                j.progresso,
                j.erro,
                j.created_at,
                j.updated_at,
                CASE
                    WHEN j.estado IN ('erro', 'cancelada') THEN 1 ELSE 0
                END AS pode_apagar,
                CASE
                    WHEN j.estado IN (
                        'aguarda', 'extracao', 'processamento', 'geracao'
                    ) THEN 1 ELSE 0
                END AS pode_cancelar,
                CASE WHEN j.estado = 'erro' THEN 1 ELSE 0 END AS pode_repetir,
                CASE
                    WHEN j.estado IN ('erro', 'cancelada', 'concluida') THEN 1
                    ELSE 0
                END AS pode_atualizar,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analise_jobs AS j
            JOIN concursos AS c
              ON c.id = j.concurso_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()
        conexao.commit()

    return dict(atualizado), criado


def repetir_analise_job(
    user_id: str,
    job_id: int,
):
    """Repõe um job em erro na fila sem criar concurso nem pipeline nova."""
    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")
        cursor = conexao.execute(
            """
            UPDATE analise_jobs
            SET estado = 'aguarda',
                progresso = 0,
                erro = NULL,
                created_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND user_id = ?
              AND estado = 'erro'
            """,
            (job_id, user_id),
        )
        if cursor.rowcount != 1:
            conexao.rollback()
            return None

        linha = conexao.execute(
            """
            SELECT
                j.id,
                'job' AS tipo,
                j.user_id,
                j.concurso_id,
                j.estado,
                j.progresso,
                j.erro,
                j.created_at,
                j.updated_at,
                0 AS pode_apagar,
                1 AS pode_cancelar,
                0 AS pode_repetir,
                0 AS pode_atualizar,
                c.titulo,
                c.entidade,
                c.link,
                c.data,
                c.tipo_procedimento
            FROM analise_jobs AS j
            JOIN concursos AS c
              ON c.id = j.concurso_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()
        conexao.commit()
    return dict(linha) if linha else None


def obter_analise_job_utilizador(
    user_id: str,
    job_id: int,
):
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT *
            FROM analise_jobs
            WHERE id = ? AND user_id = ?
            """,
            (job_id, user_id),
        ).fetchone()
    return dict(linha) if linha else None


def cancelar_analise_job(
    user_id: str,
    job_id: int,
):
    """Cancela atomicamente um job ativo do próprio utilizador."""
    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")
        cursor = conexao.execute(
            """
            UPDATE analise_jobs
            SET estado = 'cancelada', erro = NULL
            WHERE id = ?
              AND user_id = ?
              AND estado IN ('aguarda', 'extracao', 'processamento', 'geracao')
            """,
            (job_id, user_id),
        )
        if cursor.rowcount != 1:
            conexao.rollback()
            return None

        linha = conexao.execute(
            "SELECT * FROM analise_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        conexao.commit()
    return dict(linha)


def remover_analise_job_utilizador(
    user_id: str,
    job_id: int,
):
    """Remove apenas jobs falhados/cancelados do utilizador."""
    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")
        linha = conexao.execute(
            """
            SELECT id, user_id, concurso_id, estado
            FROM analise_jobs
            WHERE id = ?
              AND user_id = ?
              AND estado IN ('erro', 'cancelada')
            """,
            (job_id, user_id),
        ).fetchone()
        if linha is None:
            conexao.rollback()
            return None

        dados = dict(linha)
        conexao.execute(
            "DELETE FROM analise_jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        )
        conexao.commit()
    return dados


def analise_job_esta_cancelado(job_id: int) -> bool:
    """Ponto de cancelamento cooperativo para o worker entre fases."""
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            "SELECT estado FROM analise_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return linha is not None and linha["estado"] == "cancelada"


def remover_analise_utilizador(
    user_id: str,
    analise_id: int,
):
    """Remove apenas uma análise concluída pertencente ao utilizador."""
    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")
        linha = conexao.execute(
            """
            SELECT id, user_id, job_id, concurso_id, ficheiro_ficha
            FROM analises
            WHERE id = ?
              AND user_id = ?
              AND estado = 'concluida'
            """,
            (analise_id, user_id),
        ).fetchone()
        if linha is None:
            conexao.rollback()
            return None

        dados = dict(linha)
        conexao.execute(
            "DELETE FROM analises WHERE id = ? AND user_id = ?",
            (analise_id, user_id),
        )

        if dados.get("job_id") is not None:
            conexao.execute(
                "DELETE FROM analise_jobs WHERE id = ? AND user_id = ?",
                (dados["job_id"], user_id),
            )
        else:
            conexao.execute(
                """
                DELETE FROM analise_jobs
                WHERE user_id = ?
                  AND concurso_id = ?
                  AND estado = 'concluida'
                """,
                (user_id, dados["concurso_id"]),
            )

        ficheiro = dados.get("ficheiro_ficha")
        dados["ficheiro_exclusivo"] = bool(
            ficheiro
            and conexao.execute(
                "SELECT 1 FROM analises WHERE ficheiro_ficha = ? LIMIT 1",
                (ficheiro,),
            ).fetchone()
            is None
        )
        conexao.commit()
    return dados


def _texto_ou_none(valor):
    """
    Converte valores vazios em None.
    """
    if valor is None:
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    return texto


def guardar_concurso(
    titulo,
    entidade,
    link,
    data,
    data_limite=None,
    data_esclarecimentos=None,
    preco_base=None,
    cpv=None,
    tipo_procedimento=None,
    criterio_tipo=None,
    criterio_resumo=None,
    criterio_detalhe=None,
    entregaveis=None,
    link_anuncio_dr=None,
    link_pecas=None,
    data_entrega_propostas=None,
    municipio=None,
    freguesia=None,
    morada=None,
    codigo_postal=None,
    latitude=None,
    longitude=None,
    localizacao_contexto=None,
):
    """
    Guarda um concurso na base de dados.

    Devolve:
        ID do concurso -> concurso novo guardado
        False -> concurso já existia
    """
    conn = abrir_conexao()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO concursos (
                titulo,
                entidade,
                link,
                data,
                relevante,
                data_limite,
                data_esclarecimentos,
                preco_base,
                cpv,
                tipo_procedimento,
                criterio_tipo,
                criterio_resumo,
                criterio_detalhe,
                entregaveis,
                link_anuncio_dr,
                link_pecas,
                data_entrega_propostas,
                municipio,
                freguesia,
                morada,
                codigo_postal,
                latitude,
                longitude,
                localizacao_contexto
            )
            VALUES (
                ?, ?, ?, ?, 1, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                titulo,
                _texto_ou_none(entidade),
                link,
                _texto_ou_none(data),
                _texto_ou_none(data_limite),
                _texto_ou_none(data_esclarecimentos),
                _texto_ou_none(preco_base),
                _texto_ou_none(cpv),
                _texto_ou_none(tipo_procedimento),
                _texto_ou_none(criterio_tipo),
                _texto_ou_none(criterio_resumo),
                _texto_ou_none(criterio_detalhe),
                _texto_ou_none(entregaveis),
                _texto_ou_none(link_anuncio_dr),
                _texto_ou_none(link_pecas),
                _texto_ou_none(data_entrega_propostas),
                _texto_ou_none(municipio),
                _texto_ou_none(freguesia),
                _texto_ou_none(morada),
                _texto_ou_none(codigo_postal),
                latitude,
                longitude,
                _texto_ou_none(localizacao_contexto),
            ),
        )

        conn.commit()
        guardado = cursor.lastrowid

    except sqlite3.IntegrityError:
        guardado = False

    finally:
        conn.close()

    return guardado


def atualizar_dados_concurso(
    link,
    titulo=None,
    entidade=None,
    data=None,
    data_limite=None,
    data_esclarecimentos=None,
    preco_base=None,
    cpv=None,
    tipo_procedimento=None,
    criterio_tipo=None,
    criterio_resumo=None,
    criterio_detalhe=None,
    entregaveis=None,
    link_anuncio_dr=None,
    link_pecas=None,
    data_entrega_propostas=None,
    municipio=None,
    freguesia=None,
    morada=None,
    codigo_postal=None,
    latitude=None,
    longitude=None,
    localizacao_contexto=None,
):
    """
    Atualiza os dados complementares de um concurso existente.

    Valores vazios não substituem informação que já esteja
    guardada na base de dados.
    """
    if not link:
        return False

    titulo = _texto_ou_none(titulo)
    entidade = _texto_ou_none(entidade)
    data = _texto_ou_none(data)
    data_limite = _texto_ou_none(data_limite)
    data_esclarecimentos = _texto_ou_none(
        data_esclarecimentos
    )
    preco_base = _texto_ou_none(preco_base)
    cpv = _texto_ou_none(cpv)
    tipo_procedimento = _texto_ou_none(
        tipo_procedimento
    )
    criterio_tipo = _texto_ou_none(
        criterio_tipo
    )
    criterio_resumo = _texto_ou_none(
        criterio_resumo
    )
    criterio_detalhe = _texto_ou_none(
        criterio_detalhe
    )
    entregaveis = _texto_ou_none(entregaveis)
    link_anuncio_dr = _texto_ou_none(link_anuncio_dr)
    link_pecas = _texto_ou_none(link_pecas)
    data_entrega_propostas = _texto_ou_none(
        data_entrega_propostas
    )
    municipio = _texto_ou_none(municipio)
    freguesia = _texto_ou_none(freguesia)
    morada = _texto_ou_none(morada)
    codigo_postal = _texto_ou_none(codigo_postal)
    localizacao_contexto = _texto_ou_none(localizacao_contexto)

    conn = abrir_conexao()
    cursor = conn.cursor()

    concurso_atual = cursor.execute(
        """
        SELECT *
        FROM concursos
        WHERE link = ?
        """,
        (link,),
    ).fetchone()

    if concurso_atual is not None:
        _registar_alertas_alteracoes_concurso_conexao(
            conn,
            concurso_atual,
            {
                "titulo": titulo,
                "entidade": entidade,
                "data": data,
                "data_limite": data_limite,
                "data_esclarecimentos": data_esclarecimentos,
                "preco_base": preco_base,
                "cpv": cpv,
                "tipo_procedimento": tipo_procedimento,
                "criterio_tipo": criterio_tipo,
                "criterio_resumo": criterio_resumo,
                "criterio_detalhe": criterio_detalhe,
                "entregaveis": entregaveis,
                "link_anuncio_dr": link_anuncio_dr,
                "link_pecas": link_pecas,
                "data_entrega_propostas": data_entrega_propostas,
                "municipio": municipio,
                "freguesia": freguesia,
                "morada": morada,
                "codigo_postal": codigo_postal,
                "latitude": latitude,
                "longitude": longitude,
                "localizacao_contexto": localizacao_contexto,
            },
        )

    cursor.execute(
        """
        UPDATE concursos
        SET
            titulo = COALESCE(?, titulo),
            entidade = COALESCE(?, entidade),
            data = COALESCE(?, data),
            data_limite = COALESCE(
                ?,
                data_limite
            ),
            data_esclarecimentos = COALESCE(
                ?,
                data_esclarecimentos
            ),
            preco_base = COALESCE(
                ?,
                preco_base
            ),
            cpv = COALESCE(?, cpv),
            tipo_procedimento = COALESCE(
                ?,
                tipo_procedimento
            ),
            criterio_tipo = COALESCE(
                ?,
                criterio_tipo
            ),
            criterio_resumo = COALESCE(
                ?,
                criterio_resumo
            ),
            criterio_detalhe = COALESCE(
                ?,
                criterio_detalhe
            ),
            entregaveis = COALESCE(
                ?,
                entregaveis
            ),
            link_anuncio_dr = COALESCE(
                ?,
                link_anuncio_dr
            ),
            link_pecas = COALESCE(
                ?,
                link_pecas
            ),
            data_entrega_propostas = COALESCE(
                ?,
                data_entrega_propostas
            ),
            municipio = COALESCE(
                ?,
                municipio
            ),
            freguesia = COALESCE(
                ?,
                freguesia
            ),
            morada = COALESCE(
                ?,
                morada
            ),
            codigo_postal = COALESCE(
                ?,
                codigo_postal
            ),
            latitude = COALESCE(
                ?,
                latitude
            ),
            longitude = COALESCE(
                ?,
                longitude
            ),
            localizacao_contexto = COALESCE(
                ?,
                localizacao_contexto
            )
        WHERE link = ?
        """,
        (
            titulo,
            entidade,
            data,
            data_limite,
            data_esclarecimentos,
            preco_base,
            cpv,
            tipo_procedimento,
            criterio_tipo,
            criterio_resumo,
            criterio_detalhe,
            entregaveis,
            link_anuncio_dr,
            link_pecas,
            data_entrega_propostas,
            municipio,
            freguesia,
            morada,
            codigo_postal,
            latitude,
            longitude,
            localizacao_contexto,
            link,
        ),
    )

    atualizado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return atualizado


def concurso_existe(link):
    """
    Verifica se existe um concurso com o mesmo link.
    """
    if not link:
        return False

    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM concursos
        WHERE link = ?
        LIMIT 1
        """,
        (link,),
    )

    existe = cursor.fetchone() is not None

    conn.close()

    return existe


def contar_concursos():
    """
    Devolve o número total de concursos guardados.
    """
    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM concursos
        """
    )

    total = cursor.fetchone()[0]

    conn.close()

    return total


def _converter_data_guardada(valor):
    """
    Converte uma data guardada na base de dados.

    Aceita os formatos mais comuns usados pelo projeto.
    """
    if not valor:
        return None

    texto = str(valor).strip()

    formatos = (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    )

    for formato in formatos:
        try:
            return datetime.strptime(
                texto,
                formato,
            ).date()

        except ValueError:
            continue

    try:
        return datetime.fromisoformat(
            texto.replace("Z", "+00:00")
        ).date()

    except ValueError:
        return None


def listar_concursos_periodo(
    data_inicio,
    data_fim,
):
    """
    Devolve os concursos publicados entre duas datas,
    incluindo a data inicial e excluindo a data final.

    Os argumentos devem ser objetos datetime.date.
    """
    if not isinstance(data_inicio, date):
        raise TypeError(
            "data_inicio deve ser uma data."
        )

    if not isinstance(data_fim, date):
        raise TypeError(
            "data_fim deve ser uma data."
        )

    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            titulo,
            entidade,
            link,
            data,
            data_limite,
            data_esclarecimentos,
            preco_base,
            cpv,
            tipo_procedimento
        FROM concursos
        WHERE relevante = 1
        """
    )

    linhas = cursor.fetchall()
    conn.close()

    concursos = []

    for linha in linhas:
        (
            titulo,
            entidade,
            link,
            data_texto,
            data_limite,
            data_esclarecimentos,
            preco_base,
            cpv,
            tipo_procedimento,
        ) = linha

        data_publicacao = _converter_data_guardada(
            data_texto
        )

        if data_publicacao is None:
            continue

        if not (
            data_inicio
            <= data_publicacao
            < data_fim
        ):
            continue

        concursos.append(
            {
                "titulo": titulo,
                "entidade": entidade,
                "link": link,
                "data": data_texto,
                "data_limite": data_limite,
                "preco_base": preco_base,
                "cpv": cpv,
                "tipo_procedimento": (
                    tipo_procedimento
                ),
                "_data_ordenacao": data_publicacao,
            }
        )

    concursos.sort(
        key=lambda concurso: (
            concurso["_data_ordenacao"],
            concurso.get("titulo") or "",
        )
    )

    for concurso in concursos:
        concurso.pop(
            "_data_ordenacao",
            None,
        )

    return concursos

def guardar_analise(
    concurso_id,
    nivel,
    resumo,
    dados_json,
    user_id=None,
    job_id=None,
    score=None,
    ficheiro_ficha=None,
):
    """
    Guarda ou atualiza a análise automática
    de um concurso.
    """

    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")

        if job_id is not None:
            job = conexao.execute(
                """
                SELECT user_id, concurso_id, estado
                FROM analise_jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            if (
                job is None
                or job["estado"] == "cancelada"
                or job["concurso_id"] != concurso_id
                or (user_id is not None and job["user_id"] != user_id)
            ):
                conexao.rollback()
                return False
            user_id = job["user_id"]

        if user_id is None:
            existente = conexao.execute(
                """
                SELECT id FROM analises
                WHERE concurso_id = ? AND user_id IS NULL
                """,
                (concurso_id,),
            ).fetchone()
        else:
            existente = conexao.execute(
                """
                SELECT id FROM analises
                WHERE concurso_id = ? AND user_id = ?
                """,
                (concurso_id, user_id),
            ).fetchone()

        parametros = (
            nivel,
            resumo,
            dados_json,
            score,
            ficheiro_ficha,
            job_id,
        )
        if existente:
            analise_id = existente["id"]
            anterior = conexao.execute(
                """
                SELECT
                    id, user_id, concurso_id, dados_json,
                    score, ficheiro_ficha
                FROM analises
                WHERE id = ?
                """,
                (analise_id,),
            ).fetchone()
            if anterior and anterior["dados_json"]:
                conexao.execute(
                    """
                    INSERT INTO analise_versoes (
                        analise_id,
                        user_id,
                        concurso_id,
                        dados_json,
                        score,
                        ficheiro_ficha
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        anterior["id"],
                        anterior["user_id"],
                        anterior["concurso_id"],
                        anterior["dados_json"],
                        anterior["score"],
                        anterior["ficheiro_ficha"],
                    ),
                )
            conexao.execute(
                """
                UPDATE analises
                SET nivel = ?, resumo = ?, dados_json = ?,
                    estado = 'concluida', progresso = 100,
                    score = COALESCE(?, score),
                    ficheiro_ficha = COALESCE(?, ficheiro_ficha),
                    job_id = COALESCE(?, job_id),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*parametros, analise_id),
            )
        else:
            cursor = conexao.execute(
                """
                INSERT INTO analises (
                    user_id, job_id, concurso_id, nivel, resumo,
                    dados_json, estado, progresso, score, ficheiro_ficha
                )
                VALUES (?, ?, ?, ?, ?, ?, 'concluida', 100, ?, ?)
                """,
                (
                    user_id,
                    job_id,
                    concurso_id,
                    nivel,
                    resumo,
                    dados_json,
                    score,
                    ficheiro_ficha,
                ),
            )
            analise_id = cursor.lastrowid

        if job_id is not None:
            atualizado = conexao.execute(
                """
                UPDATE analise_jobs
                SET estado = 'concluida', progresso = 100, erro = NULL
                WHERE id = ? AND estado != 'cancelada'
                """,
                (job_id,),
            )
            if atualizado.rowcount != 1:
                conexao.rollback()
                return False

        conexao.commit()
        return analise_id


def obter_analise(concurso_id):
    """
    Obtém a análise guardada.
    """

    conn = abrir_conexao()
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM analises
        WHERE concurso_id = ?
        ORDER BY CASE WHEN user_id IS NULL THEN 0 ELSE 1 END, id DESC
        LIMIT 1
        """,
        (
            concurso_id,
        )
    )

    resultado = cursor.fetchone()

    conn.close()

    if resultado:
        return dict(resultado)

    return None


def guardar_evento_timeline(
    concurso_id,
    tipo,
    titulo,
    data=None,
    estado=None,
    origem=None,
):
    """
    Guarda um evento na timeline de um concurso.
    """

    conn = abrir_conexao()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO timeline_eventos
        (
            concurso_id,
            tipo,
            titulo,
            data,
            estado,
            origem
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            concurso_id,
            tipo,
            titulo,
            data,
            estado,
            origem,
        ),
    )

    conn.commit()
    conn.close()



def obter_timeline(concurso_id):
    """
    Devolve os eventos de timeline de um concurso.
    """

    conn = abrir_conexao()
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM timeline_eventos
        WHERE concurso_id = ?
        ORDER BY data
        """,
        (
            concurso_id,
        ),
    )

    eventos = [
        dict(linha)
        for linha in cursor.fetchall()
    ]

    conn.close()

    return eventos


def gerar_timeline(concurso):
    """
    Gera automaticamente os eventos timeline
    a partir dos dados do concurso.
    """

    concurso_id = concurso.get("id")

    if not concurso_id:
        return


    conn = abrir_conexao()
    cursor = conn.cursor()


    # evitar duplicados
    cursor.execute(
        """
        DELETE FROM timeline_eventos
        WHERE concurso_id = ?
        """,
        (concurso_id,)
    )


    eventos = []


    if concurso.get("data"):

        eventos.append(
            (
                concurso_id,
                "publicacao",
                "Publicado",
                concurso.get("data"),
                "DR",
            )
        )


    if concurso.get("data_entrega_propostas"):

        eventos.append(
            (
                concurso_id,
                "entrega",
                "Entrega de propostas",
                concurso.get("data_entrega_propostas"),
                "DR",
            )
        )


    for evento in eventos:

        cursor.execute(
            """
            INSERT INTO timeline_eventos
            (
                concurso_id,
                tipo,
                titulo,
                data,
                origem
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            evento
        )


    conn.commit()
    conn.close()

