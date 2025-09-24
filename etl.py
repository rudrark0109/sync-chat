import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
import datetime

from app import User, Message, DailyAnalytics

DATABASE_URI = 'postgresql://postgres:rudrark12@localhost/sync_db'


def run_daily_etl():
    """
    This function connects to the database, calculates daily metrics,
    and saves them to the analytics table.
    """
    print(f"Starting ETL process for date: {datetime.date.today()}")

    engine = sqlalchemy.create_engine(DATABASE_URI)
    Session = sessionmaker(bind=engine)
    db_session = Session()

    today = datetime.date.today()

    try:
        print("Extracting and transforming data...")

        new_users_count = db_session.query(User).filter(
            func.date(User.created_at) == today
        ).count()
        print(f"-> Found {new_users_count} new users today.")

        messages_sent_count = db_session.query(Message).filter(
            func.date(Message.timestamp) == today
        ).count()
        print(f"-> Found {messages_sent_count} messages sent today.")

        print("Loading data into analytics table...")
        
        today_analytics = db_session.query(DailyAnalytics).filter_by(date=today).first()
        
        if today_analytics:
            print("Updating existing record for today.")
            today_analytics.new_users_count = new_users_count
            today_analytics.messages_sent_count = messages_sent_count
        else:
            print("Creating new record for today.")
            today_analytics = DailyAnalytics(
                date=today,
                new_users_count=new_users_count,
                messages_sent_count=messages_sent_count
            )
            db_session.add(today_analytics)
            
        db_session.commit()
        print("ETL process completed successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
        db_session.rollback() 
    finally:
        db_session.close()  


if __name__ == '__main__':
    run_daily_etl()