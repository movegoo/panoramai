---
name: mobsuccess-vibely-architecture
description: Guide complet DevOps AWS pour deployer un projet vibe-code (Next.js + FastAPI/Node) sur AWS ECS Fargate. Utilise ce skill quand l'utilisateur demande de deployer sur AWS, configurer une infra, ou migrer depuis Render/Railway/Heroku.
argument-hint: [action]
---

# Mobsuccess Vibely Architecture — Guide DevOps AWS

Guide de reference pour deployer un projet web (frontend + backend + DB) sur AWS, teste et valide en production chez Mobsuccess.

## Architecture cible

```
Vercel (frontend Next.js)
    |  HTTPS
    v
ALB (eu-central-1, ACM certificate, idle timeout configurable)
    |
    v
ECS Fargate (backend FastAPI/Node, public subnet, IP publique)
    |
    v
RDS PostgreSQL 16 (private subnet, encrypted, SSL)
    |
S3 (cache/assets statiques)
```

## Stack technique

| Composant | Choix | Justification |
|-----------|-------|---------------|
| **Frontend** | Vercel | Zero config, preview deploys, CDN mondial |
| **Backend compute** | ECS Fargate | Pas de serveur a gerer, timeout configurable (vs App Runner 120s max), scale a zero impossible mais ~$30/mois pour 1 vCPU |
| **Base de donnees** | RDS PostgreSQL 16 | Manage, backups auto, encrypted at rest + SSL in transit |
| **Secrets** | SSM Parameter Store | Gratuit (vs Secrets Manager $0.40/secret/mois) |
| **Cache/assets** | S3 | Stockage pas cher, chiffre AES-256 |
| **IaC** | Terraform | Multi-cloud, reproductible, state remote |
| **CI/CD** | GitHub Actions | Deja sur GitHub, OIDC auth vers AWS |
| **DNS** | Route 53 | Hosted zone pour le domaine custom |
| **HTTPS** | ACM | Certificats gratuits, renouvellement auto |

## Pourquoi PAS App Runner

App Runner est plus simple et moins cher (~$15/mois vs ~$78/mois) mais a un **hard limit de 120 secondes** sur les requetes HTTP. Si ton backend utilise :
- Server-Sent Events (SSE) pour du temps reel
- WebSockets
- MCP (Model Context Protocol) SSE
- Des requetes longues (generation IA, gros exports)

Alors App Runner est **incompatible**. ECS Fargate permet de configurer le timeout ALB (jusqu'a 4000s).

Si ton backend n'a PAS besoin de connexions longues, App Runner est le meilleur choix.

## Structure Terraform

```
infra/
  main.tf              # Provider AWS, backend S3 pour le state
  variables.tf         # Toutes les variables (env, region, sizing)
  vpc.tf               # VPC + subnets publics/prives
  rds.tf               # PostgreSQL RDS
  ecr.tf               # ECR pour les images Docker
  ecs.tf               # Cluster + task definition + service Fargate
  alb.tf               # Load balancer + listeners HTTP/HTTPS
  s3.tf                # Bucket S3 pour cache/assets
  ssm.tf               # Parameter Store (secrets + config)
  security_groups.tf   # Regles reseau
  dns.tf               # Route 53 records
  outputs.tf           # DNS de l'ALB, endpoint RDS, etc.
  dev.tfvars           # Sizing dev (0.5 vCPU, 1 GB)
  prod.tfvars          # Sizing prod (1 vCPU, 2 GB)
  backend-dev.hcl      # Backend S3 pour le state dev
  backend-prod.hcl     # Backend S3 pour le state prod
```

## Decisions d'architecture importantes

### 1. ECS dans les public subnets (pas de NAT Gateway)

```
Public subnets : ALB + ECS (avec IP publique)
Private subnets : RDS uniquement
```

**Pourquoi :** Le NAT Gateway coute ~$32/mois + $0.045/GB. En mettant ECS dans les public subnets avec `assign_public_ip = true`, les tasks accedent a internet directement. RDS reste en private subnet (pas accessible depuis internet).

**Securite :** Le Security Group d'ECS n'autorise que le port 8000 depuis l'ALB. Meme avec une IP publique, le container n'est pas accessible directement.

### 2. SSM Parameter Store (pas Secrets Manager)

SSM Parameter Store `SecureString` = gratuit, chiffre KMS.
Secrets Manager = $0.40/secret/mois. Pour 13 secrets = $5.20/mois pour rien.

Les deux supportent la rotation, mais pour du vibe-code, SSM suffit largement.

### 3. Un seul state Terraform, un workspace par env

```bash
# Dev (compte default)
terraform init -backend-config=backend-dev.hcl
terraform apply -var-file=dev.tfvars

# Prod
AWS_PROFILE=prod-panoramai terraform init -backend-config=backend-prod.hcl
terraform apply -var-file=prod.tfvars
```

Le state est stocke dans S3 avec un lock DynamoDB pour eviter les conflits.

### 4. ALB idle timeout = 3600s pour SSE

Si ton backend utilise SSE ou des connexions longues, le timeout par defaut de l'ALB (60s) va couper les connexions. Mets `idle_timeout = 3600` sur l'ALB.

## Profils AWS

Convention de nommage dans `~/.aws/credentials` :

```ini
[default]
# Compte dev (utilise par defaut)
aws_access_key_id = ...
aws_secret_access_key = ...

[prod-panoramai]
# Compte prod (explicite)
aws_access_key_id = ...
aws_secret_access_key = ...
```

Usage :
```bash
# Dev (implicite)
aws s3 ls
terraform apply -var-file=dev.tfvars

# Prod (explicite)
AWS_PROFILE=prod-panoramai aws s3 ls
AWS_PROFILE=prod-panoramai terraform apply -var-file=prod.tfvars
```

## Deploiement initial — Etape par etape

### Etape 1 : Bootstrap du state Terraform

Pour chaque compte AWS (dev puis prod) :

```bash
# Creer le bucket S3 pour le state
aws s3api create-bucket \
  --bucket monprojet-dev-terraform-state \
  --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1

aws s3api put-bucket-versioning \
  --bucket monprojet-dev-terraform-state \
  --versioning-configuration Status=Enabled

# Creer la table DynamoDB pour le lock
aws dynamodb create-table \
  --table-name monprojet-dev-terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-central-1
```

### Etape 2 : Terraform init + apply

```bash
cd infra/
terraform init -backend-config=backend-dev.hcl
terraform plan -var-file=dev.tfvars -var="db_password=$(openssl rand -base64 24)"
terraform apply -var-file=dev.tfvars -var="db_password=$(openssl rand -base64 24)"
```

### Etape 3 : Peupler les secrets SSM

```bash
# Depuis ton .env local
aws ssm put-parameter \
  --name "/monprojet/dev/DATABASE_URL" \
  --value "postgresql://user:pass@rds-endpoint:5432/dbname" \
  --type SecureString --overwrite
```

### Etape 4 : Build + push Docker vers ECR

Si Docker Desktop n'est pas disponible (laptop sans droits admin), utilise AWS CodeBuild :

```bash
# Creer un projet CodeBuild (une seule fois)
aws codebuild create-project \
  --name monprojet-dev-build \
  --source type=S3,location=monprojet-dev-cache/codebuild/source.zip \
  --artifacts type=NO_ARTIFACTS \
  --environment type=LINUX_CONTAINER,computeType=BUILD_GENERAL1_SMALL,image=aws/codebuild/standard:7.0,privilegedMode=true \
  --service-role arn:aws:iam::ACCOUNT_ID:role/codebuild-role

# Packager + uploader + lancer le build
cd backend/
zip -r /tmp/source.zip . -x "__pycache__/*"
aws s3 cp /tmp/source.zip s3://monprojet-dev-cache/codebuild/source.zip
aws codebuild start-build --project-name monprojet-dev-build
```

Le `buildspec.yml` dans le backend :
```yaml
version: 0.2
phases:
  pre_build:
    commands:
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI
  build:
    commands:
      - docker build -t $ECR_REPO_URI:latest .
  post_build:
    commands:
      - docker push $ECR_REPO_URI:latest
```

### Etape 5 : Deployer le service ECS

```bash
aws ecs update-service \
  --cluster monprojet-dev-cluster \
  --service monprojet-dev-api \
  --force-new-deployment
```

### Etape 6 : Migrer la base de donnees

Si la DB source est inaccessible depuis ta machine (private subnet), utilise un one-shot ECS task :

```bash
# Uploader le dump sur S3
aws s3 cp dump.pgdump s3://monprojet-dev-cache/migration/

# Lancer une task de migration avec postgres:latest
aws ecs register-task-definition \
  --family monprojet-migration \
  --requires-compatibilities FARGATE \
  --network-mode awsvpc --cpu 512 --memory 1024 \
  --execution-role-arn ... --task-role-arn ... \
  --container-definitions '[{
    "name": "migration",
    "image": "postgres:latest",
    "entryPoint": ["sh", "-c"],
    "command": ["apt-get update && apt-get install -y awscli && aws s3 cp s3://bucket/migration/dump.pgdump /tmp/ && pg_restore --no-owner --clean --if-exists -h RDS_HOST -U user -d dbname /tmp/dump.pgdump"],
    "environment": [{"name": "PGPASSWORD", "value": "..."}]
  }]'

aws ecs run-task --cluster ... --task-definition monprojet-migration \
  --launch-type FARGATE \
  --network-configuration '{"awsvpcConfiguration":{"subnets":["subnet-xxx"],"securityGroups":["sg-xxx"],"assignPublicIp":"ENABLED"}}'
```

**Attention :** Utilise `postgres:latest` (pas `postgres:16`) si le dump vient d'une version superieure. pg_restore ne peut pas lire un dump d'une version plus recente.

### Etape 7 : HTTPS + domaine custom

```bash
# Demander un certificat ACM
aws acm request-certificate \
  --domain-name "api.mondomaine.com" \
  --validation-method DNS

# Ajouter le CNAME de validation dans Route 53
# Attendre la validation (~2 min)

# Ajouter le listener HTTPS sur l'ALB
aws elbv2 create-listener \
  --load-balancer-arn ALB_ARN \
  --protocol HTTPS --port 443 \
  --certificates CertificateArn=CERT_ARN \
  --default-actions Type=forward,TargetGroupArn=TG_ARN \
  --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06

# Redirect HTTP → HTTPS
aws elbv2 modify-listener --listener-arn HTTP_LISTENER_ARN \
  --default-actions '[{"Type":"redirect","RedirectConfig":{"Protocol":"HTTPS","Port":"443","StatusCode":"HTTP_301"}}]'

# DNS : A record alias vers l'ALB
# Pour un apex de zone Route 53 : impossible de mettre un CNAME, utiliser ALIAS vers l'ALB
# Pour un sous-domaine : CNAME vers le hostname Vercel/ALB
```

## Pieges courants

| Piege | Solution |
|-------|----------|
| `pg_restore: unsupported version` | Le dump vient d'un PostgreSQL plus recent. Utiliser `postgres:latest` au lieu de `postgres:16` |
| ECS `run-task` command ignoree | Le Dockerfile a un `ENTRYPOINT`. Creer une task definition separee avec `entryPoint: ["sh", "-c"]` |
| Push GitHub rejete (workflow scope) | `gh auth refresh -h github.com -s workflow` puis utiliser `gh api` pour creer le fichier |
| SSM rejecte valeur vide | AWS SSM n'accepte pas les chaines vides. Mettre un placeholder "CHANGE_ME" |
| ALB coupe les SSE apres 60s | Mettre `idle_timeout = 3600` sur l'ALB |
| Docker Desktop non disponible | Utiliser AWS CodeBuild avec un buildspec.yml |
| CNAME sur un apex de zone Route 53 | Interdit. Utiliser un A record (IP fixe) ou un ALIAS (vers une ressource AWS) |
| NAT Gateway = $32/mois | Mettre ECS dans les public subnets avec IP publique. RDS reste en private |
| App Runner timeout 120s | Hard limit non configurable. Utiliser ECS Fargate si besoin de connexions longues |

## Couts mensuels estimes (eu-central-1)

| Ressource | Dev | Prod |
|-----------|-----|------|
| ECS Fargate (0.5/1 vCPU) | ~$15 | ~$30 |
| RDS PostgreSQL (t4g.micro/small) | ~$13 | ~$26 |
| ALB | ~$16 | ~$16 |
| S3 + ECR | ~$1 | ~$1 |
| CloudWatch | ~$2 | ~$5 |
| **Total** | **~$47** | **~$78** |

**Total dev + prod : ~$125/mois**

## RGPD / donnees en Europe

- Region `eu-central-1` (Francfort) pour toutes les ressources
- RDS encrypted at rest (AES-256) + SSL in transit
- S3 encrypted (SSE-S3)
- Pas de transfert hors UE (sauf Vercel CDN, mais pas de donnees perso dans le frontend)

## Pour aller plus loin

- Ajouter CloudTrail pour l'audit
- Configurer des alertes CloudWatch (CPU > 80%, erreurs 5xx)
- Mettre en place le CI/CD GitHub Actions avec OIDC
- Ajouter un WAF devant l'ALB si necessaire
