import os
import oracledb
from dotenv import load_dotenv
import sys

# Add project root to sys.path to find .env if needed, or just load directly
# Script is in producao/, so project root is up 1 level
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
dotenv_path = os.path.join(project_root, ".env")

# Load environment variables
load_dotenv(dotenv_path)

# Configuration
DB_HOST = os.getenv("ORACLE_HOST")
DB_PORT = os.getenv("ORACLE_PORT")
DB_SERVICE = os.getenv("ORACLE_SERVICE_NAME")
DB_USER = os.getenv("ORACLE_USER")
DB_PASSWORD = os.getenv("ORACLE_PASSWORD")

def get_dados_san001():
    """
    Connects to Oracle and returns records from GRUPOAEL.SAN001 as a list of dictionaries.
    """
    if not all([DB_HOST, DB_PORT, DB_SERVICE, DB_USER, DB_PASSWORD]):
        print(f"Error: Missing Oracle environment variables using .env at {dotenv_path}")
        return []

    dsn = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"
    
    try:
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=dsn
        )

        with connection.cursor() as cursor:
            # Read SQL from file
            sql_file_path = os.path.join(current_dir, 'sql', 'query.sql')
            try:
                with open(sql_file_path, 'r') as file:
                    sql = file.read()
            except FileNotFoundError:
                print(f"Error: SQL file not found at {sql_file_path}")
                return []

            cursor.execute(sql)

            # Get column names
            columns = [col[0] for col in cursor.description]

            # Fetch all rows
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))
            
            return results

    except oracledb.Error as e:
        print(f"Oracle Error: {e}")
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    # Test the function
    dados = get_dados_san001()
    print(f"Foram encontrados {len(dados)} registros.")
    if dados:
        print("Exemplo do primeiro registro:")
        print(dados[0])
