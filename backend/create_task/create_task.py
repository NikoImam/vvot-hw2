import ydb
import os
import json
import uuid
from datetime import datetime
import boto3

endpoint = os.getenv('YDB_ENDPOINT')
database = os.getenv('YDB_DATABASE')
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
check_n_download_q_url = os.getenv('CHECK_N_DOWNLOAD_Q_URL')

def create_task(title: str, video_url: str):
    driver = ydb.Driver(
        endpoint=endpoint,
        database=database,
        credentials=ydb.iam.MetadataUrlCredentials()
    )

    driver.wait(fail_fast=True, timeout=5)
    
    session = driver.table_client.session().create()
    
    task_id = uuid.uuid4()
    created_at = datetime.now()
    
    query = """
        DECLARE $id AS Uuid;
        DECLARE $created_at AS Timestamp;
        DECLARE $title AS Utf8;
        DECLARE $video_url AS Utf8;
        DECLARE $status AS Utf8;
        DECLARE $error_message AS Utf8;
        
        UPSERT INTO tasks (id, created_at, title, video_url, status, error_message)
        VALUES ($id, $created_at, $title, $video_url, $status, $error_message);
    """
    
    params = {
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
        params,
        commit_tx=True
    )
    
    driver.stop()

    return task_id

def send_message_to_check_n_download_q(id, video_url):
    s3_client = boto3.client(
        service_name='sqs',
        endpoint_url='https://message-queue.api.cloud.yandex.net',
        region_name='ru-central1',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )

    s3_client.send_message(
        QueueUrl=check_n_download_q_url,
        MessageBody=json.dumps({"id": id, "video_url": video_url})
    )

def handler(event, context):
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
                "error": "Не указана ссылка на видео"
            }),
            "headers": {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
    
    id = create_task(title, video_url)
    send_message_to_check_n_download_q(str(id), video_url)

    return {
        "statusCode": 200
    }