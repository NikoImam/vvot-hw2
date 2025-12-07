# vvot-hw2

```shell
yc iam service-account create --name hw2-tf-sa

export TERR_SA_ID=$(yc iam service-account get hw2-tf-sa --format json | jq -r .id)

yc resource-manager folder add-access-binding $TF_VAR_folder_id --role admin --subject serviceAccount:$TERR_SA_ID

yc iam key create --output ~/.yc-keys/key.json --service-account-id $TERR_SA_ID

export YC_SERVICE_ACCOUNT_KEY_FILE=~/.yc-keys/key.json

source ./.bashrc
```

``` shell
cd ./terraform/
```
```shell
terraform init

terraform apply
```

```shell
terraform destroy
```