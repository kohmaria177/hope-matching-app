import os
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from typing import List, Dict
from datetime import datetime
import asyncio

#APSscheduler関連のインポート
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager



# 作成した各モジュールをインポート
from .database import get_session, engine
from .models import Profile, Scholarship, MatchResult
from .schemas import MatchResponseSchema
from .matching_logic import generate_rule_based_results # フェイルセーフ用
from .gemini_client import generate_match_results_gemini # Geminiクライアント

#スケジューラーのジョブのインポート
from .scheduler import delete_old_data_job

#スケジューラーとライフスパンイベントの定義
scheduler = BackgroundScheduler()
@asynccontextmanager
async def lifespan(app: FastAPI):
    # アプリケーション起動時に実行
    print("--- サーバー起動: スケジューラを開始します ---")
    
    # DBセッションをスケジューラージョブに渡すための設定
    # (APSchedulerは別スレッドで動くため、新しいエンジン/セッションが必要)
    job_engine = create_engine(DATABASE_URL)
    
    def job_wrapper():
        with Session(job_engine) as session:
            delete_old_data_job(session)

    # ジョブを登録（例: 毎日午前3時に実行）
    scheduler.add_job(job_wrapper, 'cron', hour=3, minute=0)
    scheduler.start()
    
    yield
    
    # アプリケーション終了時に実行
    print("--- サーバーシャットダウン: スケジューラを停止します ---")
    scheduler.shutdown()
# -------------------------------------------------------------
# FastAPIアプリケーションの初期化
app = FastAPI(title="HOPE マッチングAI")
# -------------------------------------------------------------
# 【追記】CORS設定
# -------------------------------------------------------------
origins = [
   "*" # "http://localhost:3000", # Next.js (フロントエンド) のアドレス
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], #全てのHTTPメソッドを許可
    allow_headers=["*"], #全てのヘッダー許可
)

# ----------------------------------------------------
# ヘルスチェック用
# ----------------------------------------------------
@app.get("/api/healthz", tags=["Health"])
def health_check():
    return {"status": "ok"}

# ----------------------------------------------------
# ユーザー診断（Profile）作成用 (テスト用)
# ----------------------------------------------------
@app.post("/api/profiles", response_model=Profile, tags=["Profiles"])
def create_profile(profile: Profile, session: Session = Depends(get_session)):
    """
    （テスト用）新しい診断プロファイルを作成します。
    """
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile

# ----------------------------------------------------
# 奨学金マスタ取得用 (テスト用)
# ----------------------------------------------------
@app.get("/api/scholarships", response_model=List[Scholarship], tags=["Scholarships"])
def get_scholarships(session: Session = Depends(get_session)):
    """
    （テスト用）DBに登録されている奨学金マスタを全件取得します。
    """
    return session.exec(select(Scholarship)).all()

# ----------------------------------------------------
# マッチングAPI (ハイブリッド戦略)
# ----------------------------------------------------
async def run_matching_strategy(profile_id: int, session: Session):
    """
    バックグラウンドでハイブリッド・マッチングを実行する関数
    """
    print(f"[{profile_id}] マッチング処理を開始...")
    profile = session.get(Profile, profile_id)
    if not profile:
        print(f"[{profile_id}] エラー: プロファイルが見つかりません。")
        return

    # DBから全奨学金を取得
    # (注：本番では全件取得は非効率なため、ルールベースで事前フィルタリング推奨)
    scholarships = session.exec(
        select(Scholarship).where(Scholarship.is_published == True)
    ).all()

    try:
        # 1. Gemini API (メイン戦略) を呼び出す (タイムアウト設定)
        print(f"[{profile_id}] メイン戦略 (Gemini) を試行...")
        gemini_response = await asyncio.wait_for(
            generate_match_results_gemini(profile, scholarships),
            timeout=10.0 # 10秒でタイムアウト
        )
        
        print(f"[{profile_id}] Gemini 成功。結果をDBに保存します。")
        # MatchResult オブジェクトに変換してDBに保存
        for res_item in gemini_response.results:
            # 奨学金IDを見つける (本番では辞書検索などで効率化)
            sch_id = next(
                (sch.id for sch in scholarships if sch.name == res_item.name), 
                None
            )
            
            match_result = MatchResult(
                rank=res_item.rank,
                score=res_item.score,
                why_match=res_item.why_match,
                difficulty=res_item.difficulty,
                deadline=datetime.fromisoformat(res_item.deadline),
                amount_per_year=res_item.amount_per_year,
                url=res_item.url,
                todo=res_item.todo,
                digest=gemini_response.digest,
                profile_id=profile_id,
                scholarship_id=sch_id,
                raw_json=res_item.model_dump_json()
            )
            session.add(match_result)

    except Exception as e:
        # 2. フェイルセーフ戦略 (ルールベース) を実行
        print(f"[{profile_id}] Gemini 失敗 ({e})。フェイルセーフ (ルールベース) を実行します。")
        rule_based_results = generate_rule_based_results(session, profile_id)
        
        for res_item in rule_based_results:
            session.add(res_item)

    finally:
        # 3. 実行結果をコミット
        session.commit()
        print(f"[{profile_id}] マッチング処理完了。")


@app.post("/api/request_match", tags=["Matching"])
async def request_match(
    profile_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    マッチングリクエストを受け付け、バックグラウンドでハイブリッド処理を実行する。
    （ユーザーを待たせないため、即時レスポンスを返す）
    """
    background_tasks.add_task(run_matching_strategy, profile_id, session)
    
    return {
        "status": "success", 
        "message": "マッチング処理を受け付けました。数秒後に結果を確認してください。",
        "profile_id": profile_id
    }

# ----------------------------------------------------
# マッチング結果取得用
# ----------------------------------------------------
@app.get("/api/match_results", response_model=List[MatchResult], tags=["Matching"])
def get_match_results(
    profile_id: int,
    session: Session = Depends(get_session)
):
    """
    指定されたプロファイルIDに紐づくマッチング結果（TOP5）を取得する。
    """
    results = session.exec(
        select(MatchResult)
        .where(MatchResult.profile_id == profile_id)
        .order_by(MatchResult.rank)
    ).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="マッチング結果が見つからないか、処理中です。")
        
    return results