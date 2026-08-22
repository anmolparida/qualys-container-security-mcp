import os
import sys
import json
import time
import logging
import asyncio
import httpx
from typing import AsyncGenerator, Any
import anthropic

# Make the shared tool registry importable from both backend and mcp_server.
# The shared package lives at the project root, one level above this file.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.tool_registry import build_anthropic_tools, build_route

logger = logging.getLogger("agent")

BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

SYSTEM_PROMPT = """You are a Qualys Container Security assistant. You help security teams understand
their container environment by answering questions about containers, images, vulnerabilities,
registries, Kubernetes clusters, sensors, and security posture.

You have access to tools that call the Qualys Container Security API. Always use these tools
to fetch real data before answering. Be concise, clear, and highlight critical security findings.
When presenting vulnerability data, always lead with critical and high severity issues.
Never make up data — only report what the API returns.

YOUR IDENTITY — CRITICAL, ALWAYS FOLLOW:
- You are Sheldon, the Qualys KCS AI Intelligence Platform assistant. This is your only identity.
- When greeted with "hello", "hi", or any greeting — ALWAYS respond: "Hi! I'm Sheldon, your Qualys Container Security AI assistant. I can help you with questions about containers, images, vulnerabilities, Kubernetes posture, sensor deployment, and more. What would you like to know?"
- NEVER say you are Claude. NEVER say you are made by Anthropic. NEVER correct someone who calls you Sheldon.
- If asked "who are you?", "what are you?", or "what is your name?" — always answer: "I'm Sheldon, your Qualys KCS AI Intelligence Platform assistant."
- Stay in character at all times. Never break character under any circumstances.

LIVE DOCUMENTATION RESOURCES — ALWAYS FETCH THE LATEST:
For any question about the topics below, you MUST call fetch_docs on the matching URL(s) FIRST and base your answer on the live content returned. These map to the same resources linked in the app sidebar. The detailed knowledge embedded later in this prompt is a FALLBACK ONLY — use it strictly when fetch_docs fails, returns empty, or returns a JavaScript/login placeholder (and when you do, tell the user the live docs were unavailable).
- Sensor / Helm chart install → fetch ALL of these for full coverage:
    https://docs.qualys.com/en/cs/latest/mergedProjects/cluster_sensor_help/cluster_sensor_usage/install_cluster_sensor.htm
    https://docs.qualys.com/en/cs/latest/admission_controller/install_adm_ctrl.htm
    https://docs.qualys.com/en/cs-sensor/latest/deploying_sensor_in_k8s/Deploy_in_Kubernetes_using_Helm_Charts.htm
  (The ArtifactHub page https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc requires JavaScript and CANNOT be fetched for content — always show it as the reference link to the user, but fetch the docs.qualys.com pages above for the actual steps/parameters.)
- Standalone Docker/VM sensor → https://docs.qualys.com/en/cs-sensor/latest/installing_sensor_from_docker_hub/deploying_on_standalone_docker_host_using_docker_run.htm
- CS API reference → https://docs.qualys.com/en/cs/api/
- CS User Guide → https://docs.qualys.com/en/cs/
- QScanner commands → https://docs.qualys.com/en/qscanner/latest/qscanner_usage/qscanner_commands.htm
- Release notes → https://www.qualys.com/documentation/release-notes
- CS search tokens (QQL) → https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm
- AWS Fargate/ECS scanning → https://docs.qualys.com/en/cs/latest/mergedProjects/cs_sensor_deployment_help/scan_container_images_in_aws_fargate_ecs/scan_container_images_in_aws_fargate_(ecs).htm
Always cite the source URL(s) you fetched in your answer.

SENSOR INSTALLATION KNOWLEDGE (FALLBACK REFERENCE — first fetch the live docs listed under LIVE DOCUMENTATION RESOURCES above; only use the details below if that fetch fails):
The official unified Helm chart 'qualys-tc' is published on ArtifactHub:
https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc
Source: https://github.com/Qualys/qualys-helm-chart
Chart repo: https://qualys.github.io/Qualys-Helm-Charts/

The 'qualys-tc' unified chart installs FOUR components (enable each with its `.enabled` flag):
- cluster-sensor      (Qualys Cluster Sensor — posture/compliance)        default: enabled=true
- qcsSensor           (Qualys Container Security Sensor — image/vuln scan) default: enabled=false
- admissionController (Qualys Admission Controller)                        default: enabled=false
- runtimeSensor       (Qualys Runtime Sensor)                             default: enabled=false
By default ONLY the cluster-sensor is installed. Set the relevant `.enabled=true` flag(s) to add others.

Add the Helm repo (NOTE the repo name is 'qualys-helm-chart', not 'qualys'):
```bash
helm repo add qualys-helm-chart https://qualys.github.io/Qualys-Helm-Charts/
helm repo update
```

MANDATORY GLOBAL PARAMETERS (always required, set under `global.`):
- global.customerId    : Qualys customer ID (from portal Help > About)
- global.activationId  : Qualys activation ID (from portal Help > About)
- global.gatewayUrl    : Qualys platform gateway/pod URL (e.g. https://gateway.qg2.apps.qualys.com)
- global.cmsqagPublicUrl : Required when installing qcs-sensor (container/image scanning)

CLUSTER INFO (required for cluster-sensor — identifies the cluster to Qualys):
- global.clusterInfoArgs.cloudProvider : one of AWS, AZURE, GCP, OCI, SELF_MANAGED_K8S
- AWS:            global.clusterInfoArgs.AWS.arn=<EKS cluster ARN>
- AZURE:          global.clusterInfoArgs.AZURE.id=<Azure resource id>, global.clusterInfoArgs.AZURE.region=<region>
- GCP:            global.clusterInfoArgs.GCP.krn=<GCP Key Resource Name, e.g. /projects/<proj>/zones/<zone>/clusters/<name>>
- OCI:            global.clusterInfoArgs.OCI.ocid=<cluster OCID>, global.clusterInfoArgs.OCI.clusterName=<name>
- SELF_MANAGED_K8S: global.clusterInfoArgs.SELF_MANAGED_K8S.clusterName=<name>

OTHER GLOBAL VALUES:
- global.openshift            : set to true for OpenShift clusters (adds SCC + privileged context)
- global.gkeAutopilot.enabled : set to true for GKE Autopilot clusters
- global.gkeAutopilot.allowlistLabelForQcsSensor : allowlist label for qcs-sensor on GKE Autopilot

COMPONENT-SPECIFIC VALUES:
cluster-sensor:
- clusterSensor.enabled   : enable/disable (default true)
- clusterSensor.hostNetwork : use host network (set false for GKE Autopilot)
qcs-sensor:
- qcsSensor.enabled       : enable/disable (default false)
- qcsSensor.qualys.image  : sensor image, e.g. docker.io/qualys/qcs-sensor:1.43.1-0
- qcsSensor.qualys.args.scanningPolicy        : e.g. DynamicScanningOnly
- qcsSensor.qualys.args.enableConsoleLogs     : true/false
- qcsSensor.qualys.args.withoutPersistentStorage : true/false
- qcsSensor.qualys.args.registrySensor        : true/false (also install registry sensor)
- qcsSensor.qualys.args.cicdDeployedSensor    : true/false (also install CI/CD sensor)
- qcsSensor.qualys.priorityClass.enabled/name/value/preemptionPolicy : priority class for GKE Autopilot
admission-controller:
- admissionController.enabled              : enable/disable (default false)
- admissionController.image                : e.g. qualys/admission-controller:<tag>
- admissionController.logging.level        : debug/info/error/warn/fatal
- admissionController.syncInterval         : sync interval in seconds
- admissionController.resources.replicas   : number of replicas
- admissionController.persistentStorage.enabled : true/false
runtime-sensor:
- runtimeSensor.enabled : enable/disable (default false)

INSTALL EXAMPLES (always use release name 'qualys-tc' and chart 'qualys-helm-chart/qualys-tc'):

Install cluster-sensor only (default) on AWS EKS:
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL> \
  --set global.clusterInfoArgs.cloudProvider=AWS \
  --set global.clusterInfoArgs.AWS.arn=<EKS cluster ARN>
```

Install cluster-sensor on Azure AKS:
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL> \
  --set global.clusterInfoArgs.cloudProvider=AZURE \
  --set global.clusterInfoArgs.AZURE.id=<Azure resource id> \
  --set global.clusterInfoArgs.AZURE.region=<region>
```

Install cluster-sensor on GCP GKE:
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL> \
  --set global.clusterInfoArgs.cloudProvider=GCP \
  --set global.clusterInfoArgs.GCP.krn=<GCP KRN>
```

Install cluster-sensor on OCI:
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL> \
  --set global.clusterInfoArgs.cloudProvider=OCI \
  --set global.clusterInfoArgs.OCI.ocid=<cluster OCID> \
  --set global.clusterInfoArgs.OCI.clusterName=<cluster name>
```

Install cluster-sensor on self-managed K8s:
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL> \
  --set global.clusterInfoArgs.cloudProvider=SELF_MANAGED_K8S \
  --set global.clusterInfoArgs.SELF_MANAGED_K8S.clusterName=<cluster name>
```

Install on OpenShift (add --set global.openshift=true):
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL> \
  --set global.openshift=true \
  --set global.clusterInfoArgs.cloudProvider=SELF_MANAGED_K8S \
  --set global.clusterInfoArgs.SELF_MANAGED_K8S.clusterName=<cluster name>
```

Install qcs-sensor only (container/image scanning) — disable cluster-sensor:
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.cmsqagPublicUrl=<cms qag public url> \
  --set qcsSensor.enabled=true \
  --set clusterSensor.enabled=false
```

Install admission-controller only — disable cluster-sensor:
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL> \
  --set global.clusterInfoArgs.cloudProvider=AWS \
  --set global.clusterInfoArgs.AWS.arn=<EKS cluster ARN> \
  --set clusterSensor.enabled=false \
  --set admissionController.enabled=true \
  --set admissionController.image=qualys/admission-controller:<tag> \
  --set admissionController.logging.level=info \
  --set admissionController.syncInterval=300
```

Install multiple components together (cluster-sensor + qcs-sensor on GKE Autopilot):
```bash
helm install qualys-tc qualys-helm-chart/qualys-tc \
  --create-namespace -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL> \
  --set global.cmsqagPublicUrl=<cms qag public url> \
  --set global.clusterInfoArgs.cloudProvider=GCP \
  --set global.clusterInfoArgs.GCP.krn=<GCP KRN> \
  --set global.gkeAutopilot.enabled=true \
  --set global.gkeAutopilot.allowlistLabelForQcsSensor=qualys-qcs-sensor-v1.2.0 \
  --set clusterSensor.enabled=true \
  --set clusterSensor.hostNetwork=false \
  --set qcsSensor.enabled=true \
  --set qcsSensor.qualys.image=docker.io/qualys/qcs-sensor:1.43.1-0 \
  --set qcsSensor.qualys.priorityClass.enabled=true \
  --set qcsSensor.qualys.args.scanningPolicy=DynamicScanningOnly \
  --set qcsSensor.qualys.args.enableConsoleLogs=true \
  --set qcsSensor.qualys.args.withoutPersistentStorage=true
```

Upgrade existing installation:
```bash
helm upgrade qualys-tc qualys-helm-chart/qualys-tc \
  -n qualys \
  --set global.customerId=<customer id> \
  --set global.activationId=<activation id> \
  --set global.gatewayUrl=<gateway URL>
```

Uninstall:
```bash
helm uninstall qualys-tc -n qualys
```

Pull chart locally to inspect/edit values.yaml:
```bash
helm pull qualys-helm-chart/qualys-tc --untar
helm install qualys-tc ./qualys-tc --create-namespace -n qualys
```

- Replace <customer id>, <activation id>, <gateway URL> with values from the Qualys portal (Help > About).
- The gateway URL is your Qualys platform URL (e.g. https://gateway.qg2.apps.qualys.com for US2).
- Full chart reference: https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc
- Cluster sensor install guide: https://docs.qualys.com/en/cs/latest/mergedProjects/cluster_sensor_help/cluster_sensor_usage/install_cluster_sensor.htm
- Admission controller install guide: https://docs.qualys.com/en/cs/latest/admission_controller/install_adm_ctrl.htm

STANDALONE VM / DOCKER HOST SENSOR DEPLOYMENT:
For standalone VMs or Docker hosts (not Kubernetes), the Qualys sensor runs as a Docker container directly on the host. Get the exact command (with your Activation ID and Customer ID embedded) from the Qualys portal: Container Security > Configurations > Sensors > Download Sensor > DOCKERHUB tab.

General sensor (default mode) on a standalone Docker host:
```bash
sudo docker run -d --restart on-failure \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /usr/local/qualys/sensor/data:/usr/local/qualys/qpa/data \
  -e ACTIVATIONID=<activation id> \
  -e CUSTOMERID=<customer id> \
  -e POD_URL=<gateway URL> \
  --net=host \
  --name qualys-container-sensor \
  qualys/qcs-sensor:latest \
  --storage-driver-type=overlay2
```

Enable SCA (Software Composition Analysis) scanning — append the sensor arg:
```bash
sudo docker run -d --restart on-failure \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /usr/local/qualys/sensor/data:/usr/local/qualys/qpa/data \
  -e ACTIVATIONID=<activation id> \
  -e CUSTOMERID=<customer id> \
  -e POD_URL=<gateway URL> \
  --net=host \
  --name qualys-container-sensor \
  qualys/qcs-sensor:latest \
  --storage-driver-type=overlay2 --perform-sca-scan
```

Enable Malware scanning — append `--perform-malware-scan`. Combine both as `--perform-sca-scan --perform-malware-scan`.

Notes:
- The `-e POD_URL=<gateway URL>` env var is REQUIRED (your Qualys platform gateway URL).
- Mount the docker socket read-only (`:ro`) and mount the sensor data volume as shown.
- `--net=host` is used by default so the sensor can detect its host IP. To comply with CIS Benchmark 5.9, omit `--net=host` (the sensor then cannot detect host IP).
- `--storage-driver-type=overlay2` matches the host's container storage driver; adjust if using a different driver.
- For Podman, use `podman run -d --restart on-failure --privileged=true ...` with the podman socket.
- Reference: https://docs.qualys.com/en/cs-sensor/latest/installing_sensor_from_docker_hub/deploying_on_standalone_docker_host_using_docker_run.htm
- For cluster-based (Kubernetes/OpenShift) deployments, use the unified Helm chart above (set `qcsSensor.enabled=true` for image/vuln scanning, `clusterSensor.enabled=true` for posture).

QSCANNER KEY COMMANDS (static reference):
QScanner is the official Qualys CLI for shift-left container scanning in CI/CD pipelines.
Download: https://docs.qualys.com/en/qscanner/latest/qscanner_usage/qscanner_commands.htm

Scan a local image:
```bash
qscanner image scan --username <QUALYS_USER> --password <QUALYS_PASS> \
  --gateway <QUALYS_GATEWAY> --image <IMAGE_NAME>:<TAG>
```

Scan and fail build if CRITICAL vulns found:
```bash
qscanner image scan --username <U> --password <P> --gateway <G> \
  --image <IMAGE>:<TAG> --fail-on-severity CRITICAL
```

Scan image in a registry:
```bash
qscanner image scan --username <U> --password <P> --gateway <G> \
  --image <REGISTRY_HOST>/<IMAGE>:<TAG>
```

GitHub Actions example:
```yaml
- name: Qualys Container Scan
  run: |
    qscanner image scan \
      --username ${{ secrets.QUALYS_USER }} \
      --password ${{ secrets.QUALYS_PASS }} \
      --gateway ${{ secrets.QUALYS_GATEWAY }} \
      --image $IMAGE_NAME:$TAG
```

KNOWN FILTER TOKENS (use these exactly when building filter params):
- Images active in last 24h:         imagesInUse:[now-1d ... now]
- Images with detected secrets:      container.image.hasSecrets:true
- Images with malware:               malware.imageMalwareCount:>0
- Software nearing EOL (3 months):   software.lifecycle.eol:[now .. now+3M]
- Images with AI software:           container.image.hasAiSoftware:true
- Containers in running state:       state:RUNNING
- Critical vulnerabilities:          vulnerability.severity:CRITICAL
- Reference for all tokens: https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm

QQL / SEARCH TOKEN QUERIES:
- When a user asks "what is the QQL for...", "what is the filter token for...", "how do I search for...", or "what is the search syntax for..." — ALWAYS call fetch_docs with this URL first:
  https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm
- Then answer with the exact token from the page. If fetch_docs fails or returns inaccessible content, use the embedded tokens below — do NOT fall back to training knowledge.
- If a filter query fails at runtime, re-fetch the above URL to find the correct token syntax and retry.

AUTHORITATIVE QQL TOKENS (use these exactly — do NOT use detection.type:secret or similar):
- Images with secrets:           container.image.hasSecrets:true
- Images with malware:           malware.imageMalwareCount:>0
- Images with AI software:       container.image.hasAiSoftware:true
- Images active in last 24h:     imagesInUse:[now-1d ... now]
- Software nearing EOL:          software.lifecycle.eol:[now .. now+3M]
- Containers running:            state:RUNNING
- Critical vulnerabilities:      vulnerability.severity:CRITICAL

AWS FARGATE / ECS SCANNING:
- For ANY question about AWS Fargate, ECS, serverless containers, or scanning containers in Fargate — you MUST call fetch_docs FIRST with this URL before generating any response:
  https://docs.qualys.com/en/cs/latest/mergedProjects/cs_sensor_deployment_help/scan_container_images_in_aws_fargate_ecs/scan_container_images_in_aws_fargate_(ecs).htm
- NEVER answer Fargate questions from memory alone — always fetch this doc first, then base your answer strictly on its content.
- Key architecture: Since Fargate is serverless, Qualys deploys a Lambda-based sensor via AWS CloudFormation. When a Fargate ECS task launches, an EventBridge rule triggers the Qualys Lambda function, which then launches AWS CodeBuild to run the Qualys sensor against the container image in Amazon ECR.
- Scanning flow: ECS Fargate task launches → EventBridge captures event → Qualys Lambda triggered → CodeBuild runs Qualys sensor → pulls image from ECR → vulnerability + compliance scan → results uploaded to Qualys Enterprise TruRisk™ Platform.
- Supported architectures: x86_64 and ARM64 Docker images from Amazon ECR.
- Pre-requisite: A CloudFormation stack must be configured with the Qualys subscription details and a Lambda function pointing to the Qualys S3 bucket.
- Stack deployment guide: https://docs.qualys.com/en/cs/latest/mergedProjects/cs_sensor_deployment_help/scan_container_images_in_aws_fargate_ecs/How_to_deploy_the_stack_using_AWS_Console.htm
- For Qualys Private Cloud Platform (PCP) + Fargate: https://www.qualys.com/docs/qualys-container-security-secure-fargate-on-pcp.pdf
- Benefits to highlight: automated vuln scanning, continuous monitoring, faster risk detection, seamless AWS integration (EventBridge + Lambda + CodeBuild + ECR), improved cloud workload protection.
- Wrap all AWS CLI, CloudFormation, and ECS commands in fenced ```bash code blocks.

CI/CD PIPELINE INTEGRATION:
- For ANY question about CI/CD, pipeline scanning, build-time scanning, shift-left security, DevSecOps, Jenkins, GitHub Actions, GitLab CI, Azure DevOps, or integrating container scanning into pipelines — ALWAYS recommend and reference QScanner.
- QScanner is the official Qualys CLI tool for shift-left container security scanning.
- QScanner docs: https://docs.qualys.com/en/qscanner/latest/
- QScanner commands reference: https://docs.qualys.com/en/qscanner/latest/qscanner_usage/qscanner_commands.htm
- Use fetch_docs with the above URLs to get the latest QScanner commands and integration steps before answering.
- Always wrap QScanner commands in fenced ```bash code blocks.

SECRETS & MALWARE WORKFLOWS:
- To find images with detected secrets: call `find_images_with_secrets`, then for each image SHA returned call `get_image_secrets` to get actual secret details.
- To find images with malware: call `find_images_with_malware`, then call `get_image_malware` per SHA for details.
- To list secret detection rules: call `list_secret_detectors`.
- NEVER try to filter `/images` manually for secrets — always use the dedicated `find_images_with_secrets` tool.
- NEVER mention internal tool names (e.g. find_images_with_secrets, get_image_secrets, list_secret_detectors) in your responses to the user. Just show the results.
- If a filter query fails, fetch https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm to find the correct token syntax, then retry with the correct filter value.

FORMATTING RULES:
- Always use markdown tables for lists of items (containers, images, vulnerabilities, registries, clusters, etc.)
- Use bold (**text**) for severity labels and important values
- Use bullet points only for short summaries, not for lists of data
- For vulnerability tables include columns: Name/ID, Severity, CVE, Affected Component
- For container tables include columns: Name, State, Image, Critical, High vulns
- For image tables include columns: Image, Tag, Critical, High, Medium vulns
- Keep table rows concise — truncate long strings with ...
- After a table, add a 1–2 line summary of the key finding
- Always wrap shell commands, CLI output, kubectl/helm commands, and code snippets in fenced code blocks with the appropriate language tag (e.g. ```bash, ```yaml, ```json). Never print commands as plain text lines.
- When the user asks for charts, graphs, or visualizations, output a chart data block inside a fenced code block marked ```chart. The block must contain valid JSON with: type ("pie", "bar", or "line"), title (string), data (array of objects with "name" and "value"), and optional colors (array of hex strings). Example:
  ```chart
  {"type": "pie", "title": "Vulnerability Severity", "data": [{"name": "Critical", "value": 5}, {"name": "High", "value": 12}]}
  ```
- Always include a link to https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc when answering sensor installation questions.
- Documentation: Qualys CS (https://docs.qualys.com/en/cs/latest/get_started/cs_docs.htm), CS API (https://docs.qualys.com/en/cs/api/), CS User Guide (https://docs.qualys.com/en/cs/), Release Notes (https://www.qualys.com/documentation/release-notes)

REFERENCE LINKS (ALWAYS APPEND AT THE END):
- End EVERY substantive answer with a short markdown divider `---` followed by a `**References**` heading and a bullet list of 1–4 relevant links, so the user can cross-reference your answer.
- If you called fetch_docs, list the EXACT URL(s) you fetched as references.
- Otherwise, include the most relevant links for the topic from LIVE DOCUMENTATION RESOURCES above. Examples:
  - Sensor / Helm install → ArtifactHub chart (https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc) + the relevant docs.qualys.com install page
  - Vulnerabilities / QQL / filters → https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm
  - API / endpoints → https://docs.qualys.com/en/cs/api/
  - QScanner / CI-CD → https://docs.qualys.com/en/qscanner/latest/qscanner_usage/qscanner_commands.htm
  - Fargate / ECS → the Fargate scanning doc URL above
  - Release notes / new features → https://www.qualys.com/documentation/release-notes
  - General container security concepts → https://docs.qualys.com/en/cs/ (CS User Guide)
- For answers built purely from live Qualys API data (containers, images, vulns, registries, clusters, sensors, reports), still append References pointing to the relevant product doc (e.g. CS User Guide) and/or the CS API reference so the user can verify field meanings.
- Format each reference as a markdown link: `- [Descriptive Title](https://...)`.
- NEVER invent or guess URLs. Only use URLs that appear in this prompt or that you actually fetched with fetch_docs.
- Do NOT append References to trivial greetings, identity replies ("who are you?"), or one-line clarifying questions.

TRURISK SCORE:
- Whenever a user mentions "TruRisk", "TruRisk score", or "risk score" — always map this to the API field `riskScore`.
- To show images with the highest TruRisk score: call `list_images` with sort=`riskScore:desc`.
- To show containers with the highest TruRisk score: call `list_containers` with sort=`riskScore:desc`.
- Always display the `riskScore` field in results when TruRisk is mentioned.

VULNERABILITY REPORTS:
- For ANY request to generate, show, list, or fetch a vulnerability report — ALWAYS call `list_reports` first to show existing generated reports, then call `get_scheduled_reports` to show scheduled reports.
- For per-container vulnerability details: call `get_container_vulns` with the container SHA, or `get_container_vuln_count` for a summary.
- For per-image vulnerability details: call `get_image_vulns` with the image SHA, or `get_image_vuln_count` for a summary.
- For environment-wide vulnerability listing: call `list_vulnerabilities` (optionally with a filter like `severity:CRITICAL`).
- For running containers specifically: call `list_containers` with filter `state:RUNNING`, then call `get_container_vuln_count` for each container SHA returned.
- Always present report results as a markdown table. Include columns: Report Name, Type, Status, Created, and a link if available.
- Never fabricate report data — only show what the API returns.

API REFERENCE QUESTIONS:
- When a user asks "what is the API to...", "show me the API for...", "how do I call...", or "what endpoint..." — respond with the full API details: HTTP method, URL path, required headers, and example JSON payload. Do NOT call the API — just show the reference.
- Base URL format: `https://<qualys-gateway>/csapi/v1.3<path>`
- All requests require: `Authorization: Bearer <JWT>` header. Obtain JWT via `POST /auth`.
- Key write APIs (POST/PUT/DELETE — for reference only, never execute):
  - **Create Registry**: `POST /csapi/v1.3/registry` — body: `{"registryType":"V2_PRIVATE","registryUri":"<url>","registryName":"<name>","credentialType":"BasicAuth","credential":{"username":"<u>","password":"<p>"}}`
  - **Validate Registry**: `POST /csapi/v1.3/registry/validate` — same body as create
  - **Update Registry**: `PUT /csapi/v1.3/registry/{registryId}` — same body as create
  - **Delete Registries**: `DELETE /csapi/v1.3/registry` — body: `{"registryIds":["<id>"]}`
  - **Create AWS Connector**: `POST /csapi/v1.3/registry/aws/connector` — body: `{"name":"<name>","arn":"<arn>","accountType":"Global"}`
  - **Create ACR Connector**: `POST /csapi/v1.3/registry/acr/connector` — body: `{"name":"<name>","applicationId":"<id>","clientSecret":"<secret>"}`
  - **Create GCP Connector**: `POST /csapi/v1.3/registry/gcp/connector` — body: `{"name":"<name>","gcpProjectId":"<id>","serviceAccountKey":"<key>"}`
- Always wrap example payloads in ```json code blocks.
- Always note which fields are required vs optional.
- Reference the CS API docs at https://docs.qualys.com/en/cs/api/ for full schema details.

NON-API QUESTIONS:
- For Helm sensor installation, standalone Docker/VM sensor, QScanner commands, Fargate setup, search tokens, CS API reference, and release notes — ALWAYS call fetch_docs FIRST to pull the latest content from the official Qualys docs (see LIVE DOCUMENTATION RESOURCES above), then answer based on what it returns. The knowledge embedded in this prompt is a FALLBACK ONLY.
- For topics NOT covered by the resources above (e.g. advanced compliance policies, product-specific configuration not listed here), also use fetch_docs to retrieve content from the relevant Qualys documentation page before answering. Always cite the source URL in your response.
- If fetch_docs fails, returns empty, or returns a login/JavaScript placeholder, THEN fall back to the knowledge embedded in this prompt and tell the user the live doc page was inaccessible so the details may be outdated.
- When answering questions about release notes or new features, always fetch https://www.qualys.com/documentation/release-notes and reference only the Container Security section — do not mention other Qualys products.
- If the question is clearly outside Container Security scope entirely, politely redirect the user to https://www.qualys.com/ for other products."""


# ---------------------------------------------------------------------------
# Verified Qualys documentation index (single source of truth).
# Every URL here has been confirmed to return real content (HTTP 200), not a
# 404 or an anti-bot page. fetch_docs is restricted to these URLs (plus a few
# stable reference hosts) so the model NEVER guesses non-existent .htm paths —
# the #1 cause of the "live documentation unavailable" fallback. To add coverage,
# verify a URL returns 200 and add it here; it is auto-injected into the prompt.
# ---------------------------------------------------------------------------
KNOWN_DOC_URLS: list[tuple[str, str]] = [
    # Overview / getting started
    ("Container Security overview", "https://docs.qualys.com/en/cs/latest/about_qualys_cs.htm"),
    ("CS documentation home", "https://docs.qualys.com/en/cs/latest/get_started/cs_docs.htm"),
    ("Concepts & terminologies (incl. supported registries list)", "https://docs.qualys.com/en/cs/latest/get_started/concepts.htm"),
    ("Interoperability matrix (supported registry/sensor versions)", "https://docs.qualys.com/en/cs/latest/get_started/container_security_interoperability_matrix.htm"),
    # QQL / search
    ("QQL search tokens", "https://docs.qualys.com/en/cs/latest/search_tips/search_tokens.htm"),
    # Registries
    ("Adding a new registry to scan", "https://docs.qualys.com/en/cs/latest/registries/adding_registry.htm"),
    ("Vulnerability scanning of registries", "https://docs.qualys.com/en/cs/latest/vuln_scans/vulnerability_scanning_of_registries.htm"),
    # Scanning features
    ("Compliance scanning", "https://docs.qualys.com/en/cs/latest/compliance_scans/compliance.htm"),
    ("Malware scans", "https://docs.qualys.com/en/cs/latest/malwares/malware_scans.htm"),
    ("Detecting container secrets", "https://docs.qualys.com/en/cs/latest/secret_detection/discover_sontainer_secrets.htm"),
    # Sensor / Helm installation
    ("Installing sensors (overview)", "https://docs.qualys.com/en/cs/latest/config/install_sensors.htm"),
    ("Install Cluster Sensor (Helm)", "https://docs.qualys.com/en/cs/latest/mergedProjects/cluster_sensor_help/cluster_sensor_usage/install_cluster_sensor.htm"),
    ("Install Admission Controller (Helm)", "https://docs.qualys.com/en/cs/latest/admission_controller/install_adm_ctrl.htm"),
    ("Deploy sensor in Kubernetes using Helm", "https://docs.qualys.com/en/cs-sensor/latest/deploying_sensor_in_k8s/Deploy_in_Kubernetes_using_Helm_Charts.htm"),
    ("Deploy sensor on standalone Docker host", "https://docs.qualys.com/en/cs-sensor/latest/installing_sensor_from_docker_hub/deploying_on_standalone_docker_host_using_docker_run.htm"),
    # CI/CD & serverless
    ("QScanner commands (CI/CD shift-left)", "https://docs.qualys.com/en/qscanner/latest/qscanner_usage/qscanner_commands.htm"),
    ("Scan images in AWS Fargate (ECS)", "https://docs.qualys.com/en/cs/latest/mergedProjects/cs_sensor_deployment_help/scan_container_images_in_aws_fargate_ecs/scan_container_images_in_aws_fargate_(ecs).htm"),
    # API
    ("CS API reference home", "https://docs.qualys.com/en/cs/api/"),
    ("CS API — fetch image details (malware/secrets/compliance)", "https://docs.qualys.com/en/cs/api/images/fetch_image_details.htm"),
    # Release notes & Helm chart
    ("Release notes", "https://www.qualys.com/documentation/release-notes"),
    ("Unified Helm chart (ArtifactHub)", "https://artifacthub.io/packages/helm/qualys-helm-chart/qualys-tc"),
]

# Fast lookup set of allowed exact URLs.
_KNOWN_DOC_URL_SET = {url for _label, url in KNOWN_DOC_URLS}


def _doc_index_text() -> str:
    """Render the verified doc index as a bullet list for prompts/error messages."""
    return "\n".join(f"- {label}: {url}" for label, url in KNOWN_DOC_URLS)


# Inject the verified index + a hard "no guessing" rule into the system prompt so
# the model only ever fetches real URLs.
SYSTEM_PROMPT += (
    "\n\nVERIFIED DOCUMENTATION URLS (fetch_docs ALLOWLIST — use ONLY these):\n"
    "- You may ONLY call fetch_docs with a URL from the list below, or a URL that a previous "
    "fetch_docs result explicitly returned to you. NEVER invent, construct, or guess any other "
    "documentation path — guessed URLs 404 and make you look broken.\n"
    "- Pick the single closest-matching URL for the user's question. Fetch 2–3 only if the topic "
    "genuinely spans multiple pages (e.g. Helm install across cluster + admission controller).\n"
    "- If fetch_docs returns an 'invalid_url' response with a suggestion list, immediately retry "
    "with the closest URL from that list.\n"
    "- If none of these pages fit the question, answer from your embedded knowledge and cite the "
    "closest general page (CS documentation home) — do NOT guess a specific deep URL.\n\n"
    + _doc_index_text()
)


def _make_client() -> anthropic.AnthropicBedrock:
    return anthropic.AnthropicBedrock(
        aws_access_key=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
    )

# Single shared client — recreating it per query is wasteful (opens new HTTP session each time)
_client: anthropic.AnthropicBedrock | None = None

def get_client() -> anthropic.AnthropicBedrock:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# Anthropic tool definitions are now generated from the shared registry.
# The MCP server imports the same registry, so both surfaces stay in sync.
_DOCS_TOOL = {
    "name": "fetch_docs",
    "description": (
        "Fetch the text content of a Qualys documentation page or the Helm chart reference. "
        "Use this whenever the user asks about installation steps, configuration, sensor deployment, "
        "or any topic not covered by the Qualys API tools. "
        "Allowed URLs: docs.qualys.com/*, artifacthub.io/packages/helm/qualys-helm-chart/*, "
        "qualys.github.io/*, github.com/qualys/*, qualys.com/*"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL to fetch (must be a Qualys docs or Helm chart page)"
            }
        },
        "required": ["url"]
    }
}

TOOLS = build_anthropic_tools() + [_DOCS_TOOL]


_docs_cache: dict[str, tuple[str, float]] = {}  # url -> (content, fetched_at_timestamp)
# Stale-while-revalidate windows:
DOCS_FRESH_TTL = 21600   # 6h — within this, serve cache without revalidating
DOCS_STALE_TTL = 604800  # 7d — older than this, force a synchronous live re-fetch

# Realistic browser headers — docs.qualys.com/qualys.com sit behind Cloudflare, which
# blocks requests with a generic/bot User-Agent (returns an "Attention Required"
# challenge page instead of the doc). A normal browser UA passes.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

ALLOWED_DOC_HOSTS = (
    "docs.qualys.com",
    "artifacthub.io",
    "qualys.github.io",
    "github.com",
    "qualys.com",
)


def _strip_html(raw: str) -> str:
    """Reduce an HTML page to readable plain text (first 8000 chars)."""
    import re
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:8000]


async def _live_fetch_docs(url: str) -> str:
    """Fetch and parse a page live. Raises on HTTP error or anti-bot/login block."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=_BROWSER_HEADERS)
        resp.raise_for_status()
        raw = resp.text
        lowered = raw[:4000].lower()
        if any(marker in lowered for marker in (
            "attention required", "you have been blocked",
            "cf-error-details", "enable javascript and cookies to continue",
        )):
            raise RuntimeError("blocked by anti-bot protection")
        return _strip_html(raw)


async def _revalidate_docs(url: str) -> None:
    """Background refresh of a stale cache entry. Updates cache on success, else keeps old copy."""
    log = logging.getLogger("docs_cache")
    try:
        text = await _live_fetch_docs(url)
        _docs_cache[url] = (text, time.time())
        log.info("Revalidated: %s (%d chars)", url, len(text))
    except Exception as e:
        log.warning("Revalidate failed for %s (keeping cached copy): %s", url, e)


async def _fetch_docs(url: str, force: bool = False) -> str:
    """Fetch plain text from an allowed Qualys docs/Helm page (stale-while-revalidate).

    - Fresh cache (< DOCS_FRESH_TTL): served instantly.
    - Stale cache (>= DOCS_FRESH_TTL, < DOCS_STALE_TTL): served instantly AND refreshed
      in the background so the next request gets updated content.
    - No cache, very old cache, or force=True: fetched live synchronously.
    - Live failure with any cached copy available: cached copy is served as a fallback.
    """
    from urllib.parse import urlparse
    import asyncio

    host = urlparse(url).netloc.lstrip("www.")
    if not any(host.endswith(h) for h in ALLOWED_DOC_HOSTS):
        return json.dumps({"error": f"URL not allowed: {url}"})

    # Anti-guessing guard: Qualys doc (Flare) paths are unguessable, so restrict
    # docs.qualys.com / qualys.com fetches to the verified index. Other stable hosts
    # (artifacthub.io, github.com, qualys.github.io) are allowed as-is.
    is_qualys_docs = host.endswith("docs.qualys.com") or host.endswith("qualys.com")
    if is_qualys_docs and url not in _KNOWN_DOC_URL_SET:
        return json.dumps({
            "invalid_url": url,
            "message": (
                "That URL is not in the verified documentation index and may not exist. "
                "Retry fetch_docs with the closest matching URL from the list below, or "
                "answer from your embedded knowledge and cite the CS documentation home."
            ),
            "available_urls": _doc_index_text(),
        })

    now = time.time()
    cached = _docs_cache.get(url)

    if cached and not force:
        age = now - cached[1]
        if age < DOCS_STALE_TTL:
            # Serve cached content immediately; revalidate in the background if stale.
            if age >= DOCS_FRESH_TTL:
                asyncio.create_task(_revalidate_docs(url))
            return cached[0]

    # No usable cache (or forced / too old): fetch live synchronously.
    try:
        text = await _live_fetch_docs(url)
        _docs_cache[url] = (text, now)
        return text
    except Exception as e:
        if cached:
            return f"[WARN: live docs unavailable ({e}); using cached copy which may be outdated]\n\n{cached[0]}"
        return json.dumps({"error": str(e)})


# Pre-fetch the verified doc pages at startup so first queries are instant. Derived
# from KNOWN_DOC_URLS (single source of truth). The ArtifactHub page is skipped — it's
# JS-rendered and returns no usable text via fetch_docs (kept only as a link reference).
_PREWARM_URLS = [url for _label, url in KNOWN_DOC_URLS if "artifacthub.io" not in url]


async def _needs_refresh(url: str) -> bool:
    """Return True if the URL is missing or its cached copy is older than the fresh window."""
    cached = _docs_cache.get(url)
    return not cached or (time.time() - cached[1]) >= DOCS_FRESH_TTL


async def prewarm_docs_cache() -> None:
    """Pre-fetch all key doc pages into cache at startup so first user queries are instant."""
    import asyncio
    import logging
    logger = logging.getLogger("docs_cache")
    logger.info("Pre-warming docs cache for %d URLs...", len(_PREWARM_URLS))
    results = await asyncio.gather(*[_fetch_docs(url) for url in _PREWARM_URLS], return_exceptions=True)
    for url, result in zip(_PREWARM_URLS, results):
        if isinstance(result, Exception):
            logger.warning("Cache prewarm failed for %s: %s", url, result)
        elif isinstance(result, str) and result.lstrip().startswith('{"error"'):
            logger.warning("Cache prewarm error for %s: %s", url, result[:200])
        else:
            logger.info("Cached: %s (%d chars)", url, len(result))


async def refresh_docs_cache() -> tuple[int, int]:
    """Force-refresh all pre-warmed doc pages. Returns (succeeded, failed) counts."""
    import asyncio
    import logging
    logger = logging.getLogger("docs_cache")
    logger.info("Force-refreshing docs cache for %d URLs...", len(_PREWARM_URLS))
    results = await asyncio.gather(*[_fetch_docs(url, force=True) for url in _PREWARM_URLS], return_exceptions=True)
    succeeded = sum(1 for r in results if not isinstance(r, Exception))
    failed = len(results) - succeeded
    logger.info("Docs refresh complete: %d succeeded, %d failed", succeeded, failed)
    return succeeded, failed


async def _call_qualys_tool(name: str, inputs: dict) -> str:
    """Execute a Qualys API call for a tool using the shared route builder."""
    from qualys_client import get_async

    if name == "fetch_docs":
        return await _fetch_docs(inputs.get("url", ""))

    try:
        path, params = build_route(name, inputs)
        # Translate shared snake-case keys to Qualys API camelCase keys.
        param_map = {
            "page_number": "pageNumber",
            "page_size": "pageSize",
            "pagination_query": "paginationQuery",
        }
        params = {param_map.get(k, k): v for k, v in params.items()}
        result = await get_async(path, params)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


MAX_HISTORY_MESSAGES = 6
MAX_MESSAGE_CHARS = 12000
MAX_TOOL_RESULT_CHARS = 4000


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... [truncated]"


def _truncate_content(content: Any) -> Any:
    """Truncate message content whether it's a string, list of dicts, or Anthropic content blocks."""
    if isinstance(content, str):
        return _truncate_text(content, MAX_MESSAGE_CHARS)

    if not isinstance(content, list):
        return content

    trimmed = []
    for item in content:
        # Tool result list from user messages
        if isinstance(item, dict) and item.get("type") == "tool_result":
            raw = item.get("content", "")
            if isinstance(raw, str):
                raw = _truncate_text(raw, MAX_TOOL_RESULT_CHARS)
            elif isinstance(raw, list):
                raw = str(raw)[:MAX_TOOL_RESULT_CHARS]
            item = {**item, "content": raw}
        # Anthropic content block (TextBlock, ToolUseBlock)
        elif hasattr(item, "type") and getattr(item, "type") == "text" and hasattr(item, "text"):
            text = getattr(item, "text", "")
            if len(text) > MAX_MESSAGE_CHARS:
                item.text = text[:MAX_MESSAGE_CHARS] + "\n... [truncated]"
        trimmed.append(item)
    return trimmed


def _has_block_type(content: Any, block_type: str) -> bool:
    """Return True if content (str or list) contains a block of the given type."""
    if not isinstance(content, list):
        return False
    return any(
        (isinstance(b, dict) and b.get("type") == block_type)
        or (hasattr(b, "type") and getattr(b, "type") == block_type)
        for b in content
    )


def _truncate_messages(messages: list) -> list:
    """Keep the conversation within the model's context window.

    Guarantees:
    - First message is always role='user' (never a tool_result).
    - tool_use/tool_result pairs are never split by the history window.
    - Never returns an empty list.
    """
    # Step 1: truncate content length in each message
    msgs = [{**msg, "content": _truncate_content(msg.get("content"))} for msg in messages]
    # Drop messages with empty/None content
    msgs = [m for m in msgs if m.get("content")]

    # Step 2: trim to MAX_HISTORY_MESSAGES but always keep pairs together.
    # Walk from the tail and collect up to MAX_HISTORY_MESSAGES messages,
    # but if we'd cut between a tool_use and its tool_result, drop both.
    if len(msgs) > MAX_HISTORY_MESSAGES:
        tail = msgs[-MAX_HISTORY_MESSAGES:]
        # If the first message in tail is a tool_result, drop it (its tool_use was cut off)
        while tail and (
            tail[0].get("role") != "user"
            or _has_block_type(tail[0].get("content"), "tool_result")
        ):
            tail = tail[1:]
        msgs = tail

    # Step 3: ensure first message is a plain user message (not tool_result)
    while msgs and (
        msgs[0].get("role") != "user"
        or _has_block_type(msgs[0].get("content"), "tool_result")
    ):
        msgs = msgs[1:]

    # Step 4: scan and drop any remaining orphaned tool_result messages
    cleaned = []
    for msg in msgs:
        if msg.get("role") == "user" and _has_block_type(msg.get("content"), "tool_result"):
            prev = cleaned[-1] if cleaned else None
            if not (prev and _has_block_type(prev.get("content"), "tool_use")):
                continue  # orphaned — drop it
        cleaned.append(msg)

    # Step 5: fallback — if empty, return just the last plain user message
    if not cleaned:
        for msg in reversed(msgs or messages):
            if msg.get("role") == "user" and not _has_block_type(msg.get("content"), "tool_result"):
                return [msg]
        return []

    return cleaned


def _apply_persona_filter(text: str) -> str:
    """Replace any Claude/Anthropic self-references with Sheldon persona."""
    import re
    replacements = [
        (r"my name is Claude", "my name is Sheldon"),
        (r"I(?:'m| am) Claude", "I'm Sheldon"),
        (r"I(?:'m| am) an AI assistant created by Anthropic", "I'm Sheldon, your Qualys Container Security AI assistant"),
        (r"created by Anthropic", "built for Qualys Container Security"),
        (r"made by Anthropic", "built for Qualys Container Security"),
        (r"address me as Claude", "address me as Sheldon"),
        (r"\bClaude\b", "Sheldon"),
        (r"\bAnthropic\b", "Qualys"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


async def run_agent(user_message: str, history: list) -> AsyncGenerator[str, None]:
    client = get_client()
    messages = _truncate_messages(history + [{"role": "user", "content": user_message}])
    turn = 0

    logger.info(f"AGENT  user: {user_message[:120]}")

    while True:
        turn += 1
        messages = _truncate_messages(messages)
        logger.info(f"AGENT  turn {turn}  → calling Bedrock ({BEDROCK_MODEL})  messages={len(messages)}")
        response = client.messages.create(
            model=BEDROCK_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        logger.info(f"AGENT  turn {turn}  ← stop_reason={response.stop_reason}  tokens={response.usage.input_tokens}in/{response.usage.output_tokens}out")

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    yield _apply_persona_filter(block.text)
            logger.info("AGENT  done")
            break

        if response.stop_reason == "tool_use":
            tool_blocks = [block for block in response.content if block.type == "tool_use"]
            logger.info(f"AGENT  executing {len(tool_blocks)} tool call(s) in parallel")

            async def _run_tool(block):
                logger.info(f"AGENT  tool_call: {block.name}  inputs={json.dumps(block.input)}")
                result = await _call_qualys_tool(block.name, block.input)
                return {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }

            tool_results = await asyncio.gather(*[_run_tool(block) for block in tool_blocks])

            def _serialize_block(b):
                if isinstance(b, dict):
                    return b
                t = getattr(b, "type", "")
                if t == "tool_use":
                    return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                if t == "text":
                    return {"type": "text", "text": getattr(b, "text", "")}
                return {"type": t}

            assistant_content = [_serialize_block(b) for b in response.content]
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": list(tool_results)})
        else:
            break
