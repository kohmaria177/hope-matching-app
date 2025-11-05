from sqlmodel import Session, select
from .models import Profile, MatchResult
from datetime import datetime, timedelta

def delete_old_data_job(session: Session):
    """
    90日以上経過したProfileとMatchResultを削除するジョブ
    """
    print("--- [ジョブ実行] 90日経過したデータのクリーンアップを開始 ---")
    
    try:
        # 90日前の日付を計算
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        # 1. 古いMatchResultを削除
        # (Profileを削除する前に、関連するMatchResultを削除する必要があります)
        statement_matches = select(MatchResult).where(MatchResult.deadline < cutoff_date) # 締切日で判定 (例)
        # または created_at を MatchResult に追加して判定
        
        old_matches = session.exec(statement_matches).all()
        match_count = len(old_matches)
        for match in old_matches:
            session.delete(match)
        
        # 2. 古いProfileを削除
        statement_profiles = select(Profile).where(Profile.created_at < cutoff_date)
        old_profiles = session.exec(statement_profiles).all()
        profile_count = len(old_profiles)
        for profile in old_profiles:
            session.delete(profile)
            
        # 変更をコミット
        session.commit()
        
        print(f"--- [ジョブ完了] {profile_count} 件のProfile、{match_count} 件のMatchResultを削除しました ---")

    except Exception as e:
        print(f"--- [ジョブエラー] データ削除中にエラーが発生しました: {e} ---")
        session.rollback()