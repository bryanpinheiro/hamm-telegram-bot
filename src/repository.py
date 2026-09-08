import sqlite3

class Repository:
    def __init__(self):
        self.connection = sqlite3.connect('user.db', check_same_thread=False)
        self.cursor = self.connection.cursor()
        self.init_db()

    def init_db(self):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            balance REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS type_transaction(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transactions(
            id_transaction INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL NOT NULL,
            type INTEGER,
            created_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(type) REFERENCES type_transaction(id)
        );

        INSERT OR IGNORE INTO type_transaction (id, name) VALUES (1, 'deposit'), (2, 'withdraw');
        """
        self.cursor.executescript(create_table_query)
        self.connection.commit()

    def user_exists(self, user_id):
        query = "SELECT id FROM users WHERE id = ?"
        self.cursor.execute(query, (user_id,))
        return self.cursor.fetchone() is not None

    def user_create_if_not_exists(self, user_id):
        if not self.user_exists(user_id):
            query = "INSERT INTO users (id, balance) VALUES (?, ?)"
            self.cursor.execute(query, (user_id, 0))
            self.connection.commit()

    def inflow(self, user_id, amount):
        query = "UPDATE users SET balance = balance + ? WHERE id = ?"
        self.cursor.execute(query, (amount, user_id))

        query = "INSERT INTO transactions (user_id, amount, type, created_at) VALUES (?, ?, 1, datetime('now'))"
        self.cursor.execute(query, (user_id, amount))
        self.connection.commit()

    def outflow(self, user_id, amount):
        query = "UPDATE users SET balance = balance - ? WHERE id = ?"
        self.cursor.execute(query, (amount, user_id))

        query = "INSERT INTO transactions (user_id, amount, type, created_at) VALUES (?, ?, 2, datetime('now'))"
        self.cursor.execute(query, (user_id, amount))
        self.connection.commit()

    def close(self):
        self.connection.close()
