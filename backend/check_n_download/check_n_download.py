import json
import requests
import ydb
import os
import boto3
from io import BytesIO
import logging
import uuid

endpoint = os.getenv('YDB_ENDPOINT')
database = os.getenv('YDB_DATABASE')
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
bucket_name = os.getenv('BUCKET_NAME')
extract_audio_q_url = os.getenv('EXTRACT_AUDIO_Q_URL')

def is_correct_link(video_url):
    url = 'https://cloud-api.yandex.net/v1/disk/public/resources'
    params = {'public_key': video_url}
    headers = {'Accept': 'application/json'}

    response = requests.get(url=url, params=params, headers=headers, timeout=10)

    body = json.loads(response.content)

    if body.get('mime_type') == None:
        return False
    else:
        return body.get('mime_type').startswith('video/')

def change_task_status(id: str, status, message=None):
    try:
        driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.MetadataUrlCredentials()
        )

        driver.wait(fail_fast=True, timeout=5)

        session = driver.table_client.session().create()

        query = """
            DECLARE $id AS Uuid;
            DECLARE $status AS Utf8;
            DECLARE $error_message AS Utf8?;
            
            UPDATE tasks
            SET status = $status,
                error_message = $error_message
            WHERE id = $id
        """

        params = {
            '$id': uuid.UUID(id),
            '$status': status,
            '$error_message': message if message is not None else None
        }

        prepared_query = session.prepare(query)
        session.transaction().execute(
            prepared_query,
            params,
            commit_tx=True
        )

    finally:
        driver.stop()

def download_video(id, video_url):
    url = 'https://cloud-api.yandex.net/v1/disk/public/resources/download'
    params = {'public_key': video_url}
    headers = {'Accept': 'application/json'}

    response = requests.get(url=url, params=params, headers=headers, timeout=10)
    body = json.loads(response.content)
    href = body.get('href')

    obj_key = f'temp/videos/{id}'

    if href != None:
        response = requests.get(href, stream=True, timeout=100)
        response.raise_for_status()

        s3_client = boto3.client(
            service_name='s3',
            endpoint_url='https://storage.yandexcloud.net',
            region_name='ru-central1',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

        buff = BytesIO(response.content)
        
        s3_client.upload_fileobj(
            buff,
            bucket_name,
            obj_key,
            ExtraArgs={'ContentType': response.headers.get('Content-Type')}
        )

    return obj_key

def send_message_to_extract_audio_q(id, obj_key):
    s3_client = boto3.client(
        service_name='sqs',
        endpoint_url='https://message-queue.api.cloud.yandex.net',
        region_name='ru-central1',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )

    s3_client.send_message(
        QueueUrl=extract_audio_q_url,
        MessageBody=json.dumps({"id": id, "obj_key": obj_key})
    )

def handler(event, context):
    for msg in event['messages']:
        body = json.loads(msg['details']['message']['body'])

        if is_correct_link(body['video_url']):
            change_task_status(body['id'], 'processing')
        else:
            change_task_status(body['id'], 'error', 'Некорректная ссылка на публичное видео')
            return {'statusCode': 200}

        obj_key = download_video(body['id'], body['video_url'])
        send_message_to_extract_audio_q(body['id'], obj_key)

    return {"statusCode": 200}