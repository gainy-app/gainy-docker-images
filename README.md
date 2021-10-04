```bash
aws configure
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 217303665077.dkr.ecr.us-east-1.amazonaws.com
docker build -t gainy .
docker tag gainy:latest 217303665077.dkr.ecr.us-east-1.amazonaws.com/gainy:latest
docker push 217303665077.dkr.ecr.us-east-1.amazonaws.com/gainy:latest
```