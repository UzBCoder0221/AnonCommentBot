from datetime import datetime
import sqlite3
import re


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
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INT NOT NULL,
            anon_name VARCHAR(255) DEFAULT 'USER',
            first_name VARCHAR(255) DEFAULT 'User',
            last_name VARCHAR(255),
            username VARCHAR(255),
            joined_at DATETIME,
            language VARCHAR(3)
            );
"""
        self.execute(sql, commit=True)

    def create_table_posts(self):
        sql = """
        CREATE TABLE IF NOT EXISTS Posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            to_id INT,
            message_id INT,
            to_message_id INT,
            thread_start_id INT,
            channel_id INT,
            content TEXT,
            created_at DATETIME
            );
"""
        self.execute(sql, commit=True)

    def create_table_user_post(self):
        sql = """
        CREATE TABLE IF NOT EXISTS user_post (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user INT,
            post INT
            );
"""
        self.execute(sql, commit=True)
    def create_table_reaction(self):
        sql = """
        CREATE TABLE IF NOT EXISTS reaction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user INT,
            post INT,
            reaction VARCHAR(255),
            created_at DATETIME
            );
"""
        self.execute(sql, commit=True)

    def create_all_tables(self):
        self.create_table_users()
        self.create_table_posts()
        self.create_table_user_post()
        self.create_table_reaction()

    @staticmethod
    def format_args(sql, parameters: dict):
        sql += " AND ".join([
            f"{item} = ?" for item in parameters
        ])
        return sql, tuple(parameters.values())

    def add_user(self, telegram_id: int, anon_name: str, first_name: str, last_name: str = None, username: str = None, joined_at = datetime.today(), language='uz'):
        sql = """
        INSERT INTO Users(telegram_id, anon_name, first_name, last_name, username, joined_at, language) VALUES(?, ?, ?, ?, ?, ?, ?)
        """
        self.execute(sql, parameters=(telegram_id, anon_name, first_name, last_name, username, joined_at, language), commit=True)
    
    def add_post(self, to_id: int, message_id: int, to_message_id: int = None, thread_start_id: int = None, channel_id: int = None, content: str = None, created_at=datetime.today()):
        sql = """
        INSERT INTO Posts(to_id, message_id, to_message_id, thread_start_id, channel_id, content, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)
        """
        self.execute(sql, parameters=(to_id, message_id, to_message_id, thread_start_id, channel_id, content, created_at), commit=True)
    def add_user_post(self, user: int, post: int):
        sql = """
        INSERT INTO user_post(user, post) VALUES(?, ?)
        """
        self.execute(sql, parameters=(user, post), commit=True)


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

    def update_user_language(self, language, id):
        sql = f"""
        UPDATE Users SET language=? WHERE id=?
        """
        return self.execute(sql, parameters=(language, id), commit=True)

    def delete_users(self):
        self.execute("DELETE FROM Users WHERE TRUE", commit=True)

    def select_all_posts(self):
        sql = """
        SELECT * FROM Posts
        """
        return self.execute(sql, fetchall=True)

    def select_post(self, **kwargs):
        sql = "SELECT * FROM Posts WHERE "
        sql, parameters = self.format_args(sql, kwargs)
        return self.execute(sql, parameters=parameters, fetchone=True)

    def select_last_post(self, to_id: int):
        sql = "SELECT * FROM Posts WHERE to_id = ? ORDER BY id DESC LIMIT 1"
        return self.execute(sql, parameters=(to_id,), fetchone=True)

    def count_posts(self):
        return self.execute("SELECT COUNT(*) FROM Posts;", fetchone=True)

    def update_post_content(self, content, id):
        sql = """
        UPDATE Posts SET content=? WHERE id=?
        """
        return self.execute(sql, parameters=(content, id), commit=True)

    def update_post_to_message_id(self, to_message_id, id):
        sql = """
        UPDATE Posts SET to_message_id=? WHERE id=?
        """
        return self.execute(sql, parameters=(to_message_id, id), commit=True)

    def delete_posts(self):
        self.execute("DELETE FROM Posts WHERE TRUE", commit=True)

    def select_all_user_posts(self):
        sql = """
        SELECT * FROM user_post
        """
        return self.execute(sql, fetchall=True)

    def select_user_post(self, **kwargs):
        sql = "SELECT * FROM user_post WHERE "
        sql, parameters = self.format_args(sql, kwargs)
        return self.execute(sql, parameters=parameters, fetchone=True)

    def delete_user_posts(self):
        self.execute("DELETE FROM user_post WHERE TRUE", commit=True)

    def add_reaction(self, user: int, post: int, reaction: str, created_at=datetime.today()):
        sql = """
        INSERT INTO reaction(user, post, reaction, created_at) VALUES(?, ?, ?, ?)
        """
        self.execute(sql, parameters=(user, post, reaction, created_at), commit=True)

    def get_or_create_user(self, telegram_id: int, first_name: str, last_name: str = None, username: str = None):
        user = self.select_user(telegram_id=telegram_id)
        if user:
            return user
        count = self.count_users()
        anon_name = f"USER_{(count[0] or 0) + 1}"
        self.add_user(
            telegram_id=telegram_id,
            anon_name=anon_name,
            first_name=first_name,
            last_name=last_name,
            username=username
        )
        return self.select_user(telegram_id=telegram_id)

    def select_all_reactions(self):
        sql = """
        SELECT * FROM reaction
        """
        return self.execute(sql, fetchall=True)

    def select_reaction(self, **kwargs):
        sql = "SELECT * FROM reaction WHERE "
        sql, parameters = self.format_args(sql, kwargs)
        return self.execute(sql, parameters=parameters, fetchone=True)

    def count_reactions(self):
        return self.execute("SELECT COUNT(*) FROM reaction;", fetchone=True)

    def delete_reactions(self):
        self.execute("DELETE FROM reaction WHERE TRUE", commit=True)


def logger(statement):
    print(f"""
_____________________________________________________
Executing:
{statement}
_____________________________________________________
""")