import os
import uuid
from sqlalchemy import create_engine, text

host = os.environ.get("DB_HOST", "localhost")
port = os.environ.get("DB_PORT", "5432")
user = os.environ.get("DB_USER", "postgres")
pwd = os.environ.get("DB_PASSWORD", "postgres")
admin_url = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/postgres"
print("ADMIN:", admin_url)

eng = create_engine(admin_url, isolation_level="AUTOCOMMIT")
name = f"zenrows_test_{uuid.uuid4().hex[:8]}"
print("TRY CREATE:", name)
with eng.connect() as conn:
    conn.execute(text(f"CREATE DATABASE {name}"))
print("CREATED")

eng.dispose()

eng2 = create_engine(f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{name}")
with eng2.connect() as c:
    print("CURRENT DB:", c.exec_driver_sql("SELECT current_database()").scalar_one())
eng2.dispose()

admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
with admin.connect() as conn:
    conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
print("DROPPED")
