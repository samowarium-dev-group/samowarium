from yoyo import read_migrations, get_backend
import env


def apply():
    backend = get_backend(
        f"postgres://{env.get_postgres_user()}:{env.get_postgres_password()}@{env.get_postgres_host()}/{env.get_postgres_db()}"
    )
    migrations = read_migrations("./migrations")
    backend.apply_migrations(backend.to_apply(migrations))
