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

async def create_task(title: str, video_url: str):
    driver = ydb.Driver(
        endpoint=endpoint,
        database=database,
        credentials=credentials
    )

    driver.wait(fail_fast=True, timeout=5)
    
    session = driver.table_client.session().create()
    
    task_id = str(uuid.uuid4())
    created_at = datetime.now()
    
    query = """
        DECLARE $id AS Utf8;
        DECLARE $created_at AS Timestamp;
        DECLARE $title AS Utf8;
        DECLARE $video_url AS Utf8;
        DECLARE $status AS Utf8;
        DECLARE $error_message AS Utf8;
        
        UPSERT INTO tasks (id, created_at, title, video_url, status, error_message)
        VALUES ($id, $created_at, $title, $video_url, $status, $error_message);
    """
    
    parameters = {
        '$id': task_id,
        '$created_at': created_at,
        '$title': title,
        '$video_url': video_url,
        '$status': 'queued',
        '$error_message': ''
    }
    
    prepared_query = session.prepare(query)
    session.transaction().execute(
        prepared_query,
        parameters,
        commit_tx=True
    )
    
    driver.stop()

    return task_id

async def handler(event, context):
    if 'body' in event:
        if event.get('isBase64Encoded', False):
            import base64
            body = base64.b64decode(event['body']).decode('utf-8')
        else:
            body = event['body']
        
        data = json.loads(body)
    else:
        data = event
    
    title = data.get('title', '').strip()
    video_url = data.get('link', '').strip()
    
    if not title:
        return {
            "statusCode": 400,
            "body": json.dumps({
                'error': 'Не указано название лекции'
            }),
            "headers": {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
    
    if not video_url:
        return {
            "statusCode": 400,
            "body": json.dumps({
                'error': 'Не указана ссылка на видео'
            }),
            "headers": {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
    
    await create_task(title, video_url)

    return {
        "statusCode": 200
    }