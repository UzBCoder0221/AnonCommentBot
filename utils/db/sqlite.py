from datetime import datetime
import sqlite3


class Database:
    def __init__(self, path_to_db="main.db"):
        self.path_to_db = path_to_db

    @property
    def connection(self):
        return sqlite3.connect(self.path_to_db)

    def execute(self, sql: str, parameters: tuple = None, fetchone=False, fetchall=False, commit=False):
        if not parameters:
            parameters = ()
        connection = self.connection
        connection.set_trace_callback(logger)
        cursor = connection.cursor()
        data = None
        cursor.execute(sql, parameters)

        if commit:
            connection.commit()
        if fetchall:
            data = cursor.fetchall()
        if fetchone:
            data = cursor.fetchone()
        connection.close()
        return data

    def create_table_users(self):
        sql = """
        CREATE TABLE Users (
            id INT NOT NULL PRIMARY KEY,
            telegram_id INT NOT NULL,
            first_name VARCHAR(255) DEFAULT 'User',
            last_name VARCHAR(255),
            username VARCHAR(255),
            joined_at DATETIME,
            language VARCHAR(3),
            );
"""
        self.execute(sql, commit=True)

    def create_table_posts(self):
        sql = """
        CREATE TABLE Posts (
            id INT NOT NULL PRIMARY KEY,
            to_id INT,
            message_id INT,
            to_message_id INT,
            thread_start_id INT,
            channel_id INT,
            content INT,
            created_at INT
            );
"""
        self.execute(sql, commit=True)
    def create_table_user_post(self):
        sql = """
        CREATE TABLE user_post (
            id INT NOT NULL PRIMARY KEY,
            user INT,
            post INT,
            );
"""
        self.execute(sql, commit=True)
    def create_table_reaction(self):
        sql = """
        CREATE TABLE reaction (
            id INT NOT NULL PRIMARY KEY,
            user INT,
            post INT,
            reaction VARCHAR(255)
            created_at INT
            );
"""
        self.execute(sql, commit=True)


    @staticmethod
    def format_args(sql, parameters: dict):
        sql += " AND ".join([
            f"{item} = ?" for item in parameters
        ])
        return sql, tuple(parameters.values())

    def add_user(self, id: int, telegram_id: int, first_name: str, last_name: str = None, username: str = None, joined_at = datetime.today(), language='uz'):
        sql = """
        INSERT INTO Users(id, telegram_id, first_name, last_name, username, joined_at, language) VALUES(?, ?, ?, ?, ?, ?, ?)
        """
        self.execute(sql, parameters=(id, name, username, email, language), commit=True)

    def select_all_users(self):
        sql = """
        SELECT * FROM Users
        """
        return self.execute(sql, fetchall=True)

    def select_user(self, **kwargs):
        sql = "SELECT * FROM Users WHERE "
        sql, parameters = self.format_args(sql, kwargs)

        return self.execute(sql, parameters=parameters, fetchone=True)

    def count_users(self):
        return self.execute("SELECT COUNT(*) FROM Users;", fetchone=True)

    def update_user_email(self, email, id):
        # SQL_EXAMPLE = "UPDATE Users SET email=mail@gmail.com WHERE id=12345"

        sql = f"""
        UPDATE Users SET email=? WHERE id=?
        """
        return self.execute(sql, parameters=(email, id), commit=True)

    def delete_users(self):
        self.execute("DELETE FROM Users WHERE TRUE", commit=True)


def logger(statement):
    print(f"""
_____________________________________________________
Executing:
{statement}
_____________________________________________________
""")