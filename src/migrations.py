from yoyo import read_migrations, get_backend
import env


def apply():
    backend = get_backend(env.get_postgres_connection_string())
    migrations = read_migrations("./migrations")
    backend.apply_migrations(backend.to_apply(migrations))
