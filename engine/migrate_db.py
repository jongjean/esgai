import sqlite3

def migrate():
    db_path = "/app/leads.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. stage3_data
    try:
        cursor.execute("ALTER TABLE leads ADD COLUMN stage3_data TEXT")
        print("Success: Added stage3_data column.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Notice: stage3_data already exists.")
        else:
            print(f"Error adding stage3_data: {e}")
            
    # 2. report_content
    try:
        cursor.execute("ALTER TABLE leads ADD COLUMN report_content TEXT")
        print("Success: Added report_content column.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Notice: report_content already exists.")
        else:
            print(f"Error adding report_content: {e}")
            
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
