# vvot-hw2

```shell
wget 'https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-linux-x64' -O backend/extract_audio/ffmpeg

chmod +x backend/extract_audio/ffmpeg
```

```shell
yc iam service-account create --name hw2-tf-sa

export TERR_SA_ID=$(yc iam service-account get hw2-tf-sa --format json | jq -r .id)

yc resource-manager folder add-access-binding $TF_VAR_folder_id --role admin --subject serviceAccount:$TERR_SA_ID

yc iam key create --output ~/.yc-keys/key.json --service-account-id $TERR_SA_ID

export YC_SERVICE_ACCOUNT_KEY_FILE=~/.yc-keys/key.json

source ./.bashrc
```

``` shell
export TF_VAR_cloud_id=<cloud_id>
export TF_VAR_folder_id=<folder_id>
export TF_VAR_prefix=<prefix>

cd ./terraform/
```
```shell
terraform init

terraform apply
```

```shell
terraform destroy
```