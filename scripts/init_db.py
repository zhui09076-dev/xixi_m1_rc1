# scripts/init_db.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Config
from core.database import Database

def main():
    config = Config.load("config.yaml")
    db_path = config.get("database.path", "data/xixi.db")
    db = Database(db_path)
    db.close()
    print("数据库初始化完成")

if __name__ == "__main__":
    main()
