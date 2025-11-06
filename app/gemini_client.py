import os
import json
import google.generativeai as genai
from google.generativeai import types
from .models import Profile, Scholarship
from .schemas import MatchResponseSchema # 作成したスキーマをインポート
from typing import List

# .envファイルからAPIキーを読み込む設定
# (app/database.py で load_dotenv() が呼ばれている前提)
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("警告: GEMINI_API_KEY が設定されていません。Gemini機能は利用できません。")

def generate_match_results_gemini(
    profile: Profile, 
    scholarships: List[Scholarship]
) -> MatchResponseSchema:
    """
    Gemini APIを呼び出し、構造化されたマッチング結果を取得する
    """
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY が設定されていません。フェイルセーフ戦略を使用します。")
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash", # 高速・安価なモデル推奨
        # 構造化出力（JSON）の設定
        generation_config=types.GenerationConfig(
            response_mime_type="application/json",
            response_schema=MatchResponseSchema,
            temperature=0.2 # 創造性よりも一貫性を優先
        )
    )
    
    # プロンプトの組み立て
    system_instruction = (
        "あなたは奨学金マッチングAI「HOPE」です。ユーザーのプロフィールと提供された奨学金データベースのみに基づき、"
        "最も適合性の高いTOP5を、指定されたJSONスキーマで返してください。"
        "データベース外の情報は絶対に生成せず、優しく前向きなトーンで説明を加えてください。"
    )
    
    # データをJSON文字列に変換してプロンプトに埋め込む
    # Profileを辞書に変換
    profile_data = profile.model_dump_json(exclude={'id', 'created_at', 'match_results'})
    
    # Scholarshipのリストを辞書リストに変換
    scholarships_data = [
        sch.model_dump_json(exclude={'id', 'match_results', 'last_checked'}) 
        for sch in scholarships
    ]

    prompt = (
        f"--- ユーザープロフィール ---\n{profile_data}\n\n"
        f"--- 奨学金データベース (検索対象) ---\n{json.dumps(scholarships_data, ensure_ascii=False)}\n\n"
        "このデータベース内から、ユーザーに最適な奨学金TOP5を選び出し、指定されたJSONスキーマに従ってJSONを生成してください。"
    )

    try:
        # API呼び出し
        response = model.generate_content(
            prompt,
            system_instruction=system_instruction
        )
        
        # 応答のテキスト（JSON文字列）をPydanticモデルにパース
        return MatchResponseSchema.model_validate_json(response.text)

    except Exception as e:
        # 失敗ログを記録（ステップ7のフェイルセーフに繋げる）
        print(f"Gemini API Error: {e}")
        raise # エラーを呼び出し元に伝播させる