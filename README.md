
# secure-cicd-aws-github-oidc

## What it demonstrates

- Dockerized app
- GitHub Actions CI/CD
- No AWS access keys in GitHub secrets
- GitHub OIDC → AWS IAM role
- Trivy image scanning
- Push image to ECR
- Troubleshooting broken IAM policy

This project uses GitHub OpenID Connect (OIDC) to allow GitHub Actions to access AWS without storing AWS access keys.

Why OIDC is used

Traditional CI/CD pipelines store long-lived AWS access keys in GitHub Secrets.
This project avoids that by using short-lived credentials issued dynamically by AWS.

No static secrets. No key rotation.

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

I have used the full access for testing, you can only add the required access.

```AmazonEC2ContainerRegistryPowerUser```

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:GetRepositoryPolicy",
                "ecr:DescribeRepositories",
                "ecr:ListImages",
                "ecr:DescribeImages",
                "ecr:BatchGetImage",
                "ecr:GetLifecyclePolicy",
                "ecr:GetLifecyclePolicyPreview",
                "ecr:ListTagsForResource",
                "ecr:DescribeImageScanFindings",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:PutImage"
            ],
            "Resource": "*"
        }
    ]
}
```

#### IAM permissions

Initial broken policy (for troubleshooting)
- Missing ecr:PutImage

#### Then fix it by attaching:
or a custom least-privilege policy.

### How the authentication works (step by step)

1. Workflow starts in GitHub Actions

- Triggered by a push to the master branch.

2. GitHub issues a short-lived OIDC token

- The token includes claims such as:

  - Repository name

  - Branch name

  - Workflow identity

  - Audience (```sts.amazonaws.com```)

3.  GitHub sends this token to AWS STS

- Using  ```sts:AssumeRoleWithWebIdentity```

4.  AWS validates the token
- AWS checks:

  - The token was issued by ```token.actions.githubusercontent.com```

  - The repository name matches

  - The branch name matches

  - The audience is ```sts.amazonaws.com```

5.  AWS issues temporary credentials

- Valid only for a short time

- Scoped to the IAM role permissions

6.  GitHub Actions uses these credentials

- Logs in to ECR

- Pushes the Docker image

At no point are AWS access keys stored in GitHub.

### Why AWS trusts GitHub

AWS trusts GitHub because:

- An OIDC identity provider is configured in AWS IAM

- An IAM role trust policy explicitly allows GitHub Actions from this repo and branch

This ensures only this repository and branch can assume the role.

## Important fix: Branch and repo name must match exactly
- During setup, the pipeline failed with:

  ```Not authorized to perform sts:AssumeRoleWithWebIdentity```
#### Root cause

- The repository uses the master branch

- The IAM trust policy was configured for main

OIDC is strict. Even a branch name mismatch will break authentication.

#### Correct trust policy for this repository

Repository

```geekapt/DevSecOps-Series```

Branch

```master```

#### Final trust policy

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
          "token.actions.githubusercontent.com:sub": "repo:geekapt/DevSecOps-Series:ref:refs/heads/master",
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}

```

This fix allowed GitHub Actions to successfully assume the role.


### Troubleshooting notes (real-world issue)
#### Issue

Pipeline failed during AWS authentication.

Error

```Could not assume role with OIDC:```

```Not authorized to perform sts:AssumeRoleWithWebIdentity```


### Resolution

- Verified branch name (master)

- Updated IAM trust policy to match repo and branch

- Re-ran the workflow

This mirrors common production issues when teams first adopt OIDC.