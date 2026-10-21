# Deploy to Azure Container Apps

Not deployed. These steps need an Azure subscription and run under your own account. Nothing here has been executed against Azure.

## What gets deployed

The `Dockerfile` image serves the treasury corpus (Strategy, BitMine, Coinbase) on port 8765. The bge-small query encoder is baked into the image. With `ANTHROPIC_API_KEY` set, cited answers come from `claude-haiku-5-5`; without it, they come from the model-free extractive fallback. Answers are capped at `FILING_ANSWERS_PER_MINUTE` (default 30) per replica, because a public URL spends API credit.

The server rejects requests whose `Host` header is not local. Set `FILING_ALLOWED_HOSTS` to the app's public hostname after the first deploy.

## Steps

```sh
RG=filing-research-rg
LOC=eastus
ACR=filingresearch$RANDOM          # must be globally unique, lowercase
ENV=filing-research-env
APP=filing-research

az login
az group create -n $RG -l $LOC
az acr create -g $RG -n $ACR --sku Basic
az acr build -r $ACR -t filing-research:v3 .      # builds in Azure; no local Docker needed

az containerapp env create -g $RG -n $ENV -l $LOC
az containerapp create -g $RG -n $APP --environment $ENV \
  --image $ACR.azurecr.io/filing-research:v3 --registry-server $ACR.azurecr.io \
  --target-port 8765 --ingress external \
  --cpu 1.0 --memory 2.0Gi --min-replicas 0 --max-replicas 1 \
  --secrets anthropic-key="<your key>" \
  --env-vars ANTHROPIC_API_KEY=secretref:anthropic-key FILING_ANSWERS_PER_MINUTE=10

FQDN=$(az containerapp show -g $RG -n $APP --query properties.configuration.ingress.fqdn -o tsv)
az containerapp update -g $RG -n $APP --set-env-vars FILING_ALLOWED_HOSTS=$FQDN
echo "https://$FQDN/"
```

## Check it

```sh
curl -s https://$FQDN/api/config | python3 -m json.tool | head
curl -s -X POST https://$FQDN/api/answer -H 'Content-Type: application/json' \
  -d '{"question":"How many bitcoins did Strategy hold as of July 24, 2026?","scope":{"company":"MSTR","accessions":["0001050446-26-000044"]}}'
```

`answer.provider` in `/api/config` should read `anthropic`. If it reads `extractive`, the key secret is not reaching the container.

## Cost and teardown

`--min-replicas 0` scales to zero when idle; the first request after idle waits for a cold start (image pull plus model load). At the measured token counts, Haiku 5.5 costs roughly $0.0003 per answered question at list price. Remove everything with `az group delete -n $RG`.
