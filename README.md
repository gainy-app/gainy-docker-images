## Gainy Base Docker Images

#### Registry auth:
```bash
aws configure
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 217303665077.dkr.ecr.us-east-1.amazonaws.com
```

#### Build and tag new local image: 
```
IMAGE_TAG=local make build
```