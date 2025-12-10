import json
import requests
import os
import time
import io
from markdown_pdf import MarkdownPdf, Section
import ydb
import uuid
import boto3

API_KEY = os.getenv('API_KEY')
BUCKET_NAME = os.getenv('BUCKET_NAME')
FOLDER_ID = os.getenv('FOLDER_ID')
YDB_ENDPOINT = os.getenv('YDB_ENDPOINT')
YDB_DATABASE = os.getenv('YDB_DATABASE')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

def recognize(audio_obj_key):
    file_uri = f"https://storage.yandexcloud.net/{BUCKET_NAME}/{audio_obj_key}"

    request_data = {
        "uri": file_uri,
        "recognitionModel": {
            "model": "general",
            "audioFormat": {
                "containerAudio": {
                    "containerAudioType": "MP3"
                }
            },
            "languageRestriction": {
                "restrictionType": "WHITELIST",
                "languageCode": ["ru-RU"]
            },
            "textNormalization": {
                "textNormalization": "TEXT_NORMALIZATION_ENABLED",
                "phoneFormattingMode": "PHONE_FORMATTING_MODE_DISABLED",
                "profanityFilter": False,
                "literatureText": True
            }
        },
        "speakerLabeling": {
            "speakerLabeling": "SPEAKER_LABELING_DISABLED"
        },
        "summarization": {
            "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
            "properties": [
                {
                    "instruction": "Ты - составитель конспектов. Проанализируй текст, полученный из аудиозаписи, и составь конспект. Текст должен быть хорошо структурирован и передавать максимально информации. Ответ выдай в Markdown формате. Минимум слов - 500. Ответ не должен быть в json формате или ещё в каком-то ином виде. Только Markdown. Начинай со второго уровня ##"
                }
            ]
        }
    }

    headers = {
        "Authorization": f"Api-key {API_KEY}",
        "x-folder-id": FOLDER_ID
    }

    response = requests.post(
        "https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync",
        headers=headers,
        json=request_data,
        verify=False
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Recognition request failed: {response.status_code}"
        )

    operation_data = response.json()
    operation_id = operation_data.get("id")
    if not operation_id:
        raise RuntimeError("Operation ID not found in response")

    print(f"Operation ID: {operation_id}")
    print("Waiting for recognition to complete...", end="", flush=True)

    operation_url = f"https://operation.api.cloud.yandex.net/operations/{operation_id}"

    while True:
        op_response = requests.get(operation_url, headers=headers, verify=False)

        if op_response.status_code != 200:
            print(f"\nOperation check failed: {op_response.status_code}")
            time.sleep(10)
            continue

        op_data = op_response.json()

        if op_data.get("done"):
            if "error" in op_data:
                raise RuntimeError(f"Operation failed:\n{json.dumps(op_data['error'], ensure_ascii=False, indent=2)}")
            break

        print("Waiting for result...")
        time.sleep(10)

    speech_response = requests.get(
        f"https://stt.api.cloud.yandex.net/stt/v3/getRecognition?operation_id={operation_id}",
        headers=headers,
        verify=False
    )

    print(f"\nSpeech Result {speech_response.status_code}")
    if speech_response.status_code != 200:
        raise RuntimeError(
            f"Result request failed: {speech_response.status_code}"
        )
    
    result = json.loads(speech_response.text.splitlines()[-1])

    return result['result']['summarization']['results'][0]['response']

def get_title_by_id(id: str):
    driver = ydb.Driver(
        endpoint=YDB_ENDPOINT,
        database=YDB_DATABASE,
        credentials=ydb.iam.MetadataUrlCredentials()
    )

    driver.wait(fail_fast=True, timeout=5)
    
    session = driver.table_client.session().create()

    query = """
        DECLARE $id AS Uuid;

        SELECT 
            id,
            title
        FROM tasks 
        WHERE id = $id;
    """

    params = {
        '$id': uuid.UUID(id),
    }

    prepared_query = session.prepare(query)

    result = session.transaction().execute(
        prepared_query,
        params,
        commit_tx=True
    )

    title = result[0].rows[0].title
    
    driver.stop()

    return title

def create_pdf_bytes(text, title) -> io.BytesIO:
    pdf = MarkdownPdf()

    md = f"# {title}\n\n{text}"

    pdf.add_section(Section(md))

    out = io.BytesIO()
    pdf.save_bytes(out)

    return out

def send_pdf_to_bucket(id, pdf_bytes: io.BytesIO):
    s3_client = boto3.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net',
        region_name='ru-central1',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    obj_key = f'temp/pdfs/{id}'

    pdf_bytes.seek(0)

    s3_client.upload_fileobj(
        pdf_bytes,
        BUCKET_NAME,
        obj_key,
        ExtraArgs={'ContentType': 'application/pdf'}
    )

    return obj_key

def update_task_status_to_completed(id):
    # try:
    driver = ydb.Driver(
        endpoint=YDB_ENDPOINT,
        database=YDB_DATABASE,
        credentials=ydb.iam.MetadataUrlCredentials()
    )

    driver.wait(fail_fast=True, timeout=5)

    session = driver.table_client.session().create()

    query = """
        DECLARE $id AS Uuid;
        DECLARE $status AS Utf8;
        
        UPDATE tasks
        SET status = $status
        WHERE id = $id
    """

    params = {
        '$id': uuid.UUID(id),
        '$status': 'completed'
    }

    prepared_query = session.prepare(query)

    session.transaction().execute(
        prepared_query,
        params,
        commit_tx=True
    )

    # finally:
    driver.stop()

def handler(event, context):
    for msg in event['messages']:
        body = json.loads(msg['details']['message']['body'])

        try:
            recognited_text = recognize(body['audio_obj_key'])
            title = get_title_by_id(body['id'])
            pdf_bytes = create_pdf_bytes(recognited_text, title)
            send_pdf_to_bucket(body['id'], pdf_bytes)
            update_task_status_to_completed(body['id'])
        except:
            return {"statusCode": 500}
        
    return {"statusCode": 200}