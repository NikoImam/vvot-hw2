#!/bin/bash

set -e

event=$(cat)

body=$(echo "$event" | jq -r '.messages[0].details.message.body')
id=$(echo "$body" | jq -r '.id')
video_obj_key=$(echo "$body" | jq -r '.video_obj_key')

video_f="/tmp/video_$id"
audio_f="/tmp/audio_$id"

audio_obj_key="temp/audios/$id"

yc storage s3api get-object \
    --bucket "$BUCKET_NAME" \
    --key "$video_obj_key" \
    "$video_f" &>/dev/null

ffmpeg -i "$video_f" -vn -f mpeg -c:a libmp3lame -q:a 6 "$audio_f" &>/dev/null

yc storage s3api put-object \
    --body "$audio_f" \
    --bucket "$BUCKET_NAME" \
    --key "$audio_obj_key" \
    --content-type "audio/mpeg" &>/dev/null

rm -f "$video_f" "$audio_f"

q_msg_body="{\"id\": \"$id\", \"audio_obj_key\": \"$audio_obj_key\"}"

curl \
  --request POST \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'Action=SendMessage' \
  --data-urlencode "MessageBody=$q_msg_body" \
  --data-urlencode "QueueUrl=$RECOG_AUDIO_Q_URL" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
  --aws-sigv4 'aws:amz:ru-central1:sqs' \
  https://message-queue.api.cloud.yandex.net/ &>/dev/null

echo "{\"status_code\": 200}"
