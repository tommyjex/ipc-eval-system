"""
数据库初始化脚本
创建所有表结构
"""
import sys
import os
import socket
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env", override=True)

import pymysql

db_host = os.getenv("DB_HOST", "localhost")
db_port = int(os.getenv("DB_PORT", "3306"))
db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD", "password")
db_name = os.getenv("DB_NAME", "evaluation")

# 解析域名为IP地址
try:
    ip_address = socket.gethostbyname(db_host)
    print(f"DNS解析: {db_host} -> {ip_address}")
    connect_host = ip_address
except socket.gaierror as e:
    print(f"DNS解析失败: {db_host}, 错误: {e}")
    connect_host = db_host

print(f"数据库连接: {connect_host}:{db_port}/{db_name}")


def create_tables():
    print("正在连接数据库...")
    try:
        conn = pymysql.connect(
            host=connect_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            charset='utf8mb4',
            connect_timeout=10
        )
        print("数据库连接成功！")
        
        cursor = conn.cursor()
        
        # 创建评测集表
        print("\n创建 datasets 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL COMMENT '评测集名称',
                description TEXT COMMENT '评测集描述',
                type ENUM('video', 'image', 'mixed') NOT NULL COMMENT '评测集类型',
                status ENUM('draft', 'ready', 'archived') DEFAULT 'draft' COMMENT '评测集状态',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                INDEX idx_datasets_status (status),
                INDEX idx_datasets_type (type),
                INDEX idx_datasets_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评测集表'
        """)
        print("  datasets 表创建成功")
        
        # 创建评测数据表
        print("\n创建 evaluation_data 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_data (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                dataset_id BIGINT NOT NULL COMMENT '评测集ID',
                file_name VARCHAR(255) NOT NULL COMMENT '文件名',
                file_type VARCHAR(50) NOT NULL COMMENT '文件类型',
                file_size BIGINT NOT NULL COMMENT '文件大小(字节)',
                tos_key VARCHAR(500) NOT NULL COMMENT 'TOS对象键',
                tos_bucket VARCHAR(100) NOT NULL COMMENT 'TOS存储桶',
                status ENUM('pending', 'annotated', 'failed') DEFAULT 'pending' COMMENT '标注状态',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
                INDEX idx_evaluation_data_dataset_id (dataset_id),
                INDEX idx_evaluation_data_status (status),
                INDEX idx_evaluation_data_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评测数据表'
        """)
        print("  evaluation_data 表创建成功")
        
        # 创建标注记录表
        print("\n创建 annotations 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                data_id BIGINT NOT NULL COMMENT '评测数据ID',
                ground_truth TEXT NOT NULL COMMENT '真值标注',
                annotation_type ENUM('manual', 'ai') NOT NULL COMMENT '标注类型',
                model_name VARCHAR(100) COMMENT '模型名称',
                annotator_id BIGINT COMMENT '标注者ID',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                FOREIGN KEY (data_id) REFERENCES evaluation_data(id) ON DELETE CASCADE,
                INDEX idx_annotations_data_id (data_id),
                INDEX idx_annotations_type (annotation_type),
                INDEX idx_annotations_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标注记录表'
        """)
        print("  annotations 表创建成功")
        
        conn.commit()
        conn.close()
        
        print("\n✅ 所有数据库表创建成功！")
        
    except Exception as e:
        print(f"创建表失败: {e}")
        raise


if __name__ == "__main__":
    create_tables()
