from typing import List, Tuple
from datetime import datetime, timedelta
from sqlmodel import Session, select, func
from .models import Profile, Scholarship, MatchResult # .modelsはappフォルダ内のmodels.pyを指します

# 適合条件に応じた重み付け（W）を定義
WEIGHTS = {
    "MUST_MATCH": 1.0,  # 必須条件（満たさなければ0点）
    "SOCIAL_CARE": 0.5, # 社会的養護経験者向け (高ボーナス)
    "HIGH_AMOUNT": 0.3, # 支給額が多い
    "MAJOR_MATCH": 0.2, # 専攻分野が一致
    "DEADLINE_BONUS": 0.1 # 締切が近い（申請意欲向上）
}

def get_income_score(profile_income: str, sch_income_req: str) -> float:
    """年収条件が profile に適合するかを判断する簡易ロジック"""
    # 実際には正規表現や複雑な比較が必要だが、ここでは簡略化
    
    # 奨学金が「条件なし」なら常に適合
    if sch_income_req == "条件なし":
        return 1.0
    
    # ここでは Profile の年収バンドが奨学金要件と一致する場合のみ適合（超簡易版）
    # 例: Profileが'~300万'で、Scholarshipが'世帯年収300万円未満'なら適合
    if profile_income in sch_income_req:
        return 1.0
        
    return 0.0


def calculate_score(profile: Profile, scholarship: Scholarship) -> float:
    """
    ProfileとScholarshipを比較し、適合度スコア（0.0〜1.0）を算出する
    """
    score = 0.0

    # 1. 必須条件チェック (満たさない場合は即座に0点)
    
    # 1-1. 学年必須チェック
    if scholarship.eligible_grades and profile.grade not in scholarship.eligible_grades:
        return 0.0
    
    # 1-2. 地域必須チェック (空のリストは全国対象とみなす)
    if scholarship.eligible_prefs and profile.prefecture not in scholarship.eligible_prefs:
        return 0.0
    
    # 1-3. 年収条件チェック
    if get_income_score(profile.income_band, scholarship.income_requirement) == 0.0:
        return 0.0

    # 必須条件クリアで基本スコアを加算 
    score += 0.1

    # 2. ボーナス条件加算
    
    # 2-1. 社会的養護経験者向けボーナス
    if profile.has_social_care and "経験者" in scholarship.other_requirements:
        score += WEIGHTS["SOCIAL_CARE"]
    
    # 2-2. 専攻分野一致ボーナス
    if profile.major in scholarship.fields:
        score += WEIGHTS["MAJOR_MATCH"]
        
    # 2-3. 締切が近いボーナス (30日以内)
    days_to_deadline = (scholarship.deadline.date() - datetime.utcnow().date()).days
    if 0 < days_to_deadline <= 30:
        score += WEIGHTS["DEADLINE_BONUS"]
        
    # 2-4. 支給額ボーナス (50万円以上)
    if scholarship.amount_per_year >= 500000:
        score += WEIGHTS["HIGH_AMOUNT"]

    # スコアを0.0から1.0の範囲に正規化（ここでは単純に合計で返す）
    return min(score, 1.0)

def generate_rule_based_results(session: Session, profile_id: int) -> List[MatchResult]:
    """
    DB内のデータとルールベーススコアリングでTOP5を生成する（フェイルセーフ用）
    """
    profile = session.get(Profile, profile_id)
    if not profile:
        return []

    # 公開されている全奨学金を取得
    scholarships = session.exec(
        select(Scholarship).where(Scholarship.is_published == True)
    ).all()

    scored_results = []
    for sch in scholarships:
        score = calculate_score(profile, sch)
        if score > 0: # 必須条件をクリアしたものだけを対象
            scored_results.append({
                "scholarship": sch,
                "score": score,
                "deadline_sort_key": (sch.deadline - datetime.utcnow()).total_seconds()
            })

    # スコア降順、締切昇順でソート (scoreが高い順、スコアが同じなら締切が近い順)
    # deadline_sort_keyのマイナスは、降順ソートで「値が小さい＝締切が近い」を優先するため
    scored_results.sort(
        key=lambda x: (x["score"], -x["deadline_sort_key"]), 
        reverse=True
    )
    
    top_5 = scored_results[:5]
    
    # MatchResultオブジェクトへの変換とテンプレート生成
    match_results = []
    for rank, result in enumerate(top_5, 1):
        sch = result["scholarship"]
        
        # テンプレート生成
        why_match = f"（ルールベース）あなたの{profile.grade}と{profile.prefecture}に合致し、スコアは{result['score']:.2f}です。まずは必要書類の準備を進めましょう。"
        todo = sch.required_docs + ["学校の奨学金窓口に相談する"]
        
        match_results.append(MatchResult(
            rank=rank,
            score=result["score"],
            why_match=why_match,
            difficulty=sch.difficulty_hint,
            deadline=sch.deadline,
            amount_per_year=sch.amount_per_year,
            url=sch.url,
            todo=todo,
            digest="AI失敗時の代替結果です。期限の近いものから検討してください。",
            profile_id=profile.id,
            scholarship_id=sch.id
        ))

    return match_results