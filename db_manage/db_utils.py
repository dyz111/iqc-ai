import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pyodbc
from dbutils.pooled_db import PooledDB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Load .env from project root when running this module directly."""
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        os.environ.setdefault(key, value)


_load_env_file()


def _require_env(name: str, default: str = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


class DBConnector:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(DBConnector, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        self._configs = {
            "032_TJZT": {
                "driver": os.getenv("DB_032_DRIVER", "ODBC Driver 17 for SQL Server"),
                "server": _require_env("DB_032_SERVER"),
                "database": _require_env("DB_032_DATABASE"),
                "username": _require_env("DB_032_USERNAME"),
                "password": _require_env("DB_032_PASSWORD"),
                "timeout": int(os.getenv("DB_032_TIMEOUT", "30")),
                "extra_params": {
                    "Encrypt": os.getenv("DB_032_ENCRYPT", "yes"),
                    "TrustServerCertificate": os.getenv("DB_032_TRUST_SERVER_CERTIFICATE", "yes"),
                },
            },
            "05_iqc_system": {
                "driver": os.getenv("DB_05_DRIVER", "ODBC Driver 17 for SQL Server"),
                "server": _require_env("DB_05_SERVER"),
                "database": _require_env("DB_05_DATABASE"),
                "username": _require_env("DB_05_USERNAME"),
                "password": _require_env("DB_05_PASSWORD"),
                "timeout": int(os.getenv("DB_05_TIMEOUT", "30")),
                "extra_params": {
                    "Encrypt": os.getenv("DB_05_ENCRYPT", "yes"),
                    "TrustServerCertificate": os.getenv("DB_05_TRUST_SERVER_CERTIFICATE", "yes"),
                },
            },
        }
        self._pools = {}
        self._initialize_pools()

    def _initialize_pools(self):
        for db_type, config in list(self._configs.items()):
            try:
                self._pools[db_type] = PooledDB(
                    creator=pyodbc,
                    mincached=2,
                    maxcached=5,
                    maxconnections=10,
                    blocking=True,
                    driver=config["driver"],
                    server=config["server"],
                    database=config["database"],
                    uid=config["username"],
                    pwd=config["password"],
                    timeout=config["timeout"],
                    **config.get("extra_params", {}),
                )
                logger.info(f"Successfully created DB pool: {db_type.upper()}")
            except Exception as exc:
                logger.error(f"Failed creating DB pool {db_type.upper()}: {exc}", exc_info=True)
                self._configs.pop(db_type, None)

    @contextmanager
    def get_connection(self, db_type: str):
        if db_type not in self._pools:
            logger.error(f"Database {db_type.upper()} is not initialized.")
            raise ValueError(f"Database {db_type.upper()} is not initialized.")

        conn = None
        try:
            conn = self._pools[db_type].connection()
            logger.info(f"Acquired DB connection: {db_type.upper()}")
            yield conn
        except pyodbc.Error as exc:
            logger.error(f"DB connection error {db_type.upper()}: {exc}", exc_info=True)
            raise
        finally:
            if conn:
                conn.close()
                logger.info(f"Released DB connection: {db_type.upper()}")

    def health_check(self):
        results = {}
        for db_type in self._configs.keys():
            try:
                with self.get_connection(db_type) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT DB_NAME(), @@VERSION")
                        db_name, version = cursor.fetchone()
                        results[db_type] = {
                            "status": "healthy",
                            "database": db_name,
                            "version": version.split("\n")[0],
                        }
            except Exception as exc:
                results[db_type] = {"status": "unhealthy", "error": str(exc)}
                logger.error(f"Health check failed {db_type.upper()}: {exc}")
        return results


db_connector = DBConnector()


def db_worker(db_type: str, query: str, thread_id: int):
    logger.info(f"Thread ID: {thread_id}: start {db_type.upper()}...")
    try:
        time.sleep(0.05 * thread_id)

        with db_connector.get_connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            for i, row in enumerate(rows):
                if i < 10:
                    logger.info(f"Thread ID: {thread_id}: {db_type.upper()} data: {row}")
                elif i == 10:
                    logger.info(f"Thread ID: {thread_id}: {db_type.upper()} data: ...")
            logger.info(f"Thread ID: {thread_id}: done {db_type.upper()}. Fetched {len(rows)} rows")
    except Exception as exc:
        logger.error(f"Thread ID: {thread_id}: error fetching {db_type.upper()} data: {exc}")
        raise
    finally:
        time.sleep(0.1)


if __name__ == "__main__":
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    print("Initializing health check...", flush=True)
    print(db_connector.health_check(), flush=True)
    print("\n--- Start multi-thread DB ops ---", flush=True)

    threads = []
    num_threads_per_db = 3

    queries = {
        "032_TJZT": "select top 5 * from LHQ_QCD",
        "05_iqc_system": "select top 5 * from incoming_inspection_order_basic_detail",
    }

    thread_counter = 0
    for db_type, query in queries.items():
        for _ in range(num_threads_per_db):
            thread_counter += 1
            thread = threading.Thread(target=db_worker, args=(db_type, query, thread_counter))
            threads.append(thread)
            thread.start()

    for thread in threads:
        thread.join()
    print("\n--- All threads completed ---", flush=True)
    print("\n--- Health check done ---", flush=True)
    print(db_connector.health_check(), flush=True)
    print("\n--- Test finished ---", flush=True)
