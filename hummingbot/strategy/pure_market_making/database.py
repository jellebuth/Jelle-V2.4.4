import pymysql


def connect_database():
    db = pymysql.connect(user='hummingbot', password='',
                         host='hummingbot.ceh1qcgkh4yh.ap-northeast-1.rds.amazonaws.com')
    cursor = db.cursor()

    create_db_if_not_exists(cursor)

    cursor.execute("USE HUMMINGBOT")


def create_db_if_not_exists(cursor):
    cursor.execute("CREATE DATABASE IF NOT EXISTS HUMMINGBOT")


def write_trades_to_db(cursor):
    pass
