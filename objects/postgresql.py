import asyncio
from psycopg import AsyncConnection, sql, OperationalError, errors

class PostgreSQLLogin():
    host = "localhost"
    port = 5432
    user = "dcbot"
    password = "mikumusicbot"
    database = "dcbot"

class PostgreSQLManager():
    """Manages PostgreSQL connections and database inspection operations using async."""

    def __init__(self, login: PostgreSQLLogin = PostgreSQLLogin()):
        self.host = login.host
        self.port = login.port
        self.user = login.user
        self.password = login.password
        self.database = login.database
        self.conn: AsyncConnection | None = None

    async def connect(self):
        """Create and return an asynchronous PostgreSQL connection."""
        try:
            db = self.database
            self.conn = await AsyncConnection.connect(
                host=self.host, port=self.port, user=self.user, password=self.password, dbname=db
            )
            # FIXED: Use the async method to set autocommit on psycopg3 AsyncConnection
            await self.conn.set_autocommit(True)
            return self.conn
        except OperationalError as e:
            print(f"Could not connect to PostgreSQL: {e}")
            return None

    async def close(self):
        """Close the current connection."""
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def list_databases(self):
        """List all databases in the PostgreSQL server."""
        if not self.conn:
            print("No active connection.")
            return []
        async with self.conn.cursor() as cur:
            await cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;")
            databases = [row[0] for row in await cur.fetchall()]
            return databases

    async def list_schemas(self):
        """List all schemas in the current database (excluding system schemas)."""
        if not self.conn:
            print("No active connection.")
            return []
        async with self.conn.cursor() as cur:
            await cur.execute("""
                SELECT schema_name FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema') 
                  AND schema_name NOT LIKE 'pg_toast%'
                ORDER BY schema_name;
            """)
            schemas = [row[0] for row in await cur.fetchall()]
            return schemas

    async def table_exists(self, table_name: str, schema: str = "public") -> bool:
        """Check whether a table exists in the specified schema.

        Args:
            table_name: The name of the table to check.
            schema: The schema to search in (default: "public").

        Returns:
            True if the table exists, False otherwise.
        """
        if not self.conn:
            print("No active connection.")
            return False
        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    "SELECT EXISTS (" 
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_name = %s"
                    ")",
                    (schema, table_name)
                )
                result = await cur.fetchone()
                return result[0] if result else False
            except errors.Error as e:
                print(f"Failed to check if table '{table_name}' exists: {e}")
                return False

    async def create_user_activity_table(self, table_name: str, schema="public"):
        """Create the user activity table in the specified schema (default: public).

        Columns:
            discord_user_id   BIGINT PRIMARY KEY
            activity_type     VARCHAR(10) NOT NULL CHECK (IN ('voice', 'text', 'null'))
            last_channel_id   BIGINT
            last_message_id   BIGINT
            last_active_at    TIMESTAMPTZ DEFAULT NOW()

        Args:
            table_name: The name of the table to create. (should be guild id)
            schema: Schema name (default: 'public').

        Returns:
            True if successful, False otherwise.
        """
        if not self.conn:
            print("No active connection.")
            return False
        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    sql.SQL("""
                        CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
                            discord_user_id   BIGINT PRIMARY KEY,
                            activity_type     VARCHAR(10) NOT NULL CHECK (activity_type IN ('voice', 'text', 'null')),
                            last_channel_id   BIGINT,
                            last_message_id   BIGINT,
                            last_active_at    TIMESTAMPTZ DEFAULT NOW()
                        )
                    """).format(
                        schema=sql.Identifier(schema),
                        table_name=sql.Identifier(table_name)
                    )
                )
                return True
            except errors.Error as e:
                print(f"Failed to create table '{table_name}': {e}")
                return False

    async def insert_default_user_activity(self, table_name: str, discord_user_id, schema="public"):
        """Insert a default row for a new user into the user activity table.

        Inserts with activity_type='null', last_channel_id=NULL, last_message_id=NULL,
        and last_active_at=NOW(). Uses INSERT ... ON CONFLICT to safely handle existing users.

        Args:
            table_name: The name of the table to insert into. (should be guild id)
            discord_user_id: The Discord user's ID (BIGINT).
            schema: Schema name (default: 'public').

        Returns:
            True if successful, False otherwise.
        """
        if not self.conn:
            print("No active connection.")
            return False
        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    sql.SQL("""
                        INSERT INTO {schema}.{table_name} (discord_user_id, activity_type, last_channel_id, last_message_id, last_active_at)
                        VALUES (%s, 'null', NULL, NULL, NOW())
                        ON CONFLICT (discord_user_id) DO NOTHING
                    """).format(
                        schema=sql.Identifier(schema),
                        table_name=sql.Identifier(table_name)
                    ),
                    (discord_user_id,)
                )
                return True
            except errors.Error as e:
                print(f"Failed to insert default activity for user {discord_user_id}: {e}")
                return False

    async def insert_timeline_entry(self, entry_id: int, schema="public"):
        """Insert a new entry into the timeline table with the current time.

        Args:
            entry_id: The ID (BIGINT) for the new timeline entry. (should be guild id)
            schema: Schema name (default: 'public').

        Returns:
            True if successful, False otherwise.
        """
        if not self.conn:
            print("No active connection.")
            return False
        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    sql.SQL("""
                        INSERT INTO {}.timeline (id, time)
                        VALUES (%s, NOW())
                        RETURNING id
                    """).format(sql.Identifier(schema)),
                    (entry_id,)
                )
                return True
            except errors.Error as e:
                print(f"Failed to insert timeline entry: {e}")
                return False

    async def get_timeline_time(self, entry_id: int, schema="public"):
        """Get the time for a timeline entry by its id.

        Args:
            entry_id: The id of the timeline entry. (should be guild id)
            schema: Schema name (default: 'public').

        Returns:
            The datetime if found, None otherwise.
        """
        if not self.conn:
            print("No active connection.")
            return None
        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    sql.SQL("SELECT time FROM {}.timeline WHERE id = %s").format(
                        sql.Identifier(schema)
                    ),
                    (entry_id,)
                )
                result = await cur.fetchone()
                return result[0] if result else None
            except errors.Error as e:
                print(f"Failed to get timeline time for id {entry_id}: {e}")
                return None
            
    

    async def update_user_activity(self, table_name: str, discord_user_id, activity_type, last_channel_id, last_message_id=None, schema="public"):
        """Update activity info for an existing user in the user activity table.

        Args:
            table_name: The name of the table to update. (should be guild id)
            discord_user_id: The Discord user's ID (BIGINT).
            activity_type: 'voice', 'text', or 'null' (required).
            last_channel_id: Channel ID (BIGINT, required).
            last_message_id: Message ID (BIGINT or None). Auto-set to None if activity_type is 'voice'.
            schema: Schema name (default: 'public').

        Returns:
            True if successful, False otherwise.
        """
        if not self.conn:
            print("No active connection.")
            return False

        if discord_user_id is None or activity_type is None or last_channel_id is None:
            print("discord_user_id, activity_type, and last_channel_id are required.")
            return False
        
        if activity_type not in ('voice', 'text'):
            print("Invalid activity_type. Must be 'voice', or 'text'.")
            return False
        
        if activity_type == "text" and last_message_id is None:
            print("last_message_id is required for text activity.")
            return False

        if activity_type == "voice":
            last_message_id = None

        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    sql.SQL("INSERT INTO {schema}.{table_name} (discord_user_id, activity_type, last_channel_id, last_message_id, last_active_at) VALUES (%s, %s, %s, %s, NOW()) ON CONFLICT (discord_user_id) DO UPDATE SET activity_type = EXCLUDED.activity_type, last_channel_id = EXCLUDED.last_channel_id, last_message_id = EXCLUDED.last_message_id, last_active_at = NOW()").format(
                        schema=sql.Identifier(schema),
                        table_name=sql.Identifier(table_name)
                    ),
                    (discord_user_id, activity_type, last_channel_id, last_message_id)
                )
                return True
            except errors.Error as e:
                print(f"Failed to update activity for user {discord_user_id}: {e}")
                return False

    async def get_inactive_users(self, table_name: str, days: int, schema="public"):
        """Return discord_user_ids of users whose last_active_at is older than the specified number of days.

        Args:
            table_name: The name of the table to query. (should be guild id)
            days: Number of days. Users inactive for longer than this will be returned.
            schema: Schema name (default: 'public').

        Returns:
            List of tuple (discord_user_id, last_active_at), or an empty list if none found or on error.
        """
        if not self.conn:
            print("No active connection.")
            return []
        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    sql.SQL("""
                        SELECT discord_user_id, last_active_at
                        FROM {schema}.{table_name}
                        WHERE last_active_at < NOW() - INTERVAL '1 day' * %s
                        ORDER BY last_active_at ASC
                    """).format(
                        schema=sql.Identifier(schema),
                        table_name=sql.Identifier(table_name)
                    ),
                    (days,)
                )
                return [row for row in await cur.fetchall()]
            except errors.Error as e:
                print(f"Failed to get inactive users: {e}")
                return []

    async def get_user_activity(self, table_name: str, discord_user_id: int, schema="public"):
        """Get activity info for a single user by their Discord ID.

        Args:
            table_name: The name of the table to query. (should be guild id)
            discord_user_id: The Discord user's ID (BIGINT).
            schema: Schema name (default: 'public').

        Returns:
            Tuple of (activity_type, last_channel_id, last_message_id, last_active_at),
            or None if not found or on error.
        """
        if not self.conn:
            print("No active connection.")
            return None
        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    sql.SQL("""
                        SELECT activity_type, last_channel_id, last_message_id, last_active_at
                        FROM {schema}.{table_name}
                        WHERE discord_user_id = %s
                    """).format(
                        schema=sql.Identifier(schema),
                        table_name=sql.Identifier(table_name)
                    ),
                    (discord_user_id,)
                )
                result = await cur.fetchone()
                return result if result else None
            except errors.Error as e:
                print(f"Failed to get activity for user {discord_user_id}: {e}")
                return None

    async def remove_user_activity(self, table_name: str, discord_user_id: int, schema="public"):
        """Remove a user's activity entry from the user activity table by their Discord ID.

        Args:
            table_name: The name of the table to delete from. (should be guild id)
            discord_user_id: The Discord user's ID (BIGINT).
            schema: Schema name (default: 'public').

        Returns:
            True if successful, False otherwise.
        """
        if not self.conn:
            print("No active connection.")
            return False

        if discord_user_id is None:
            print("discord_user_id is required.")
            return False

        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    sql.SQL("""
                        DELETE FROM {schema}.{table_name}
                        WHERE discord_user_id = %s
                    """).format(
                        schema=sql.Identifier(schema),
                        table_name=sql.Identifier(table_name)
                    ),
                    (discord_user_id,)
                )
                print(f"Activity entry removed for user {discord_user_id}.")
                return True
            except errors.Error as e:
                print(f"Failed to remove activity for user {discord_user_id}: {e}")
                return False

    async def list_tables(self, schema="public"):
        """List all tables in the current database (default: public schema)."""
        if not self.conn:
            print("No active connection.")
            return []
        async with self.conn.cursor() as cur:
            await cur.execute(
                sql.SQL("""
                    SELECT tablename FROM pg_catalog.pg_tables 
                    WHERE schemaname = {} 
                    ORDER BY tablename;
                """).format(sql.Literal(schema))
            )
            tables = [row[0] for row in await cur.fetchall()]
            return tables

    async def get_table_info(self, table_name, schema="public"):
        """Get column info and row count for a selected table."""
        if not self.conn:
            print("No active connection.")
            return [], 0
        async with self.conn.cursor() as cur:
            # Column details
            await cur.execute(
                sql.SQL("""
                    SELECT column_name, data_type, is_nullable, column_default 
                    FROM information_schema.columns 
                    WHERE table_schema = {} AND table_name = {} 
                    ORDER BY ordinal_position;
                """).format(sql.Literal(schema), sql.Literal(table_name))
            )
            columns = await cur.fetchall()

            # Row count
            await cur.execute(
                sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                    sql.Identifier(schema), sql.Identifier(table_name)
                )
            )
            row_count = (await cur.fetchone())[0]
            return columns, row_count

    async def get_table_rows(self, table_name, schema="public", limit=50):
        """Fetch rows from a selected table."""
        if not self.conn:
            print("No active connection.")
            return [], []
        async with self.conn.cursor() as cur:
            await cur.execute(
                sql.SQL("SELECT * FROM {}.{} LIMIT {}").format(
                    sql.Identifier(schema), sql.Identifier(table_name), sql.Literal(limit)
                )
            )
            rows = await cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
            return columns, rows

    @staticmethod
    def _parse_choice(choice, max_val):
        """Parse user input into a valid index."""
        if choice:
            try:
                idx = int(choice) - 1
                if not (0 <= idx < max_val):
                    print("Invalid choice. Using first item.")
                    idx = 0
            except ValueError:
                print("Invalid input. Using first item.")
                idx = 0
        else:
            idx = 0
        return idx


async def main():
    """Async main function to run the inspection."""
    manager = PostgreSQLManager()
    """Interactive inspection workflow against the database set in __init__."""
    login = PostgreSQLLogin()
    print(f"Connecting to PostgreSQL at {login.host}:{login.port} as {login.user} on database {login.database}...\n")
    if not await manager.connect():
        return

    try:
        # --- List schemas ---
        schemas = await manager.list_schemas()
        print(f"=== Schemas in {manager.database} ===")
        for i, sch in enumerate(schemas, 1):
            print(f"  {i}. {sch}")
        print()

        if not schemas:
            print("No schemas found.")
            return

        # --- Pick a schema ---
        schema_choice = input("Enter schema number to inspect, or blank for first: ").strip()
        sidx = manager._parse_choice(schema_choice, len(schemas))
        selected_schema = schemas[sidx]
        print(f"\nSelected schema: {selected_schema}\n")

        # --- List tables in selected schema ---
        tables = await manager.list_tables(selected_schema)
        print(f"=== Tables in {selected_schema} schema ===")
        for i, tbl in enumerate(tables, 1):
            print(f"  {i}. {tbl}")
        print()

        if not tables:
            print("No tables found.")
            return

        # --- Pick a table to inspect ---
        table_choice = input("Enter table number to inspect, or blank for first: ").strip()
        tidx = manager._parse_choice(table_choice, len(tables))

        selected_table = tables[tidx]
        print(f"\n--- Table: {selected_schema}.{selected_table} ---")

        # Table structure
        columns, row_count = await manager.get_table_info(selected_table, selected_schema)
        print(f"Rows: {row_count}")
        print(f"{'Column':<25} {'Type':<20} {'Nullable':<10} {'Default'}")
        print("-" * 75)
        for col_name, col_type, nullable, default in columns:
            print(f"{col_name:<25} {col_type:<20} {nullable:<10} {default or '-'}")

        # Preview rows
        preview = input("\nShow first 50 rows? (y/n): ").strip().lower()
        if preview == "y":
            headers, rows = await manager.get_table_rows(selected_table, selected_schema)
            if rows:
                print(f"\n{' | '.join(headers)}")
                print("-" * (len(headers * 5)))
                for row in rows:
                    print(" | ".join(str(v) for v in row))
            else:
                print("No rows to display.")

        table_exists = await manager.table_exists(selected_table, selected_schema)
        print(f"\nTable '{selected_table}' exists in schema '{selected_schema}': {table_exists}")

    finally:
        # Ensure connection is closed even if inspection fails
        await manager.close()
        print("\nDone.")


if __name__ == "__main__":
    # On Windows, asyncio default loop (ProactorEventLoop) is not compatible with psycopg async.
    # We must force the use of SelectorEventLoop.
    import sys
    if sys.platform == "win32":
        import selectors
        asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main())

