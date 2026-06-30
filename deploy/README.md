# Deploy — AWS Lightsail Containers

Deploys Label Check as a single container with a public HTTPS URL. The whole app
(FastAPI API + static frontend) is one image, so there's nothing else to wire up.

## One-time prerequisites

1. **Docker Desktop** — installed and running.
2. **AWS CLI v2** — configured with your credentials: `aws configure`
   (you'll need an IAM user/role with Lightsail permissions).
3. **Lightsail container plugin** (`lightsailctl`) — required by `push-container-image`:
   - macOS: `brew install aws/tap/lightsailctl`
   - Windows/Linux: see AWS docs for "Install lightsailctl".

## Deploy (one command)

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # your key — never written into the repo
./deploy/deploy.sh
```

The script builds the image for `linux/amd64` (Lightsail is x86_64), creates the
container service if needed, pushes the image, injects the key at deploy time via a
temporary file, deploys, waits for health checks, and prints the **live URL**.

Defaults (override with env vars): `SERVICE_NAME=label-check`, `REGION=us-east-1`,
`POWER=nano` (~$7/mo), `SCALE=1`, `ANTHROPIC_MODEL=claude-opus-4-8`.

## Manual steps (if you'd rather not use the script)

```bash
# 1. Build (force amd64 — important on Apple Silicon Macs)
docker build --platform linux/amd64 -t label-check:latest .

# 2. Create the service (one time)
aws lightsail create-container-service \
  --service-name label-check --power nano --scale 1 --region us-east-1
#    ...wait until state = READY:
aws lightsail get-container-services --service-name label-check --region us-east-1 \
  --query 'containerServices[0].state'

# 3. Push the image — note the printed reference, e.g. ":label-check.app.1"
aws lightsail push-container-image \
  --service-name label-check --label app --image label-check:latest --region us-east-1

# 4. Create deploy/containers.json from the template below, filling in the image
#    reference and your key. (This file is gitignored — keep the key out of git.)
# 5. Deploy
aws lightsail create-container-service-deployment --service-name label-check --region us-east-1 \
  --containers file://deploy/containers.json \
  --public-endpoint file://deploy/public-endpoint.json

# 6. Get the URL (once state = RUNNING)
aws lightsail get-container-services --service-name label-check --region us-east-1 \
  --query 'containerServices[0].url' --output text
```

`deploy/containers.json` template:

```json
{
  "app": {
    "image": ":label-check.app.1",
    "ports": { "8000": "HTTP" },
    "environment": {
      "EXTRACTION_BACKEND": "claude",
      "ANTHROPIC_API_KEY": "sk-ant-...",
      "ANTHROPIC_MODEL": "claude-opus-4-8"
    }
  }
}
```

## Verify the live deployment

```bash
curl https://<your-url>/api/health     # -> {"status":"ok","extraction_backend":"claude"}
```

Then open the URL in a browser and walk the test plan in `samples/README.md`.

## Cost & teardown

`nano` runs about **$7/month** while the service exists. To stop billing entirely:

```bash
aws lightsail delete-container-service --service-name label-check --region us-east-1
```

## Notes

- The API key is passed as a container environment variable. Lightsail stores it with the
  deployment config (visible to anyone with access to your AWS account). For a prototype
  this is fine; **rotate or delete the key after the demo** if you're cautious.
- For faster/cheaper extraction you can set `ANTHROPIC_MODEL` to a Sonnet-class model
  before deploying — it still comfortably meets the 5-second budget.
