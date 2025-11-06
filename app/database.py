from sqlmodel import create_engine, Session
import os
from dotenv import load_dotenv

load_dotenv() # .env ファイルから環境変数を読み込む

# Export for other modules to use
__all__ = ['create_engine', 'Session', 'engine', 'get_session', 'DATABASE_URL']

# .env または Docker Compose の設定からDB情報を取得
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "hopedb")

# DB接続文字列を定義
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=False) # echo=Trueにすると実行されるSQLが表示されます

def get_session():
    """DBセッションを取得するジェネレータ"""
    with Session(engine) as session:
        yield session