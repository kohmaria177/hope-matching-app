import json
import os
from datetime import datetime
from sqlmodel import Session, SQLModel, create_engine
from .models import Scholarship
from .database import DATABASE_URL # DB接続情報を流用

# DBエンジンを初期化
engine = create_engine(DATABASE_URL, echo=False)

def create_db_and_tables():
    """SQLModelの定義に基づきテーブルを作成（Alembicが既に行っているが、念のため）"""
    SQLModel.metadata.create_all(engine)

def seed_data():
    """scholarships.jsonからデータを読み込み、DBに投入する"""
    print("--- データの投入を開始します ---")
    
    # data/scholarships.json へのパスを構築
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "scholarships.json")
    
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            scholarship_data = json.load(f)
    except FileNotFoundError:
        print(f"エラー: {data_path} が見つかりません。先にダミーデータを作成してください。")
        return
    
    with Session(engine) as session:
        count = 0
        for item in scholarship_data:
            # deadlineを文字列からdatetimeオブジェクトに変換
            # ZはUTCを示すため、Pythonのdatetime.fromisoformatで処理できるように変換
            item['deadline'] = datetime.fromisoformat(item['deadline'].replace('Z', '+00:00'))
            
            # Scholarshipオブジェクトを作成し、DBに追加
            scholarship = Scholarship.model_validate(item)
            session.add(scholarship)
            count += 1
        
        session.commit()
        print(f"成功: {count} 件の奨学金データをデータベースに投入しました。")

if __name__ == "__main__":
    # create_db_and_tables() # Alembicを使ったのでコメントアウト
    seed_data()