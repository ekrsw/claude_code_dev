from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base_model import BaseModel


class InfoCategory(BaseModel):
    """Information category master table"""
    
    __tablename__ = "info_categories"
    
    code = Column(String(2), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    display_order = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    def __repr__(self) -> str:
        return f"<InfoCategory(code={self.code}, name={self.display_name})>"


# Category data for initial seeding
INITIAL_CATEGORIES = [
    {"code": "01", "display_name": "_会計・財務", "display_order": 1},
    {"code": "02", "display_name": "_起動トラブル", "display_order": 2},
    {"code": "03", "display_name": "_給与・年末調整", "display_order": 3},
    {"code": "04", "display_name": "_減価・ﾘｰｽ/資産管理", "display_order": 4},
    {"code": "05", "display_name": "_公益・医療会計", "display_order": 5},
    {"code": "06", "display_name": "_工事・原価", "display_order": 6},
    {"code": "07", "display_name": "_債権・債務", "display_order": 7},
    {"code": "08", "display_name": "_事務所管理", "display_order": 8},
    {"code": "09", "display_name": "_人事", "display_order": 9},
    {"code": "10", "display_name": "_税務関連", "display_order": 10},
    {"code": "11", "display_name": "_電子申告", "display_order": 11},
    {"code": "12", "display_name": "_販売", "display_order": 12},
    {"code": "13", "display_name": "EdgeTracker", "display_order": 13},
    {"code": "14", "display_name": "MJS-Connect関連", "display_order": 14},
    {"code": "15", "display_name": "インストール・MOU", "display_order": 15},
    {"code": "16", "display_name": "かんたん！シリーズ", "display_order": 16},
    {"code": "17", "display_name": "その他（システム以外）", "display_order": 17},
    {"code": "18", "display_name": "その他MJSシステム", "display_order": 18},
    {"code": "19", "display_name": "その他システム（共通）", "display_order": 19},
    {"code": "20", "display_name": "ハード関連(HDD)", "display_order": 20},
    {"code": "21", "display_name": "ハード関連（ソフトウェア）", "display_order": 21},
    {"code": "22", "display_name": "マイナンバー", "display_order": 22},
    {"code": "23", "display_name": "ワークフロー", "display_order": 23},
    {"code": "24", "display_name": "一時受付用", "display_order": 24},
    {"code": "25", "display_name": "運用ルール", "display_order": 25},
    {"code": "26", "display_name": "顧客情報", "display_order": 26},
]