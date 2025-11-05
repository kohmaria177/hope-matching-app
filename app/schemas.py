from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Gemini APIに「この形式で出力して」と指示するためのPydanticモデル

class MatchResultSchema(BaseModel):
    """Gemini APIが出力すべき単一の奨学金マッチング結果"""
    rank: int = Field(..., description="1から5のランキング順位")
    score: float = Field(..., description="適合度スコア (0.0〜1.0)")
    name: str = Field(..., description="奨学金の正式名称")
    provider: str = Field(..., description="提供団体名")
    why_match: str = Field(..., description="この奨学金がユーザーに最適な理由を優しく具体的に説明（100字程度）")
    deadline: str = Field(..., description="YYYY-MM-DD 形式の締切日")
    amount_per_year: int = Field(..., description="年間の支給額（円）")
    required_docs: List[str] = Field(..., description="申請に必要な書類のリスト")
    difficulty: str = Field(..., description="Easy, Medium, Hardのいずれか")
    url: str = Field(..., description="奨学金の公式URL")
    todo: List[str] = Field(..., description="申請実行の第一歩となる具体的なアクションリスト（3つ程度）")

class MatchResponseSchema(BaseModel):
    """APIの最終的なレスポンス構造"""
    results: List[MatchResultSchema] = Field(..., description="最適な奨学金TOP5のリスト")
    digest: str = Field(..., description="TOP5全体を要約した、ユーザーへの励ましのメッセージ（50字以内）")