import sqlite3
import pandas as pd
import json

class DBManager:
    def __init__(self, db_path):
        self.db_path = db_path

    def get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            # Force WAL Checkpoint to ensure we see the latest data from the pulled WAL file
            # This is crucial because we just pulled raw files and SQLite might not auto-checkpoint immediately
            # or correctly in this read-only-like scenario.
            try:
                # PASSIVE: Checkpoint as much as possible without blocking
                # FULL: Checkpoint everything (might block if locks exist, but here we are single user)
                conn.execute("PRAGMA wal_checkpoint(FULL);")
            except Exception as e:
                # It might fail if database is locked or not in WAL mode, which is fine
                # print(f"Checkpoint warning: {e}")
                pass
                
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return None

    def get_tables(self):
        """Get a list of all tables in the database."""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row['name'] for row in cursor.fetchall()]
            return tables
        finally:
            conn.close()

    def get_table_info(self, table_name):
        """Get column info for a table."""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [dict(row) for row in cursor.fetchall()]
            return columns
        finally:
            conn.close()

    def get_table_data(self, table_name, limit=100, offset=0):
        """Get data from a table with pagination."""
        conn = self.get_connection()
        if not conn:
            return [], []
        
        try:
            cursor = conn.cursor()
            # Get columns first
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
            columns = [description[0] for description in cursor.description]
            
            # Get data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))
            rows = [dict(row) for row in cursor.fetchall()]
            
            # Count total rows
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            total_rows = cursor.fetchone()['count']
            
            return columns, rows, total_rows
        except sqlite3.Error as e:
            print(f"Error reading table {table_name}: {e}")
            return [], [], 0
        finally:
            conn.close()

    def execute_query(self, query):
        """Execute a custom SQL query."""
        conn = self.get_connection()
        if not conn:
            return {'error': 'Cannot connect to database'}
        
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            
            if cursor.description:
                columns = [description[0] for description in cursor.description]
                rows = [dict(row) for row in cursor.fetchall()]
                return {'columns': columns, 'rows': rows}
            else:
                conn.commit()
                return {'message': f'Query executed successfully. Rows affected: {cursor.rowcount}'}
        except sqlite3.Error as e:
            return {'error': str(e)}
        finally:
            conn.close()
