import ydb
import os
import json
import uuid
from datetime import datetime, timezone, timedelta
import pytz

YC_TOKEN = os.getenv('YC_TOKEN')

endpoint = "grpcs://ydb.serverless.yandexcloud.net:2135"
database = "/ru-central1/b1g71e95h51okii30p25/etn90if7ni01era55tu0" 
credentials=ydb.AccessTokenCredentials(YC_TOKEN)



def create_table():
    driver = ydb.Driver(
        endpoint=endpoint,
        database=database,
        credentials=credentials
    )

    driver.wait(fail_fast=True, timeout=5)
    
    session = driver.table_client.session().create()
    
    create_table_query = """
    CREATE TABLE tasks (
        id Utf8,
        created_at Timestamp,
        title Utf8,
        video_url Utf8,
        status Utf8,
        error_message Utf8,
        PRIMARY KEY (id)
    );
    """
    
    session.execute_scheme(create_table_query)
    print("Таблица 'tasks' успешно создана!")
    driver.stop()