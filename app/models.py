# -------------------------------------------------------------
# 【修正点】: SQLAlchemyからARRAY型などをインポート
# -------------------------------------------------------------
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, String, ARRAY 
# -------------------------------------------------------------

from typing import List, Optional
from datetime import datetime
import json

# ====================================================================
# 列挙値（Option Sets）
# ====================================================================
GRADES = ["HighSchool_1st", "HighSchool_3rd", "University_1st", "Graduate_Master"]
INCOME_BANDS = ["~300万", "300~500万", "500~700万", "700~1000万", "1000万~"]
CATEGORIES = ["政府", "自治体", "大学", "企業", "財団", "NPO"]
TYPES = ["給付", "貸与", "免除", "助成"]
DIFFICULTIES = ["Easy", "Medium", "Hard"]

# ====================================================================
# Profile (診断入力)
# ====================================================================
class ProfileBase(SQLModel):
    grade: str = Field(index=True)
    prefecture: str = Field(index=True)
    income_band: str = Field(index=True)
    school_band: Optional[str] = None
    major: str
    gender: Optional[str] = None
    has_social_care: bool = Field(default=False, index=True)
    target_period: str
    has_volunteer: bool = Field(default=False)
    has_cram: bool = Field(default=False)

class Profile(ProfileBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    match_results: List["MatchResult"] = Relationship(back_populates="profile")

# ====================================================================
# Scholarship (奨学金マスタ)
# ====================================================================
class ScholarshipBase(SQLModel):
    name: str = Field(index=True)
    provider: str
    category: str
    type: str
    amount_per_year: int
    period: str

    # -------------------------------------------------------------
    # 【修正点】: List[str] のフィールドすべてに、sa_column=Column(ARRAY(String)) を追加
    # -------------------------------------------------------------
    eligible_grades: List[str] = Field(default=[], sa_column=Column(ARRAY(String)))
    eligible_prefs: List[str] = Field(default=[], sa_column=Column(ARRAY(String)))
    fields: List[str] = Field(default=[], sa_column=Column(ARRAY(String)))
    # -------------------------------------------------------------

    income_requirement: str
    other_requirements: Optional[str] = None
    
    deadline: datetime = Field(index=True)
    
    # -------------------------------------------------------------
    # 【修正点】: List[str] のフィールドすべてに、sa_column=Column(ARRAY(String)) を追加
    # -------------------------------------------------------------
    required_docs: List[str] = Field(default=[], sa_column=Column(ARRAY(String)))
    # -------------------------------------------------------------

    application_method: str
    difficulty_hint: str
    url: str
    contact: Optional[str] = None
    
    is_published: bool = Field(default=True, index=True)
    last_checked: datetime = Field(default_factory=datetime.utcnow)
    source: Optional[str] = None

class Scholarship(ScholarshipBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_results: List["MatchResult"] = Relationship(back_populates="scholarship")

# ====================================================================
# MatchResult (診断結果1件)
# =-------------------------------------------------------------
# 【修正点】: List[str] のフィールドすべてに、sa_column=Column(ARRAY(String)) を追加
# -------------------------------------------------------------
class MatchResultBase(SQLModel):
    rank: int
    score: float
    why_match: str
    difficulty: str
    deadline: datetime
    amount_per_year: int
    url: str
    todo: List[str] = Field(default=[], sa_column=Column(ARRAY(String)))
    digest: str
    raw_json: Optional[str] = None
    saved: bool = Field(default=False)

class MatchResult(MatchResultBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    scholarship_id: int = Field(foreign_key="scholarship.id", index=True)
    profile: Profile = Relationship(back_populates="match_results")
    scholarship: Scholarship = Relationship(back_populates="match_results")