terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }

  required_version = ">= 0.13"
}

provider "yandex" {
  zone      = "ru-central1-d"
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
}

resource "yandex_iam_service_account" "sa" {
  name = "${var.prefix}-sa"
}

resource "yandex_resourcemanager_folder_iam_member" "ydb_editor" {
  folder_id = var.folder_id
  role      = "ydb.editor"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "kms_keys_encrypterDecrypter" {
  folder_id = var.folder_id
  role      = "kms.keys.encrypterDecrypter"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "lockbox_payloadViewer" {
  folder_id = var.folder_id
  role      = "lockbox.payloadViewer"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "storage_editor" {
  folder_id = var.folder_id
  role      = "storage.editor"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "ai_languageModels_user" {
  folder_id = var.folder_id
  role      = "ai.languageModels.user"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "functions_functionInvoker" {
  folder_id = var.folder_id
  role      = "functions.functionInvoker"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "ymq_admin" {
  folder_id = var.folder_id
  role      = "ymq.admin"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "editor" {
  folder_id = var.folder_id
  role      = "admin"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_iam_service_account_static_access_key" "sa_static_key" {
  service_account_id = yandex_iam_service_account.sa.id
}

resource "yandex_lockbox_secret" "secret" {
  name = "${var.prefix}-secret"
}

resource "yandex_lockbox_secret_version" "secret_version" {
  secret_id = yandex_lockbox_secret.secret.id

  entries {
    key        = "AWS_ACCESS_KEY_ID"
    text_value = yandex_iam_service_account_static_access_key.sa_static_key.access_key
  }

  entries {
    key        = "AWS_SECRET_ACCESS_KEY"
    text_value = yandex_iam_service_account_static_access_key.sa_static_key.secret_key
  }
}

resource "yandex_ydb_database_serverless" "db" {
  name      = "${var.prefix}-db"
  folder_id = var.folder_id
}

resource "yandex_ydb_table" "tasks-table" {
  path              = "tasks"
  connection_string = yandex_ydb_database_serverless.db.ydb_full_endpoint

  column {
    name     = "id"
    type     = "Uuid"
    not_null = true
  }

  column {
    name     = "created_at"
    type     = "Timestamp"
    not_null = true
  }

  column {
    name     = "title"
    type     = "Utf8"
    not_null = true
  }

  column {
    name     = "video_url"
    type     = "Utf8"
    not_null = true
  }

  column {
    name     = "status"
    type     = "Utf8"
    not_null = true
  }

  column {
    name     = "error_message"
    type     = "Utf8"
    not_null = false
  }

  primary_key = ["id"]

  depends_on = [
    yandex_ydb_database_serverless.db,
    yandex_resourcemanager_folder_iam_member.ydb_editor
  ]
}

resource "yandex_storage_bucket" "bucket" {
  bucket   = "${var.prefix}-bucket"
  max_size = 53e9

  lifecycle_rule {
    id      = "auto-expire"
    enabled = true

    expiration {
      days = 1
    }

    filter {
      prefix = "temp/"
    }
  }
}

resource "yandex_storage_object" "main_page" {
  bucket       = yandex_storage_bucket.bucket.bucket
  key          = "pages/index.html"
  source       = "../frontend/index.html"
  content_type = "text/html"
}

resource "yandex_storage_object" "tasks_page" {
  bucket       = yandex_storage_bucket.bucket.bucket
  key          = "pages/tasks/index.html"
  source       = "../frontend/tasks/index.html"
  content_type = "text/html"
}

data "archive_file" "create_task_func_zip" {
  type        = "zip"
  output_path = "./create_task_func.zip"

  source {
    content  = file("../backend/create_task/create_task.py")
    filename = "index.py"
  }

  source {
    content  = file("../backend/create_task/requirements.txt")
    filename = "requirements.txt"
  }
}

data "archive_file" "get_all_tasks_func_zip" {
  type        = "zip"
  output_path = "./get_all_tasks_func.zip"

  source {
    content  = file("../backend/get_all_tasks/get_all_tasks.py")
    filename = "index.py"
  }

  source {
    content  = file("../backend/get_all_tasks/requirements.txt")
    filename = "requirements.txt"
  }
}

data "archive_file" "check_n_download_func_zip" {
  type        = "zip"
  output_path = "./check_n_download_func.zip"

  source {
    content  = file("../backend/check_n_download/check_n_download.py")
    filename = "index.py"
  }

  source {
    content  = file("../backend/check_n_download/requirements.txt")
    filename = "requirements.txt"
  }
}

resource "yandex_message_queue" "check_url_n_download_video_q" {
  name                       = "${var.prefix}-check-url-download-video-q"
  fifo_queue                 = false
  message_retention_seconds  = 60 * 60 * 24
  visibility_timeout_seconds = 60 * 10

  access_key = yandex_iam_service_account_static_access_key.sa_static_key.access_key
  secret_key = yandex_iam_service_account_static_access_key.sa_static_key.secret_key

  depends_on = [
    yandex_resourcemanager_folder_iam_member.ymq_admin,
    yandex_iam_service_account_static_access_key.sa_static_key
  ]
}

data "yandex_message_queue" "check_url_n_download_video_q" {
  name       = yandex_message_queue.check_url_n_download_video_q.name
  access_key = yandex_iam_service_account_static_access_key.sa_static_key.access_key
  secret_key = yandex_iam_service_account_static_access_key.sa_static_key.secret_key

  depends_on = [yandex_message_queue.check_url_n_download_video_q]

}

resource "yandex_function" "create_task_func" {
  name               = "${var.prefix}-create-task"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = 512
  execution_timeout  = 30
  service_account_id = yandex_iam_service_account.sa.id
  user_hash          = "v1.0"

  content {
    zip_filename = data.archive_file.create_task_func_zip.output_path
  }

  environment = {
    YDB_ENDPOINT           = "grpcs://${yandex_ydb_database_serverless.db.ydb_api_endpoint}"
    YDB_DATABASE           = yandex_ydb_database_serverless.db.database_path
    CHECK_N_DOWNLOAD_Q_URL = data.yandex_message_queue.check_url_n_download_video_q.url
  }

  secrets {
    id                   = yandex_lockbox_secret.secret.id
    version_id           = yandex_lockbox_secret_version.secret_version.id
    key                  = "AWS_ACCESS_KEY_ID"
    environment_variable = "AWS_ACCESS_KEY_ID"
  }

  secrets {
    id                   = yandex_lockbox_secret.secret.id
    version_id           = yandex_lockbox_secret_version.secret_version.id
    key                  = "AWS_SECRET_ACCESS_KEY"
    environment_variable = "AWS_SECRET_ACCESS_KEY"
  }
}

resource "yandex_message_queue" "extract_audio_q" {
  name                       = "${var.prefix}-extract-audio-q"
  fifo_queue                 = false
  message_retention_seconds  = 60 * 60 * 24
  visibility_timeout_seconds = 60 * 60 * 1

  access_key = yandex_iam_service_account_static_access_key.sa_static_key.access_key
  secret_key = yandex_iam_service_account_static_access_key.sa_static_key.secret_key

  depends_on = [
    yandex_resourcemanager_folder_iam_member.ymq_admin,
    yandex_iam_service_account_static_access_key.sa_static_key
  ]
}

data "yandex_message_queue" "extract_audio_q" {
  name       = yandex_message_queue.extract_audio_q.name
  access_key = yandex_iam_service_account_static_access_key.sa_static_key.access_key
  secret_key = yandex_iam_service_account_static_access_key.sa_static_key.secret_key

  depends_on = [yandex_message_queue.extract_audio_q]
}

resource "yandex_function" "check_n_download_func" {
  name               = "${var.prefix}-check-n-download"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = 2048
  execution_timeout  = 30
  service_account_id = yandex_iam_service_account.sa.id
  user_hash          = "v1.0"

  content {
    zip_filename = data.archive_file.check_n_download_func_zip.output_path
  }

  environment = {
    YDB_ENDPOINT        = "grpcs://${yandex_ydb_database_serverless.db.ydb_api_endpoint}"
    YDB_DATABASE        = yandex_ydb_database_serverless.db.database_path
    BUCKET_NAME         = yandex_storage_bucket.bucket.bucket
    EXTRACT_AUDIO_Q_URL = data.yandex_message_queue.extract_audio_q.url
  }

  secrets {
    id                   = yandex_lockbox_secret.secret.id
    version_id           = yandex_lockbox_secret_version.secret_version.id
    key                  = "AWS_ACCESS_KEY_ID"
    environment_variable = "AWS_ACCESS_KEY_ID"
  }

  secrets {
    id                   = yandex_lockbox_secret.secret.id
    version_id           = yandex_lockbox_secret_version.secret_version.id
    key                  = "AWS_SECRET_ACCESS_KEY"
    environment_variable = "AWS_SECRET_ACCESS_KEY"
  }
}

resource "yandex_function_trigger" "check_url_n_download_video_trigger" {
  name      = "${var.prefix}-check-url-n-download-video-trigger"
  folder_id = var.folder_id

  message_queue {
    batch_cutoff       = 2
    queue_id           = yandex_message_queue.check_url_n_download_video_q.arn
    service_account_id = yandex_iam_service_account.sa.id
    batch_size         = 1
  }

  function {
    id                 = yandex_function.check_n_download_func.id
    service_account_id = yandex_iam_service_account.sa.id
  }

  depends_on = [yandex_message_queue.check_url_n_download_video_q]
}

resource "yandex_function" "get_all_tasks_func" {
  name               = "${var.prefix}-get-all-tasks"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = 512
  execution_timeout  = 30
  service_account_id = yandex_iam_service_account.sa.id
  user_hash          = "v1.0"

  content {
    zip_filename = data.archive_file.get_all_tasks_func_zip.output_path
  }

  environment = {
    YDB_ENDPOINT = "grpcs://${yandex_ydb_database_serverless.db.ydb_api_endpoint}"
    YDB_DATABASE = yandex_ydb_database_serverless.db.database_path
  }
}

resource "yandex_api_gateway" "api_gw" {
  name = "${var.prefix}-api-gw"

  execution_timeout = "30"

  spec = <<-EOT
openapi: 3.0.0
info:
  title: Sample API
  version: 1.0.0
paths:
  /:
    get:
      x-yc-apigateway-integration:
        bucket: ${yandex_storage_bucket.bucket.bucket}
        type: object_storage
        object: ${yandex_storage_object.main_page.key}
        service_account_id: ${yandex_iam_service_account.sa.id}
  
  /tasks:
    get:
      x-yc-apigateway-integration:
        bucket: ${yandex_storage_bucket.bucket.bucket}
        type: object_storage
        object: ${yandex_storage_object.tasks_page.key}
        service_account_id: ${yandex_iam_service_account.sa.id}
  
  /task/create:
    post:
      x-yc-apigateway-integration:
        payload_format_version: '0.1'
        function_id: ${yandex_function.create_task_func.id}
        tag: $latest
        type: cloud_functions
        service_account_id: ${yandex_iam_service_account.sa.id}

  /task/getAll:
    get:
      x-yc-apigateway-integration:
        payload_format_version: '0.1'
        function_id: ${yandex_function.get_all_tasks_func.id}
        tag: $latest
        type: cloud_functions
        service_account_id: ${yandex_iam_service_account.sa.id}
EOT  
}
