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

def get_all_tasks():
    driver = ydb.Driver(
        endpoint=endpoint,
        database=database,
        credentials=credentials
    )

    driver.wait(fail_fast=True, timeout=5)
    
    session = driver.table_client.session().create()

    query = """
        SELECT 
            id,
            created_at,
            title,
            video_url,
            status,
            error_message
        FROM tasks 
        ORDER BY created_at DESC;
    """

    result = session.transaction().execute(query, commit_tx=True)

    tasks = []
    for row in result[0].rows:
        created_at_dt = datetime.fromtimestamp(row.created_at / 1000000, tz=timezone(timedelta(hours=3)))
        
        task = {
            "id": row.id,
            "createdAt": created_at_dt.strftime('%d.%m.%Y | %H:%M:%S'),
            "title": row.title,
            "videoUrl": row.video_url if row.video_url else "",
            "status": row.status,
            "errorMessage": row.error_message if row.error_message else ""
        }
        tasks.append(task)
    
    driver.stop()

    return json.dumps(tasks)

async def handler(event, context):
    tasks = get_all_tasks()

    return {
        "statusCode": 200,
        "body": tasks,
        "headers": {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    }