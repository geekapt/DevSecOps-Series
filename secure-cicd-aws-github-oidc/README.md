
# secure-cicd-aws-github-oidc

## What it demonstrates

- Dockerized app
- GitHub Actions CI/CD
- No AWS access keys in GitHub secrets
- GitHub OIDC → AWS IAM role
- Trivy image scanning
- Push image to ECR
- Troubleshooting broken IAM policy

### Simple app (keep it boring on purpose)

```
GitHub repo structure

secure-cicd-aws-github-oidc/
│
├── app/
│   ├── app.py
│   └── requirements.txt
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml
│
├── Dockerfile
├── README.md
└── trivy-config.yaml

```

#### Use a minimal Python Flask app
``` app/app.py```

```
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "Secure CI/CD with GitHub OIDC!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

```
#### app/requirements.txt
```flask```

#### Dockerfile

```
FROM python:3.11-slim

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app .
EXPOSE 8080
CMD ["python", "app.py"]

```

#### GitHub Actions pipeline
```.github/workflows/ci-cd.yml```

```
name: Secure CI/CD Pipeline

on:
  push:
    branches: [ "main" ]

permissions:
  id-token: write
  contents: read

jobs:
  build-and-push:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/github-oidc-ecr-role
          aws-region: ap-south-1

      - name: Login to Amazon ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build Docker image
        run: |
          docker build -t secure-demo:${{ github.sha }} .

      - name: Trivy image scan
        uses: aquasecurity/trivy-action@0.20.0
        with:
          image-ref: secure-demo:${{ github.sha }}
          severity: HIGH,CRITICAL
          exit-code: 1

      - name: Tag and push image
        run: |
          docker tag secure-demo:${{ github.sha }} <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/secure-demo:${{ github.sha }}
          docker push <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/secure-demo:${{ github.sha }}

```
#### AWS setup
IAM Role
- Role name
```github-oidc-ecr-role```

#### Trust policy

```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:sub": "repo:<YOUR_GITHUB_USERNAME>/secure-cicd-aws-github-oidc:ref:refs/heads/main"
        }
      }
    }
  ]
}

```

#### IAM permissions

Initial broken policy (for troubleshooting)
- Missing ecr:PutImage

#### Then fix it by attaching:
or a custom least-privilege policy.
