"""CLI rescue tool for AI3L Community.

Usage:
    python backend/cli.py reset-superadmin --password <new_password>
"""

import argparse
import asyncio
import sys

import asyncpg
from pydantic_settings import BaseSettings, SettingsConfigDict


class CLISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    POSTGRES_USER: str = "ai3l"
    POSTGRES_PASSWORD: str = "changeme_postgres"
    POSTGRES_DB: str = "ai3l_community"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


async def reset_superadmin(password: str) -> None:
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
    password_hash = pwd_context.hash(password)

    settings = CLISettings()
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        result = await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE role = 'SUPER_ADMIN'",
            password_hash,
        )
        if result == "UPDATE 0":
            print("ERROR: No SUPER_ADMIN user found in the database.")
            sys.exit(1)
        print("Super Admin password updated successfully.")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="AI3L Community CLI Rescue Tool")
    subparsers = parser.add_subparsers(dest="command")

    reset_parser = subparsers.add_parser("reset-superadmin", help="Reset Super Admin password")
    reset_parser.add_argument("--password", required=True, help="New password for Super Admin")

    args = parser.parse_args()

    if args.command == "reset-superadmin":
        asyncio.run(reset_superadmin(args.password))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
